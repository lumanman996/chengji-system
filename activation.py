"""
机器绑定 + 激活码验证模块。
支持：永久激活 + 限时试用（3天）
"""
import hashlib
import hmac as hmac_mod
import json
import os
import subprocess
import sys
import winreg
from datetime import datetime, timedelta

# ── Secret Key (XOR-obfuscated, split into two 16-byte parts) ──
_K1 = bytes.fromhex("54276810b56c95f5823211332dab7ac3")
_K2 = bytes.fromhex("caff542e7be4fdd11cf7f205cc4b2ecc")
SECRET_KEY = _K1 + bytes(a ^ b for a, b in zip(_K1, _K2))

_CONFIG_DIR = os.path.join(os.environ.get("CHENGJI_APP_DIR", "."), "config")
_ACTIVATION_FILE = os.path.join(_CONFIG_DIR, "activation.json")
_TRIAL_DAYS = 3  # 试用天数

# 注册表路径（用于存储试用开始时间，防止删除文件重置试用）
_REG_KEY = r"Software\ChengjiSystem"
_REG_VALUE = "TrialStart"


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
    """Parse and verify an activation code. Returns (school_code, valid, is_trial)."""
    try:
        parts = activation_code.strip().upper().split("-")
        if len(parts) != 4:
            return None, False, False
        prefix, school_code, hash8, hmac8 = parts
        # V1 = 永久激活，T1 = 试用激活
        if prefix not in ("V1", "T1"):
            return None, False, False
        if hash8 != machine_id[:8].upper():
            return None, False, False
        expected = _compute_hmac(school_code, machine_id).upper()
        if hmac_mod.compare_digest(hmac8, expected):
            return school_code, True, prefix == "T1"
        return None, False, False
    except Exception:
        return None, False, False


# ── Trial Management ──

def _read_registry():
    """从注册表读取试用开始时间"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, _REG_VALUE)
        winreg.CloseKey(key)
        return value
    except Exception:
        return None


def _write_registry(value):
    """写入试用开始时间到注册表"""
    try:
        key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_WRITE)
        winreg.SetValueEx(key, _REG_VALUE, 0, winreg.REG_SZ, value)
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def _get_trial_start():
    """获取试用开始时间（优先注册表，其次文件）"""
    # 1. 从注册表读取
    reg_value = _read_registry()
    if reg_value:
        try:
            return datetime.fromisoformat(reg_value).replace(tzinfo=None)
        except Exception:
            pass

    # 2. 从文件读取
    trial_file = os.path.join(_CONFIG_DIR, "trial.dat")
    if os.path.exists(trial_file):
        try:
            with open(trial_file, "r") as f:
                data = json.load(f)
                start = datetime.fromisoformat(data["start"]).replace(tzinfo=None)
                # 同步到注册表
                _write_registry(data["start"])
                return start
        except Exception:
            pass

    return None


def _save_trial_start(start_time):
    """保存试用开始时间（同时写入注册表和文件）"""
    iso_str = start_time.isoformat()

    # 1. 写入注册表
    _write_registry(iso_str)

    # 2. 写入文件
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    trial_file = os.path.join(_CONFIG_DIR, "trial.dat")
    with open(trial_file, "w") as f:
        json.dump({"start": iso_str, "machine_id": get_machine_id()}, f)

    # 3. 设置隐藏属性
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetFileAttributesW(str(trial_file), 0x02)


def check_trial():
    """检查试用状态。返回 (is_valid, remaining_days, message)"""
    machine_id = get_machine_id()
    if not machine_id:
        return False, 0, "无法获取机器码"

    start = _get_trial_start()

    # 首次运行：记录试用开始时间
    if not start:
        start = datetime.now()
        _save_trial_start(start)

    # 检查是否过期
    elapsed = (datetime.now() - start).days
    remaining = _TRIAL_DAYS - elapsed

    if remaining <= 0:
        return False, 0, f"试用期已结束（共{_TRIAL_DAYS}天），请购买激活码"

    return True, remaining, f"试用期剩余 {remaining} 天"


# ── Self-Integrity Check ──

def _self_hash():
    if getattr(sys, 'frozen', False):
        return None  # 打包模式下跳过完整性校验（PyInstaller .pyc 哈希每次打包不同）
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
    """检查激活状态。返回 (status, message)
    status: "activated" | "trial" | "expired" | "invalid"
    """
    data = _load()

    # 1. 检查永久激活
    if data and data.get("activated"):
        machine_id = get_machine_id()
        if machine_id and data.get("machine_id") == machine_id:
            stored_hash = data.get("check_hash")
            if stored_hash:
                current_hash = _self_hash()
                if current_hash and stored_hash != current_hash:
                    return "invalid", "系统文件被修改，请重新激活"
            return "activated", "已激活"

    # 2. 检查试用状态
    is_valid, remaining, message = check_trial()
    if is_valid:
        return "trial", message

    return "expired", message


def try_activate(code):
    """Attempt to activate with given code."""
    machine_id = get_machine_id()
    if not machine_id:
        return {"success": False, "error": "无法获取机器码，请联系管理员。"}
    school_code, valid, is_trial = verify_code(code, machine_id)
    if not valid:
        return {"success": False, "error": "激活码无效或与本机不匹配。"}

    if is_trial:
        # 试用激活码：重置试用开始时间
        _save_trial_start(datetime.now())
        return {"success": True, "error": "", "is_trial": True}

    # 永久激活码
    data = {
        "activated": True,
        "machine_id": machine_id,
        "activation_code": code.strip().upper(),
        "school": school_code,
        "activated_at": datetime.now().isoformat(),
        "check_hash": _self_hash(),
    }
    _save(data)
    return {"success": True, "error": "", "is_trial": False}
