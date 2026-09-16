# ระบบผู้ช่วยงานพัสดุ กองทัพอากาศ (RTAF Supply Bot)

> แชทบอทตอบคำถามด้านงานพัสดุ สืบค้นระเบียบการจัดซื้อ และบริหารคลังพัสดุ  
> ขับเคลื่อนด้วย NotebookLM AI — เข้าถึงได้ผ่าน URL ทันที ไม่ต้องติดตั้งในเครื่อง

**URL:** https://rtaf-supply.streamlit.app  
**จัดทำโดย:** พ.อ.อ.กนก คงสีทอง

---

## ภาพรวมระบบ

ระบบนี้ใช้ **NotebookLM** เป็น AI ตอบคำถาม ทำงานบน **Streamlit Cloud** โดยมี **GitHub Actions** คอยรักษา session ให้อัตโนมัติทุก 5 นาที ผู้ใช้ทุกคนเข้าถึงได้ผ่าน URL โดยไม่ต้องติดตั้งโปรแกรมใดในเครื่อง

```
GitHub Actions (Cloud)
    ↓ ทุก 5 นาที
cloud_keepalive.py
    ├── ดึง session จาก GitHub Gist (เข้ารหัส)
    ├── Ping NotebookLM → ต่ออายุ Google session
    └── อัปโหลด session ที่อัปเดตกลับ Gist
            ↓
    Streamlit Cloud ดึง session จาก Gist
            ↓
    ผู้ใช้เข้าถึงได้ 24/7 ✅
```

---

## คุณสมบัติหลัก

- 🤖 **AI ตอบคำถาม** — สืบค้นระเบียบการจัดซื้อจัดจ้างด้วยภาษาธรรมชาติ
- ☁️ **ทำงาน 24/7 บน Cloud** — ไม่ต้องเปิดเครื่องคอมพิวเตอร์ทิ้งไว้
- 🔄 **Keep-Alive อัตโนมัติ** — GitHub Actions รักษา session ทุก 5 นาที
- 🔒 **ความปลอดภัยสูง** — ไม่มีข้อมูลสำคัญใดอยู่ใน source code เลย
- 🆓 **ไม่มีค่าใช้จ่าย** — ใช้ GitHub Actions (Public repo) และ Streamlit Cloud ฟรี

---

## สถาปัตยกรรมความปลอดภัย

ระบบปฏิบัติตามมาตรฐาน **Zero-Secrets in Source Code** อย่างเคร่งครัด:

| ข้อมูล | เก็บที่ | ใครเห็นได้ |
|---|---|---|
| `NOTEBOOK_ID` | Streamlit Secrets | ผู้ดูแลระบบ |
| `GIST_ID` | Streamlit Secrets | ผู้ดูแลระบบ |
| `GITHUB_TOKEN` | Streamlit Secrets | ผู้ดูแลระบบ |
| `SESSION_ENC_KEY` | Streamlit + Actions Secrets | ผู้ดูแลระบบ |
| Google Session | GitHub Gist (เข้ารหัส AES) | ผู้ดูแลระบบ |
| Source code (`app.py`) | GitHub (Public) | ทุกคน ✅ ปลอดภัย |

> **`app.py` และ `cloud_keepalive.py` ไม่มีข้อมูลสำคัญอยู่เลย** — ปลอดภัยในการเปิดเผยสาธารณะ

---

## โครงสร้างไฟล์

```
rtaf-supply-bot/
├── app.py                          # โค้ดหลัก Streamlit Cloud
├── cloud_keepalive.py              # Keep-Alive script (รันบน GitHub Actions)
├── generate_key.py                 # สร้าง encryption key (รันครั้งเดียว)
├── refresh_session.py              # Login Google + อัปโหลด session → Gist
├── refresh_session.bat             # เปิด refresh_session.py ด้วย 1 คลิก
├── requirements.txt                # Python packages
├── .gitignore                      # ป้องกันไฟล์สำคัญหลุด GitHub
└── .github/
    └── workflows/
        └── keepalive.yml           # ตั้งเวลารัน Actions ทุก 5 นาที
```

---

## สิ่งที่ต้องมีก่อนติดตั้ง

- Python 3.10+ (ใช้ login ครั้งแรกเท่านั้น)
- บัญชี GitHub
- บัญชี Streamlit Cloud
- บัญชี Google ที่มีสิทธิ์เข้า NotebookLM
- NotebookLM Notebook ที่อัปโหลดเอกสารพัสดุไว้แล้ว

---

## ขั้นตอนติดตั้ง (ภาพรวม)

1. **Login Google ครั้งแรก** — รัน `python -m notebooklm login` ในเครื่อง
2. **สร้าง GitHub Gist** — สำหรับเก็บ session เข้ารหัส (ต้องเป็น Secret Gist)
3. **สร้าง GitHub Personal Access Token** — สิทธิ์แค่ `gist` เท่านั้น
4. **สร้าง Encryption Key** — รัน `python generate_key.py`
5. **ตั้งค่า Streamlit Secrets** — ใส่ค่าทั้ง 4 ตัวใน App settings
6. **ตั้งค่า GitHub Actions Secrets** — ใส่ค่าทั้ง 4 ตัวใน Repository settings
7. **รัน `refresh_session.bat`** — อัปโหลด session ขึ้น Gist ครั้งแรก
8. **ทดสอบ GitHub Actions** — กด Run workflow แล้วรอดู ✅

---

## การบำรุงรักษา

| สถานการณ์ | สิ่งที่ต้องทำ |
|---|---|
| ปิด/เปิดเครื่องใหม่ | ไม่ต้องทำอะไร |
| แอปขึ้น "Session หมดอายุ" | Double-click `refresh_session.bat` |
| GitHub Actions แสดง ❌ | ตรวจสอบ Actions tab → คลิกดู log |
| Token หมดอายุ | สร้าง token ใหม่ → อัปเดต Secrets |

---

## License

ระบบนี้พัฒนาเพื่อใช้งานภายในกองทัพอากาศไทย (ทอ.) เท่านั้น
