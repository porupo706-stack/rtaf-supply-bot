"""
setup_token.py — ออกกุญแจเข้าระบบ (ทำครั้งเดียว) ด้วยคำสั่งเดียว

    python setup_token.py

สิ่งที่สคริปต์ทำให้อัตโนมัติ:
  1. เปิด Chrome หน้าต่างชั่วคราว (โปรไฟล์ว่าง ไม่ปนกับของจริง)
  2. ให้คุณล็อกอินบัญชี Google เฉพาะกิจ แล้วกด "I agree" ในหน้าต่างนั้น
  3. จับ token แล้วแลกเป็นกุญแจถาวรให้เอง (ไม่ต้องคัดลอกอะไรด้วยมือ)
  4. พิมพ์บรรทัดที่ต้องวางใน Streamlit → App settings → Secrets
  5. ปิด Chrome และลบโปรไฟล์ชั่วคราวทิ้ง

ติดตั้งก่อนครั้งแรก:  pip install -r requirements-admin.txt
"""
from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time

DEFAULT_PORT = 9222


# ---------------------------------------------------------
# ตัวช่วย (ทดสอบแยกได้ ไม่ต้องใช้ Google จริง)
# ---------------------------------------------------------
def chrome_candidates(env: dict | None = None, platform: str | None = None) -> list[str]:
    """ตำแหน่งที่มักติดตั้ง Chrome ตามระบบปฏิบัติการ"""
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    if platform.startswith("win"):
        out = []
        for key in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
            base = env.get(key)
            if base:
                out.append(os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"))
        return out
    if platform == "darwin":
        return ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    return []


def find_chrome(explicit: str | None = None, env: dict | None = None, platform: str | None = None,
                exists=os.path.exists, which=shutil.which) -> str | None:
    """หาไฟล์ Chrome: ใช้ค่าที่ระบุ > ตำแหน่งมาตรฐาน > ชื่อคำสั่งใน PATH"""
    if explicit:
        return explicit if exists(explicit) else None
    for path in chrome_candidates(env, platform):
        if exists(path):
            return path
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        found = which(name)
        if found:
            return found
    return None


def find_free_port(preferred: int = DEFAULT_PORT) -> int:
    """ใช้พอร์ตที่ต้องการถ้าว่าง ไม่ว่างก็ให้ระบบเลือกให้"""
    for port in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    raise RuntimeError("หาพอร์ตว่างไม่ได้")


def wait_for_port(port: int, timeout: float = 30.0, host: str = "127.0.0.1") -> bool:
    """รอจน Chrome เปิดพอร์ตควบคุมพร้อม"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            if s.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.3)
    return False


def build_login_cmd(email: str, port: int, force: bool = False, python: str | None = None) -> list[str]:
    cmd = [python or sys.executable, "-m", "notebooklm", "login", "--master-token",
           "--account", email, "--cdp-url", f"http://localhost:{port}"]
    if force:
        cmd.append("--force")
    return cmd


def launch_chrome(chrome: str, port: int, profile_dir: str) -> subprocess.Popen:
    return subprocess.Popen([
        chrome,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
    ])


def cleanup(proc, profile_dir: str) -> None:
    """ปิด Chrome ที่เราเปิด และลบโปรไฟล์ชั่วคราว (ลองซ้ำเพราะ Windows ล็อกไฟล์ช้า)"""
    if proc is not None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    for _ in range(5):
        shutil.rmtree(profile_dir, ignore_errors=True)
        if not os.path.exists(profile_dir):
            return
        time.sleep(0.5)


def default_export() -> int:
    from export_master_token import main as export_main
    return export_main()


# ---------------------------------------------------------
# main
# ---------------------------------------------------------
def main(argv: list[str] | None = None, *, launch=launch_chrome, run_cmd=subprocess.call,
         export=default_export, wait=wait_for_port, ask=input) -> int:
    ap = argparse.ArgumentParser(description="ออกกุญแจเข้าระบบด้วยคำสั่งเดียว")
    ap.add_argument("--account", help="อีเมลบัญชี Google เฉพาะกิจ (ถ้าไม่ใส่จะถามตอนรัน)")
    ap.add_argument("--chrome", help="ตำแหน่งไฟล์ Chrome (ถ้าหาเองไม่เจอ)")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--force", action="store_true",
                    help="ออกใหม่ทับ แม้โปรไฟล์นี้เคยผูกกับบัญชีอื่น")
    args = ap.parse_args(argv)

    email = (args.account or ask("อีเมลบัญชี Google เฉพาะกิจ: ")).strip()
    if "@" not in email:
        print("❌ อีเมลไม่ถูกต้อง")
        return 2

    chrome = find_chrome(args.chrome)
    if not chrome:
        print("❌ ไม่พบ Google Chrome ในเครื่อง")
        print('   ติดตั้ง Chrome หรือระบุตำแหน่ง:  python setup_token.py --chrome "C:\\...\\chrome.exe"')
        return 2

    port = find_free_port(args.port)
    profile = tempfile.mkdtemp(prefix="rtaf-chrome-")
    proc = None
    try:
        print("▶ กำลังเปิด Chrome หน้าต่างชั่วคราว...")
        proc = launch(chrome, port, profile)
        if not wait(port):
            print("❌ Chrome เปิดไม่สำเร็จ (พอร์ตควบคุมไม่ตอบสนอง) ปิด Chrome ที่ค้างอยู่แล้วลองใหม่")
            return 1

        print()
        print("▶ ในหน้าต่าง Chrome ที่เด้งขึ้นมา:")
        print("    1) ล็อกอินบัญชี Google เฉพาะกิจ")
        print("    2) กดปุ่ม  I agree  แล้วรอเฉย ๆ (อย่าปิดหน้าต่าง)")
        print()
        code = run_cmd(build_login_cmd(email, port, args.force))
        if code != 0:
            print("❌ ออกกุญแจไม่สำเร็จ ดูข้อความด้านบน แล้วลองรันใหม่ (อย่าปิดหน้าต่าง Chrome ก่อนเสร็จ)")
            return 1

        print()
        return export()
    finally:
        cleanup(proc, profile)
        print("▶ ปิด Chrome ชั่วคราวและลบโปรไฟล์แล้ว")


if __name__ == "__main__":
    sys.exit(main())
