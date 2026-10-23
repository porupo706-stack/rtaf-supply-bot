"""
export_master_token.py — รันบนคอมพิวเตอร์ของคุณ (หลัง `notebooklm login --master-token`)

อ่าน master_token.json ของ profile ปัจจุบัน แล้วพิมพ์บรรทัดที่ต้องวางใน
Streamlit → App settings → Secrets  (ห้ามส่งต่อ / ห้าม commit / ห้ามแคปหน้าจอ)
"""
import json
import sys

from notebooklm.auth import MasterTokenError, read_master_token
from notebooklm.paths import get_master_token_path


def main() -> int:
    path = get_master_token_path()
    try:
        data = read_master_token(path)
    except MasterTokenError as e:
        print(f"❌ อ่านไฟล์ไม่ได้: {e}")
        return 1
    if not data:
        print(f"❌ ไม่พบ {path}")
        print('   รันก่อน:  notebooklm login --master-token --account อีเมลบัญชีเฉพาะกิจ')
        return 1

    payload = json.dumps(
        {k: data[k] for k in ("version", "email", "android_id", "master_token")},
        ensure_ascii=False,
    )
    print("=" * 60)
    print("วางบรรทัดนี้ใน Streamlit → App settings → Secrets:")
    print("=" * 60)
    print(f"NOTEBOOKLM_MASTER_TOKEN_JSON = '''{payload}'''")
    print("=" * 60)
    print("⚠️ เป็น credential ของทั้งบัญชี Google — ใช้บัญชีเฉพาะกิจ ไม่ผูกกับงานอื่น")
    print("   ถ้าสงสัยว่ารั่ว: Google Account → Security → Your devices → ลบอุปกรณ์")
    return 0


if __name__ == "__main__":
    sys.exit(main())
