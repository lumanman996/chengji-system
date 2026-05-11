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


def _cli_mode():
    """命令行参数模式"""
    if sys.argv[1] == "--show-machine":
        mid = get_machine_id()
        if mid:
            print(f"本机机器码: {mid}")
        else:
            print("无法获取机器码")
        return

    if sys.argv[1] == "--batch":
        if len(sys.argv) < 4:
            print("用法: admin_genkey.py --batch <学校代码> <机器码文件>")
            return
        school = sys.argv[2]
        with open(sys.argv[3]) as f:
            for line in f:
                mid = line.strip()
                if mid:
                    code = generate(school, mid, is_trial=False)
                    print(f"{mid}  →  {code}")
        return

    if sys.argv[1] == "--batch-trial":
        if len(sys.argv) < 4:
            print("用法: admin_genkey.py --batch-trial <学校代码> <机器码文件>")
            return
        school = sys.argv[2]
        with open(sys.argv[3]) as f:
            for line in f:
                mid = line.strip()
                if mid:
                    code = generate(school, mid, is_trial=True)
                    print(f"{mid}  →  {code}")
        return

    if sys.argv[1] == "--trial":
        if len(sys.argv) < 4:
            print("用法: admin_genkey.py --trial <学校代码> <机器码>")
            return
        school, mid = sys.argv[2], sys.argv[3]
        code = generate(school, mid, is_trial=True)
        print(f"学校代码: {school}")
        print(f"机器码:   {mid}")
        print(f"试用激活码: {code}")
        print(f"（试用期: 3天）")
        return

    # 生成永久激活码
    if len(sys.argv) < 3:
        print("用法: admin_genkey.py <学校代码> <机器码>")
        return
    school, mid = sys.argv[1], sys.argv[2]
    code = generate(school, mid, is_trial=False)
    print(f"学校代码: {school}")
    print(f"机器码:   {mid}")
    print(f"激活码:   {code}")


def _prompt(msg=""):
    """input with EOF protection"""
    try:
        return input(msg).strip()
    except EOFError:
        return ""


def _interactive_mode():
    """交互模式：双击 exe 时进入"""
    print("=" * 44)
    print("  激活码生成工具（管理员专用）")
    print("=" * 44)
    print()

    while True:
        print("┌────────────────────────────┐")
        print("│  1. 查看本机机器码          │")
        print("│  2. 生成永久激活码          │")
        print("│  3. 生成试用激活码（3天）    │")
        print("│  0. 退出                   │")
        print("└────────────────────────────┘")
        print()
        choice = _prompt("请选择功能 [0-3]: ")
        print()

        if choice == "0" or choice == "":
            break

        elif choice == "1":
            mid = get_machine_id()
            if mid:
                print(f"本机机器码: {mid}")
            else:
                print("无法获取机器码，请检查系统权限。")

        elif choice == "2":
            school = _prompt("学校代码: ")
            mid = _prompt("机器码:   ")
            if not school or not mid:
                print("错误：学校代码和机器码不能为空。")
            else:
                code = generate(school, mid, is_trial=False)
                print(f"\n激活码: {code}")

        elif choice == "3":
            school = _prompt("学校代码: ")
            mid = _prompt("机器码:   ")
            if not school or not mid:
                print("错误：学校代码和机器码不能为空。")
            else:
                code = generate(school, mid, is_trial=True)
                print(f"\n试用激活码: {code}（试用期: 3天）")

        else:
            print("无效选择，请输入 0-3。")

        print()


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        _cli_mode()
    else:
        _interactive_mode()
        _prompt("\n按 Enter 键退出...")
