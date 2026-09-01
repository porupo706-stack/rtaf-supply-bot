"""
รันครั้งเดียวเพื่อสร้าง Encryption Key
จากนั้นเอา key ที่ได้ไปใส่ใน:
  1. refresh_session.py  → ช่อง ENCRYPTION_KEY
  2. Streamlit Cloud Secrets → SESSION_ENC_KEY = "..."
"""

from cryptography.fernet import Fernet

key = Fernet.generate_key().decode()

print("=" * 60)
print("✅ Encryption Key ของคุณ (เก็บไว้ให้ดี อย่าให้ใครรู้!):")
print()
print(key)
print()
print("=" * 60)
print()
print("วิธีใช้:")
print("  1. คัดลอก key ข้างบน")
print("  2. ใส่ใน refresh_session.py → ENCRYPTION_KEY = '...'")
print("  3. ใส่ใน Streamlit Cloud Secrets:")
print('     SESSION_ENC_KEY = "..."')
print()

input("กด Enter เพื่อปิด...")
