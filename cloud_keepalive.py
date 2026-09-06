"""
cloud_keepalive.py
──────────────────
รันบน GitHub Actions ทุก 20 นาที:
  1. ดึง session จาก GitHub Gist
  2. Ping NotebookLM (ต่ออายุ Google session)
  3. อัปโหลด session ที่อัปเดตแล้วกลับ Gist
"""

import os
import asyncio
import pathlib
import requests
from cryptography.fernet import Fernet
from datetime import datetime

# =========================================================
# Config — ดึงจาก GitHub Secrets (ห้ามใส่ค่าตรงนี้!)
# =========================================================
GIST_TOKEN     = os.environ["GIST_TOKEN"]
GIST_ID        = os.environ["GIST_ID"]
ENCRYPTION_KEY = os.environ["ENCRYPTION_KEY"]
NOTEBOOK_ID    = os.environ["NOTEBOOK_ID"]

SESSION_PATH = (
    pathlib.Path.home()
    / ".notebooklm/profiles/default/storage_state.json"
)


def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def download_session() -> str | None:
    """ดึง session จาก Gist และถอดรหัส"""
    try:
        resp = requests.get(
            f"https://api.github.com/gists/{GIST_ID}",
            headers={"Authorization": f"token {GIST_TOKEN}"},
            timeout=15,
        )
        if resp.status_code != 200:
            log(f"❌ Gist error: {resp.status_code}")
            return None
        encrypted = resp.json()["files"]["session.enc"]["content"]
        return Fernet(ENCRYPTION_KEY.encode()).decrypt(encrypted.encode()).decode()
    except Exception as e:
        log(f"❌ ดึง session ล้มเหลว: {e}")
        return None


def upload_session(content: str) -> bool:
    """เข้ารหัสและอัปโหลด session กลับ Gist"""
    try:
        encrypted = Fernet(ENCRYPTION_KEY.encode()).encrypt(content.encode()).decode()
        resp = requests.patch(
            f"https://api.github.com/gists/{GIST_ID}",
            headers={"Authorization": f"token {GIST_TOKEN}"},
            json={"files": {"session.enc": {"content": encrypted}}},
            timeout=15,
        )
        return resp.status_code == 200
    except Exception as e:
        log(f"❌ อัปโหลด session ล้มเหลว: {e}")
        return False


async def keepalive_ping():
    """Ping NotebookLM จริงๆ เพื่อต่ออายุ Google session"""
    from notebooklm import NotebookLMClient
    async with NotebookLMClient.from_storage() as client:
        await client.chat.ask(NOTEBOOK_ID, "สวัสดี")


def main():
    log("=" * 50)
    log("RTAF Supply Bot — Cloud Keep-Alive")
    log("=" * 50)

    # Step 1: ดึง session จาก Gist
    log("📥 กำลังดึง session จาก Gist...")
    session_json = download_session()
    if not session_json:
        raise SystemExit("❌ ดึง session ไม่ได้ — หยุดทำงาน")

    # Step 2: บันทึก session file ลงเครื่อง runner
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    SESSION_PATH.write_text(session_json, encoding="utf-8")
    log(f"✅ session file พร้อม ({len(session_json):,} bytes)")

    # Step 3: Ping NotebookLM เพื่อต่ออายุ
    log("🔄 กำลัง ping NotebookLM...")
    try:
        asyncio.run(keepalive_ping())
        log("✅ Keep-alive สำเร็จ — session ต่ออายุแล้ว")
    except Exception as e:
        log(f"⚠️ Keep-alive ล้มเหลว (ยังอัปโหลด session เดิม): {e}")

    # Step 4: อัปโหลด session กลับ Gist (อาจมี cookie ใหม่หลัง ping)
    log("📤 กำลังอัปโหลด session กลับ Gist...")
    if SESSION_PATH.exists():
        updated_json = SESSION_PATH.read_text(encoding="utf-8")
        if upload_session(updated_json):
            log("✅ Gist อัปเดตสำเร็จ")
        else:
            log("❌ Gist อัปเดตล้มเหลว")

    log("🏁 เสร็จสิ้น")


if __name__ == "__main__":
    main()
