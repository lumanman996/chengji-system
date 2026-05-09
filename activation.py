"""
机器绑定 + 激活码验证模块。
"""
import hashlib
import hmac as hmac_mod
import json
import os
import subprocess
import sys
from datetime import datetime

# ── Secret Key (XOR-obfuscated, split into two 16-byte parts) ──
_K1 = bytes.fromhex("54276810b56c95f5823211332dab7ac3")
_K2 = bytes.fromhex("caff542e7be4fdd11cf7f205cc4b2ecc")
SECRET_KEY = _K1 + bytes(a ^ b for a, b in zip(_K1, _K2))

_CONFIG_DIR = os.path.join(os.environ.get("CHENGJI_APP_DIR", "."), "config")
_ACTIVATION_FILE = os.path.join(_CONFIG_DIR, "activation.json")


# ── Machine Fingerprint ──

def _powershell_query(ps_command):
    """Run a PowerShell Get-CimInstance command, return cleaned value."""
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", ps_command],
            timeout=15, stderr=subprocess.DEVNULL,
        )
        value = out.decode("utf-8", errors="ignore").strip()
        return value if value else ""
    except Exception:
        return ""


def get_machine_id():
    """Collect hardware info, return 32-char hex SHA-256 prefix."""
    cpu = _powershell_query(
        "Get-CimInstance Win32_Processor | Select-Object -ExpandProperty ProcessorId"
    )
    mb = _powershell_query(
        "Get-CimInstance Win32_BaseBoard | Select-Object -ExpandProperty SerialNumber"
    )
    disk = _powershell_query(
        "Get-CimInstance Win32_DiskDrive | Select-Object -First 1 -ExpandProperty SerialNumber"
    )
    parts = [p for p in [cpu, mb, disk] if p and "fill" not in p.lower()]
    if not parts:
        return None
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# ── Activation Code Verification ──

def _compute_hmac(school_code, machine_id):
    msg = (school_code + machine_id).encode()
    return hmac_mod.new(SECRET_KEY, msg, hashlib.sha256).hexdigest()[:8]


def verify_code(activation_code, machine_id):
    """Parse and verify an activation code. Returns (school_code, valid)."""
    try:
        parts = activation_code.strip().upper().split("-")
        if len(parts) != 4 or parts[0] != "V1":
            return None, False
        _, school_code, hash8, hmac8 = parts
        if hash8 != machine_id[:8].upper():
            return None, False
        expected = _compute_hmac(school_code, machine_id).upper()
        if hmac_mod.compare_digest(hmac8, expected):
            return school_code, True
        return None, False
    except Exception:
        return None, False


# ── Self-Integrity Check ──

def _self_hash():
    path = os.path.abspath(__file__)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ── Activation State Management ──

def _load():
    if not os.path.exists(_ACTIVATION_FILE):
        return None
    with open(_ACTIVATION_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save(data):
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    with open(_ACTIVATION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetFileAttributesW(
            str(_ACTIVATION_FILE), 0x02
        )


def check_activation():
    """Returns True if activated and integrity is intact."""
    data = _load()
    if not data or not data.get("activated"):
        return False
    machine_id = get_machine_id()
    if not machine_id:
        return False
    if data.get("machine_id") != machine_id:
        return False
    stored_hash = data.get("check_hash")
    if stored_hash:
        current_hash = _self_hash()
        if current_hash and stored_hash != current_hash:
            return False
    return True


def try_activate(code):
    """Attempt to activate with given code."""
    machine_id = get_machine_id()
    if not machine_id:
        return {"success": False, "error": "无法获取机器码，请联系管理员。"}
    school_code, valid = verify_code(code, machine_id)
    if not valid:
        return {"success": False, "error": "激活码无效或与本机不匹配。"}
    data = {
        "activated": True,
        "machine_id": machine_id,
        "activation_code": code.strip().upper(),
        "school": school_code,
        "activated_at": datetime.now().isoformat(),
        "check_hash": _self_hash(),
    }
    _save(data)
    return {"success": True, "error": ""}
