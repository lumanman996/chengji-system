"""
激活码生成工具 — 管理员专用，不随 exe 分发。

用法:
    python admin_genkey.py <学校代码> <机器码>        # 生成永久激活码
    python admin_genkey.py --trial <学校代码> <机器码>  # 生成试用激活码（3天）
    python admin_genkey.py --show-machine              # 查看本机机器码
    python admin_genkey.py --batch <学校代码> <文件>     # 批量生成永久激活码
    python admin_genkey.py --batch-trial <学校代码> <文件>  # 批量生成试用激活码

示例:
    python admin_genkey.py SCHOOL a3f29b01c8d4e6f71234abcdef567890
    python admin_genkey.py --trial SCHOOL a3f29b01c8d4e6f71234abcdef567890
"""
import hashlib
import hmac as hmac_mod
import subprocess
import sys

# ── 与 activation.py 相同的密钥 ──
_K1 = bytes.fromhex("54276810b56c95f5823211332dab7ac3")
_K2 = bytes.fromhex("caff542e7be4fdd11cf7f205cc4b2ecc")
SECRET_KEY = _K1 + bytes(a ^ b for a, b in zip(_K1, _K2))


def _powershell_query(ps_command):
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


def generate(school_code, machine_id, is_trial=False):
    school_code = school_code.upper()
    machine_id = machine_id.lower()
    msg = (school_code + machine_id).encode()
    hmac8 = hmac_mod.new(SECRET_KEY, msg, hashlib.sha256).hexdigest()[:8]
    prefix = "T1" if is_trial else "V1"
    return f"{prefix}-{school_code}-{machine_id[:8].upper()}-{hmac8.upper()}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == "--show-machine":
        mid = get_machine_id()
        if mid:
            print(f"本机机器码: {mid}")
        else:
            print("无法获取机器码")
        sys.exit(0)

    # 批量生成永久激活码
    if sys.argv[1] == "--batch":
        if len(sys.argv) < 4:
            print("用法: python admin_genkey.py --batch <学校代码> <机器码文件>")
            sys.exit(1)
        school = sys.argv[2]
        with open(sys.argv[3]) as f:
            for line in f:
                mid = line.strip()
                if mid:
                    code = generate(school, mid, is_trial=False)
                    print(f"{mid}  →  {code}")
        sys.exit(0)

    # 批量生成试用激活码
    if sys.argv[1] == "--batch-trial":
        if len(sys.argv) < 4:
            print("用法: python admin_genkey.py --batch-trial <学校代码> <机器码文件>")
            sys.exit(1)
        school = sys.argv[2]
        with open(sys.argv[3]) as f:
            for line in f:
                mid = line.strip()
                if mid:
                    code = generate(school, mid, is_trial=True)
                    print(f"{mid}  →  {code}")
        sys.exit(0)

    # 生成试用激活码
    if sys.argv[1] == "--trial":
        if len(sys.argv) < 4:
            print("用法: python admin_genkey.py --trial <学校代码> <机器码>")
            sys.exit(1)
        school, mid = sys.argv[2], sys.argv[3]
        code = generate(school, mid, is_trial=True)
        print(f"学校代码: {school}")
        print(f"机器码:   {mid}")
        print(f"试用激活码: {code}")
        print(f"（试用期: 3天）")
        sys.exit(0)

    # 生成永久激活码
    if len(sys.argv) < 3:
        print("用法: python admin_genkey.py <学校代码> <机器码>")
        sys.exit(1)

    school, mid = sys.argv[1], sys.argv[2]
    code = generate(school, mid, is_trial=False)
    print(f"学校代码: {school}")
    print(f"机器码:   {mid}")
    print(f"激活码:   {code}")
