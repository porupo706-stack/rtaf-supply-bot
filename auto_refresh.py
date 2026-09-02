"""
auto_refresh.py (Enhanced with Keep-Alive)
──────────────────────────────────────────
ทำงาน 2 อย่างพร้อมกัน:
  1. อัปโหลด session ขึ้น Gist ทุก 3 นาที
  2. Ping NotebookLM จริงๆ ทุก 30 นาที (ต่ออายุ Google session)
"""

import time
import pathlib
import asyncio
import requests
import sys
from cryptography.fernet import Fernet
from datetime import datetime

# =========================================================
# CONFIG — ใส่ค่าเดียวกับ refresh_session.py
# =========================================================
GITHUB_TOKEN   = "YOUR_GITHUB_TOKEN_HERE"
GIST_ID        = "YOUR_GIST_ID_HERE"
ENCRYPTION_KEY = "YOUR_ENCRYPTION_KEY_HERE"

NOTEBOOK_ID = "53c42aa4-91a9-46b0-9094-2b480d0f0c5f"

UPLOAD_EVERY_MINUTES    = 3   # อัปโหลด Gist ทุกกี่นาที
KEEPALIVE_EVERY_MINUTES = 30  # Ping NotebookLM ทุกกี่นาที

# =========================================================
SESSION_PATH = (
    pathlib.Path.home()
    / ".notebooklm/profiles/default/storage_state.json"
)


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def upload_to_gist() -> bool:
    """อัปโหลด session ปัจจุบันขึ้น GitHub Gist"""
    if not SESSION_PATH.exists():
        log("❌ ไม่พบ session file — รัน refresh_session.bat ก่อน")
        return False
    try:
        content   = SESSION_PATH.read_text(encoding="utf-8")
        encrypted = Fernet(ENCRYPTION_KEY.encode()).encrypt(
            content.encode()
        ).decode()
        resp = requests.patch(
            f"https://api.github.com/gists/{GIST_ID}",
            headers={"Authorization": f"token {GITHUB_TOKEN}"},
            json={"files": {"session.enc": {"content": encrypted}}},
            timeout=15,
        )
        if resp.status_code == 200:
            log(f"✅ Gist อัปเดต ({len(content):,} bytes)")
            return True
        else:
            log(f"❌ Gist Error: {resp.status_code}")
            return False
    except Exception as e:
        log(f"❌ Upload Error: {e}")
        return False


async def keepalive_ping() -> bool:
    """
    Ping NotebookLM จริงๆ เพื่อต่ออายุ Google session
    หลัง ping แล้ว cookie จะถูกอัปเดต → save ทับไฟล์เดิม
    """
    try:
        from notebooklm import NotebookLMClient
        log("🔄 กำลัง ping NotebookLM เพื่อต่ออายุ session...")
        async with NotebookLMClient.from_storage() as client:
            # แค่ connect แล้ว disconnect ก็พอ — Google จะ refresh cookie อัตโนมัติ
            await client.chat.ask(NOTEBOOK_ID, ".")
        log("✅ Keep-alive สำเร็จ — Google session ต่ออายุแล้ว")
        return True
    except Exception as e:
        log(f"⚠️ Keep-alive ล้มเหลว: {e}")
        return False


def validate_config() -> bool:
    errors = []
    if "XXXX" in GITHUB_TOKEN:  errors.append("GITHUB_TOKEN")
    if "XXXX" in GIST_ID:       errors.append("GIST_ID")
    if "XXXX" in ENCRYPTION_KEY: errors.append("ENCRYPTION_KEY")
    if errors:
        print("❌ กรุณาตั้งค่าใน auto_refresh.py:")
        for e in errors:
            print(f"   • {e}")
        return False
    return True


def main():
    print("╔══════════════════════════════════════════════════╗")
    print("║   RTAF Supply Bot — Auto Session Manager        ║")
    print(f"║   อัปโหลด Gist ทุก {UPLOAD_EVERY_MINUTES} นาที                      ║")
    print(f"║   Ping NotebookLM ทุก {KEEPALIVE_EVERY_MINUTES} นาที                  ║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    if not validate_config():
        sys.exit(1)

    upload_counter   = 0
    keepalive_counter = 0
    upload_interval   = UPLOAD_EVERY_MINUTES * 60
    keepalive_interval = KEEPALIVE_EVERY_MINUTES * 60

    # รันทันทีตอนเริ่ม
    upload_to_gist()
    asyncio.run(keepalive_ping())
    upload_to_gist()  # อัปโหลดอีกครั้งหลัง keepalive (cookie ใหม่)

    last_upload   = time.time()
    last_keepalive = time.time()

    while True:
        now = time.time()

        # อัปโหลด Gist
        if now - last_upload >= upload_interval:
            upload_to_gist()
            last_upload = now

        # Keep-alive ping
        if now - last_keepalive >= keepalive_interval:
            asyncio.run(keepalive_ping())
            upload_to_gist()  # อัปโหลดทันทีหลัง keepalive
            last_keepalive = now

        time.sleep(30)  # ตรวจทุก 30 วินาที


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⛔ หยุดแล้ว")
