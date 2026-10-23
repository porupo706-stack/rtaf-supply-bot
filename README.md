# ระบบผู้ช่วยงานพัสดุ กองทัพอากาศ (RTAF Supply Bot)

> แชทบอทตอบคำถามด้านงานพัสดุ สืบค้นระเบียบการจัดซื้อ และบริหารคลังพัสดุ  
> เข้าถึงได้ผ่าน URL ทันที ไม่ต้องติดตั้งในเครื่อง

**URL:** https://rtaf-supply.streamlit.app  
**จัดทำโดย:** พ.อ.อ.กนก คงสีทอง

---

## ภาพรวมระบบ

ระบบนี้ ทำงานบน **Streamlit Cloud** โดยมี **GitHub Actions** คอยรักษา session ให้อัตโนมัติ ผู้ใช้ทุกคนเข้าถึงได้ผ่าน URL โดยไม่ต้องติดตั้งโปรแกรมใดในเครื่อง

```
GitHub Actions (Cloud)
    ↓ 
cloud_keepalive.py
    ├── ดึง session จาก GitHub Gist (เข้ารหัส)
    └── อัปโหลด session ที่อัปเดตกลับ Gist
            ↓
    Streamlit Cloud ดึง session จาก Gist
            ↓
    ผู้ใช้เข้าถึงได้ 24/7 ✅
```

---

## คุณสมบัติหลัก

- 🤖 **AI ตอบคำถาม** — สืบค้นระเบียบการจัดซื้อจัดจ้างด้วยภาษาธรรมชาติ พร้อมเลขอ้างอิงที่กดดูต้นฉบับได้
- 💡 **คำถามแนะนำ + คำถามต่อเนื่อง** — สร้างจากแหล่งข้อมูลจริง กดถามได้ทันที
- 🧵 **บทสนทนาแยกรายผู้ใช้** — ถามต่อเนื่องได้ ไม่ปนกับคนอื่น และส่งออกเป็น Markdown ได้
- 📚 **หน้าแหล่งข้อมูล** — ดูสรุป/คำสำคัญ/เนื้อหาเต็มของแต่ละไฟล์ (ผู้ดูแลเพิ่ม-ลบไฟล์ ลิงก์ ข้อความได้)
- 🎨 **สื่อสรุป (Studio)** — พอดแคสต์, รายงาน, สไลด์ (PDF/PPTX), แบบทดสอบ, แฟลชการ์ด, Mind Map, ตารางข้อมูล (CSV), อินโฟกราฟิก
- ☁️ **ทำงาน 24/7 บน Cloud** — ไม่ต้องเปิดเครื่องคอมพิวเตอร์ทิ้งไว้
- 🔄 **Keep-Alive อัตโนมัติ** — GitHub Actions รักษา session
- 🔒 **ความปลอดภัยสูง** — ไม่มีข้อมูลสำคัญใดอยู่ใน source code เลย
- 🆓 **ไม่มีค่าใช้จ่าย** — ใช้ GitHub Actions (Public repo) และ Streamlit Cloud ฟรี

---

## สถาปัตยกรรมความปลอดภัย

ระบบปฏิบัติตามมาตรฐาน **Zero-Secrets in Source Code** อย่างเคร่งครัด:

| ข้อมูล | เก็บที่ | ใครเห็นได้ |
|---|---|---|
| `GIST_ID` | Streamlit Secrets | ผู้ดูแลระบบ |
| `GITHUB_TOKEN` | Streamlit Secrets | ผู้ดูแลระบบ |
| `SESSION_ENC_KEY` | Streamlit + Actions Secrets | ผู้ดูแลระบบ |
| `ADMIN_PASSWORD` | Streamlit Secrets | ผู้ดูแลระบบ |
| Google Session | GitHub Gist (เข้ารหัส AES) | ผู้ดูแลระบบ |
| Source code (`app.py`) | GitHub (Public) | ทุกคน ✅ ปลอดภัย |

### สิทธิ์การใช้งาน

| ผู้ใช้ทั่วไป | ผู้ดูแล (ใส่ `ADMIN_PASSWORD`) |
|---|---|
| ถาม–ตอบ, ส่งออกบทสนทนา, ดูสรุป/เนื้อหาไฟล์, ดาวน์โหลดสื่อที่มีอยู่ | เพิ่ม/ลบแหล่งข้อมูล, สร้างสื่อใหม่, บันทึกบทสนทนาเป็นโน้ต, ดูโควตา |

> ถ้าไม่ตั้ง `ADMIN_PASSWORD` ฟังก์ชันของผู้ดูแลจะถูกปิดทั้งหมด (ค่าเริ่มต้นที่ปลอดภัย)  
> แอปนี้ใช้บัญชี Google เดียวร่วมกัน จึงจำกัดการเขียน/สร้างสื่อไว้ที่ผู้ดูแลเพื่อไม่ให้โควตาหมดหรือฐานความรู้ถูกแก้ไข

---

## โครงสร้างไฟล์

```
rtaf-supply-bot/
├── app.py                          # โค้ดหลัก Streamlit Cloud (หน้าถาม–ตอบ / แหล่งข้อมูล / สื่อสรุป)
├── features.py                     # ฟังก์ชันเรียก notebooklm-py (ไม่พึ่ง streamlit)
├── citations.py                    # เลขอ้างอิง + การ์ดแหล่งข้อมูล
├── tests/test_features.py          # ทดสอบฟังก์ชันที่ไม่ต้องใช้เครือข่าย
├── cloud_keepalive.py              # Keep-Alive script (รันบน GitHub Actions)
├── generate_key.py                 # สร้าง encryption key (รันครั้งเดียว)
├── refresh_session.py              # Login Google + อัปโหลด session → Gist
├── refresh_session.bat             # เปิด refresh_session.py ด้วย 1 คลิก
├── requirements.txt                # Python packages
├── .gitignore                      # ป้องกันไฟล์สำคัญหลุด GitHub
└── .github/
    └── workflows/
        └── keepalive.yml           # ตั้งเวลารัน Actions
```

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
