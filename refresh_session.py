"""
refresh_session.py
──────────────────
รันไฟล์นี้เมื่อ session Google หมดอายุ
จะทำให้ครบทุกขั้นตอนอัตโนมัติ:
  1. เปิด browser ให้ login Google
  2. อ่าน session ใหม่
  3. เข้ารหัส
  4. อัปโหลดไปยัง GitHub Gist
  5. แอปบน Streamlit Cloud จะดึงไปใช้เองอัตโนมัติ
"""

import subprocess
import pathlib
import requests
import sys
from cryptography.fernet import Fernet

# =========================================================
# ⚙️ CONFIG — แก้ค่าเหล่านี้เพียงครั้งเดียว
# =========================================================

GITHUB_TOKEN = "ghp_XXXXXXXXXXXXXXXXXXXX"
# วิธีสร้าง: github.com → Settings → Developer settings
#            → Personal access tokens → Tokens (classic)
#            → Generate new token → ติ๊กแค่ "gist" → Copy

GIST_ID = "XXXXXXXXXXXXXXXXXXXX"
# วิธีสร้าง: gist.github.com → New gist
#            → ใส่ชื่อไฟล์ "session.enc" → ใส่ข้อความอะไรก็ได้
#            → Create secret gist
#            → copy ID จาก URL: gist.github.com/username/[GIST_ID]

ENCRYPTION_KEY = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX="
# ได้จากการรัน generate_key.py

# =========================================================
# ห้ามแก้ด้านล่างนี้
# =========================================================

SESSION_PATH = (
    pathlib.Path.home()
    / ".notebooklm"
    / "profiles"
    / "default"
    / "storage_state.json"
)


def banner(text: str):
    print()
    print("─" * 55)
    print(f"  {text}")
    print("─" * 55)


def encrypt(content: str) -> str:
    f = Fernet(ENCRYPTION_KEY.encode())
    return f.encrypt(content.encode()).decode()


def update_gist(encrypted_content: str) -> bool:
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    data = {"files": {"session.enc": {"content": encrypted_content}}}
    try:
        resp = requests.patch(
            f"https://api.github.com/gists/{GIST_ID}",
            headers=headers,
            json=data,
            timeout=20,
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"  ❌ ไม่สามารถเชื่อมต่อ GitHub: {e}")
        return False


def validate_config() -> bool:
    errors = []
    if "XXXX" in GITHUB_TOKEN:
        errors.append("GITHUB_TOKEN ยังไม่ได้ตั้งค่า")
    if "XXXX" in GIST_ID:
        errors.append("GIST_ID ยังไม่ได้ตั้งค่า")
    if "XXXX" in ENCRYPTION_KEY:
        errors.append("ENCRYPTION_KEY ยังไม่ได้ตั้งค่า (รัน generate_key.py ก่อน)")
    if errors:
        print("❌ กรุณาตั้งค่าต่อไปนี้ใน refresh_session.py:")
        for e in errors:
            print(f"   • {e}")
        return False
    return True


def main():
    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║   RTAF Supply Bot — Session Auto-Refresher      ║")
    print("╚══════════════════════════════════════════════════╝")

    # ตรวจ config
    if not validate_config():
        input("\nกด Enter เพื่อปิด...")
        sys.exit(1)

    # ขั้นตอนที่ 1: Login
    banner("ขั้นตอน 1/3 — Login Google ผ่าน NotebookLM")
    print("  กรุณา login บน browser ที่จะเปิดขึ้นมา...")
    print("  (ถ้าใช้ QR ให้สแกนด้วยมือถือ)")
    print()

    try:
        subprocess.run(
            ["python", "-m", "notebooklm", "login"],
            check=True
        )
    except subprocess.CalledProcessError:
        print("❌ Login ล้มเหลว กรุณาลองใหม่")
        input("\nกด Enter เพื่อปิด...")
        sys.exit(1)

    # ขั้นตอนที่ 2: อ่านและเข้ารหัส session
    banner("ขั้นตอน 2/3 — เข้ารหัส Session")

    if not SESSION_PATH.exists():
        print(f"  ❌ ไม่พบไฟล์: {SESSION_PATH}")
        print("  Login อาจไม่สำเร็จ กรุณาลองใหม่")
        input("\nกด Enter เพื่อปิด...")
        sys.exit(1)

    session_content = SESSION_PATH.read_text(encoding="utf-8")
    encrypted = encrypt(session_content)
    print(f"  ✅ Session ขนาด {len(session_content):,} bytes — เข้ารหัสสำเร็จ")

    # ขั้นตอนที่ 3: อัปโหลด Gist
    banner("ขั้นตอน 3/3 — อัปโหลดไปยัง GitHub Gist")
    print("  กำลังอัปโหลด...", end="", flush=True)

    if update_gist(encrypted):
        print(" ✅")
        print()
        print("╔══════════════════════════════════════════════════╗")
        print("║  ✅ สำเร็จ! แอปจะดึง session ใหม่อัตโนมัติ      ║")
        print("║  ไม่ต้องแก้ไข Streamlit Secrets อีกแล้ว!        ║")
        print("╚══════════════════════════════════════════════════╝")
    else:
        print(" ❌")
        print()
        print("  อัปโหลดไม่สำเร็จ ตรวจสอบ:")
        print("  • GITHUB_TOKEN ถูกต้องและมีสิทธิ์ gist")
        print("  • GIST_ID ถูกต้อง")
        print("  • มีการเชื่อมต่ออินเทอร์เน็ต")

    print()
    input("กด Enter เพื่อปิด...")


if __name__ == "__main__":
    main()
