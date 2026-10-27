# ระบบผู้ช่วยงานพัสดุ กองทัพอากาศ (RTAF Supply Bot)

> แชทบอทตอบคำถามด้านงานพัสดุ สืบค้นระเบียบการจัดซื้อ และบริหารคลังพัสดุ  
> เข้าถึงได้ผ่าน URL ทันที ไม่ต้องติดตั้งในเครื่อง

**URL:** https://rtaf-supply.streamlit.app  
**จัดทำโดย:** พ.อ.อ.กนก คงสีทอง

---

## ภาพรวมระบบ

เว็บแอป **Streamlit** ที่เป็นหน้าบ้านของ Notebook ใน Google NotebookLM (ปัจจุบันเรียก Gemini Notebook)
ผู้ใช้ถามคำถามเป็นภาษาไทย ระบบส่งคำถามไปให้ NotebookLM ตอบจากเอกสารระเบียบที่อัปโหลดไว้
แล้วแสดงคำตอบพร้อมเลขอ้างอิงที่กดดูต้นฉบับได้ โดยเชื่อมต่อผ่านไลบรารี
[notebooklm-py](https://github.com/teng-lin/notebooklm-py) (ไม่เป็นทางการ)

```
ผู้ใช้ ──► Streamlit Cloud (app.py)
              │
              ├─ features.py / citations.py ──► notebooklm-py ──► NotebookLM (เอกสารระเบียบ)
              │
              └─ auth_setup.py ──► master token (Secrets)
                                     └─► mint cookie Google ใหม่เองเมื่อ session หมดอายุ
```

เมื่อตั้งค่า **master token** แล้ว ไลบรารีจะสร้าง session Google ใหม่ให้เองทุกครั้งที่หมดอายุ
ไม่ต้องล็อกอินซ้ำ ไม่ต้องรีเฟรชด้วยมือ

---

## คุณสมบัติ

แอปมี 3 หน้า (เมนูแถบซ้าย)

### 💬 ถาม–ตอบ
- ถามเป็นภาษาไทย ได้คำตอบพร้อม **เลขอ้างอิง** กดหรือชี้ดูชื่อไฟล์ต้นฉบับและข้อความที่อ้างอิง (ไฮไลต์ในบริบทรอบข้าง)
- รายการ **แหล่งข้อมูลอ้างอิง** ใต้คำตอบ ใช้ได้บนมือถือ
- **คำถามต่อเนื่อง** — ปุ่มคำถามถัดไปที่ NotebookLM แนะนำหลังตอบ
- บทสนทนาต่อเนื่องและ **แยกรายผู้ใช้** (ไม่ปนกับคนอื่น)
- **ส่งออกบทสนทนา** เป็นไฟล์ Markdown พร้อมแหล่งอ้างอิง และปุ่ม **เริ่มบทสนทนาใหม่**

### 📚 แหล่งข้อมูล
- รายการไฟล์ทั้งหมดในฐานความรู้ พร้อมชนิดไฟล์และจำนวนคำ
- **สรุป + คำสำคัญ** ของแต่ละไฟล์ ตอบเป็นภาษาเดียวกับเอกสารต้นฉบับ
- **ดูเนื้อหาเต็ม** ของไฟล์
- ผู้ดูแล: เพิ่มไฟล์ (PDF, Word, ข้อความ, Markdown, EPUB, เสียง, รูปภาพ), ลิงก์/YouTube, วางข้อความ และลบแหล่งข้อมูล (มีขั้นยืนยัน)

### 🎨 สื่อสรุป (Studio)
สร้างและดาวน์โหลดสื่อจากแหล่งข้อมูลชุดเดียวกัน

| ชนิด | ไฟล์ที่ดาวน์โหลด |
|---|---|
| พอดแคสต์ (Deep Dive / Brief / Critique / Debate) | เสียง (มีตัวเล่นในหน้า) |
| รายงาน / คู่มือสรุป / บทความ | Markdown |
| สไลด์นำเสนอ | PDF หรือ PPTX |
| แบบทดสอบ, แฟลชการ์ด | JSON, Markdown, HTML |
| แผนผังความคิด (Mind Map) | JSON (แสดงเป็นรายการซ้อนชั้นในหน้า) |
| ตารางข้อมูล | CSV |
| อินโฟกราฟิก | PNG (แสดงตัวอย่างในหน้า) |

ผู้ใช้ทั่วไปดาวน์โหลดสื่อที่มีอยู่ได้ ส่วนการ **สร้างใหม่** สำหรับผู้ดูแล (ใช้โควตา)

---

## สิทธิ์การใช้งาน

แอปใช้บัญชี Google **บัญชีเดียวร่วมกัน** จึงแบ่งสิทธิ์เพื่อไม่ให้ฐานความรู้ถูกแก้ไขหรือโควตาหมด

| ผู้ใช้ทั่วไป | ผู้ดูแล (ใส่ `ADMIN_PASSWORD` ที่แถบซ้าย → 🔐 ผู้ดูแลระบบ) |
|---|---|
| ถาม–ตอบ, ส่งออกบทสนทนา, ดูสรุป/เนื้อหาไฟล์, ดาวน์โหลดสื่อที่มีอยู่ | เพิ่ม/ลบแหล่งข้อมูล, สร้างสื่อใหม่, บันทึกบทสนทนาเป็นโน้ตใน Notebook, ตรวจโควตา |

- ถ้าไม่ตั้ง `ADMIN_PASSWORD` ฟังก์ชันผู้ดูแลจะ **ปิดทั้งหมด**
- จำกัดการใส่รหัสผิด 5 ครั้งต่อ session (นับใหม่เมื่อรีเฟรชหน้า) จึงต้องตั้งรหัสให้ยาวและเดายาก

---

## การติดตั้ง

### 1) Secrets ที่ต้องมี (Streamlit → App settings → Secrets)

| ตัวแปร | จำเป็น | ความหมาย |
|---|---|---|
| `NOTEBOOK_ID` | ✅ | รหัส Notebook (ส่วนหลัง `/notebook/` ใน URL ของ NotebookLM) |
| `NOTEBOOKLM_MASTER_TOKEN_JSON` | ✅ แนะนำ | ค่าจาก `export_master_token.py` ทำให้ session ต่ออายุเอง |
| `ADMIN_PASSWORD` | แนะนำ | รหัสผู้ดูแล (ถ้าไม่ตั้ง ฟังก์ชันผู้ดูแลถูกปิด) |
| `GIST_ID`, `GITHUB_TOKEN`, `SESSION_ENC_KEY` | ทางเลือก (ระบบเดิม) | ใช้ดึง session จาก Gist เป็นตัวสำรอง ดู [ระบบเดิม](#ระบบเดิม-gist--keep-alive) |

รูปแบบ TOML:

```toml
NOTEBOOK_ID = "รหัส notebook"
ADMIN_PASSWORD = "รหัสผ่านยาว ๆ ที่เดายาก"
NOTEBOOKLM_MASTER_TOKEN_JSON = '''{"version": 1, "email": "...", "android_id": "...", "master_token": "..."}'''
```

### 2) ออก master token (ทำครั้งเดียว บนคอมพิวเตอร์ที่มี browser)

ใช้บัญชี Google **เฉพาะกิจ** และแชร์ Notebook ให้บัญชีนั้น (ถ้าไม่ใช่เจ้าของ)

```bash
pip install "notebooklm-py[browser,headless]"
python -m notebooklm login --master-token --account อีเมลบัญชีเฉพาะกิจ@gmail.com
python export_master_token.py
```

`export_master_token.py` จะพิมพ์บรรทัด `NOTEBOOKLM_MASTER_TOKEN_JSON = '''...'''` ให้คัดลอกไปวางใน Secrets แล้วกด **Save changes** และ **Reboot app**

**ถ้า browser ที่สคริปต์เปิดถูกปิดเอง** (ขึ้น `Target page, context or browser has been closed`)
ให้เปิด Chrome ปกติแล้วให้สคริปต์เชื่อมเข้าไป (Windows PowerShell):

```powershell
Start-Process "C:\Program Files\Google\Chrome\Application\chrome.exe" -ArgumentList "--remote-debugging-port=9222","--user-data-dir=$env:TEMP\chrome-rtaf"
python -m notebooklm login --master-token --account อีเมล@gmail.com --cdp-url http://localhost:9222
```

ล็อกอินและกด **I agree** ในหน้าต่าง Chrome นั้น สคริปต์จะจับ token และแลกให้เอง
เสร็จแล้วลบโปรไฟล์ชั่วคราว: `Remove-Item -Recurse -Force "$env:TEMP\chrome-rtaf"`

> การคัดลอกคุกกี้ `oauth_token` ด้วยมือแล้วใช้ `--oauth-token` ก็ทำได้ แต่ token ใช้ได้ครั้งเดียวและหมดอายุเร็วมาก พลาดง่าย

### 3) ทดสอบ
เปิดแอปแล้วถามคำถาม 1 ข้อ ถ้าตอบได้และไม่มีคำเตือนสีเหลือง แปลว่าเข้าโหมด master token แล้ว
คำเตือน *"ตั้งค่า master token ไม่สำเร็จ — ใช้ session สำรองแทน"* แปลว่าค่าที่วางยังไม่ถูกต้อง

### ลำดับการยืนยันตัวตนของแอป
1. `NOTEBOOKLM_MASTER_TOKEN_JSON` (mint cookie เอง) → 2. session จาก Gist → 3. `NOTEBOOKLM_AUTH_JSON`

เมื่อใช้ master token แอปจะไม่ใช้ `NOTEBOOKLM_AUTH_JSON` เพราะโหมดนั้นปิดการ mint ใหม่

---

## ความปลอดภัย

| เรื่อง | รายละเอียด |
|---|---|
| ค่าลับ | เก็บใน Streamlit Secrets เท่านั้น **ห้าม commit** (`master_token.json` และ `storage_state.json` อยู่ใน `.gitignore`) |
| master token | เป็น credential ของ **ทั้งบัญชี Google** ไม่หมดอายุเอง และเปลี่ยนรหัสผ่านก็ไม่ทำให้ใช้ไม่ได้ |
| บัญชี | ใช้บัญชีเฉพาะกิจ ไม่ผูกกับงานอื่น แชร์ Notebook ให้บัญชีนั้นเท่านั้น |
| ถ้าสงสัยว่ารั่ว | Google Account → Security → Your devices → ลบอุปกรณ์ที่ไม่รู้จัก แล้วออก token ใหม่ |
| ภาพหน้าจอ/แชท | อย่าส่งหรือแคปหน้าจอที่มีค่า token, รหัสผ่าน หรือ Secrets |
| รหัสผู้ดูแล | ตั้งให้ยาวและเดายาก เพราะแอปเปิดสาธารณะ |

---

## โครงสร้างไฟล์

```
rtaf-supply-bot/
├── app.py                    # หน้าเว็บ Streamlit (ถาม–ตอบ / แหล่งข้อมูล / สื่อสรุป)
├── features.py               # ฟังก์ชันเรียก notebooklm-py (ไม่พึ่ง streamlit ทดสอบแยกได้)
├── citations.py              # เลขอ้างอิง + การ์ดแหล่งข้อมูล
├── auth_setup.py             # ติดตั้ง master token ให้ notebooklm-py
├── export_master_token.py    # รันบนเครื่องผู้ดูแล: พิมพ์ค่าที่ต้องวางใน Secrets
├── requirements.txt          # streamlit, notebooklm-py[headless], requests, cryptography
├── tests/                    # ทดสอบฟังก์ชันที่ไม่ต้องใช้เครือข่าย
└── (ระบบเดิม) cloud_keepalive.py, generate_key.py, refresh_session.py/.bat, .github/workflows/keepalive.yml
```

รันทดสอบ: `python tests/test_features.py` และ `python tests/test_auth_setup.py`

---

## การบำรุงรักษา / แก้ปัญหา

| สถานการณ์ | สาเหตุ / สิ่งที่ต้องทำ |
|---|---|
| หน้า **"Zzzz แอปหลับ"** | Streamlit ฟรีพักแอปเมื่อไม่มีคนเข้านาน ไม่ใช่บั๊ก กดปุ่ม *Yes, get this app back up!* รอประมาณ 1 นาที |
| หน้า **"Session Google หมดอายุ"** (โหมด master token) | token ถูกเพิกถอนหรือใช้ไม่ได้ ออก token ใหม่ตามขั้นตอนด้านบน วางทับ Secret แล้ว Reboot app |
| ขึ้น "ไม่พบ NOTEBOOK_ID" | ไม่มี `NOTEBOOK_ID` ใน Secrets |
| ฟังก์ชันผู้ดูแลไม่ขึ้น | ยังไม่ได้ตั้ง `ADMIN_PASSWORD` หรือยังไม่ได้เข้าสู่ระบบที่แถบซ้าย |
| สร้างสื่อไม่สำเร็จ | โควตาหมดหรือเกินลิมิตของบัญชี ตรวจที่แถบซ้าย → 📊 โควตาการใช้งาน (ผู้ดูแล) |
| พอดแคสต์/วิดีโอใช้เวลานาน | ปกติ ใช้เวลาหลายนาที |

### ข้อจำกัด
- **notebooklm-py ไม่เป็นทางการ** ใช้ API ภายในของ Google ที่อาจเปลี่ยนโดยไม่แจ้ง ถ้า Google เปลี่ยนระบบ แอปอาจใช้ไม่ได้ชั่วคราว
- มีลิมิตจำนวนแหล่งข้อมูลและโควตาการสร้างสื่อตามระดับบัญชี Google
- ใช้บัญชีเดียวร่วมกัน ผู้ใช้หลายคนพร้อมกันใช้โควตาร่วมกัน

---

## ระบบเดิม (Gist + Keep-Alive)

ก่อนใช้ master token ระบบรักษา session ด้วย GitHub Actions ที่ ping NotebookLM ทุก 5 นาที
และเก็บ session เข้ารหัส (Fernet) ไว้ที่ GitHub Gist แล้วให้แอปดึงไปใช้
ไฟล์ที่เกี่ยวข้อง: `cloud_keepalive.py`, `.github/workflows/keepalive.yml`, `refresh_session.py/.bat`, `generate_key.py`

ตอนนี้ยังเก็บไว้เป็น **ตัวสำรอง** เมื่อยืนยันว่า master token ใช้งานได้นิ่งแล้ว
สามารถปิด/ลบส่วนนี้ได้ (รวมถึงเพิกถอน `GITHUB_TOKEN` และลบ Gist) เพื่อลดความเสี่ยงและไม่ให้ Actions กินโควตาเปล่า ๆ

---

## License

ระบบนี้พัฒนาเพื่อใช้งานภายในกองทัพอากาศไทย (ทอ.) เท่านั้น
