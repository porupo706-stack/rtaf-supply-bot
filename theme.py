"""
theme.py — หน้าตาของเว็บ (โทนฟ้าน้ำเงินกองทัพอากาศ + เส้นทอง)
ไม่พึ่ง streamlit จึงทดสอบแยกได้ ไม่ใช้ตราสัญลักษณ์ทางการ (ใช้ไอคอนทั่วไปเท่านั้น)
"""

import base64
from pathlib import Path

LOGO_PATH = Path(__file__).parent / "assets" / "logo.png"
PHOTO_PATH = Path(__file__).parent / "assets" / "hero-photo.jpg"

NAVY = "#0A2A5E"
BLUE = "#1F5FBF"
SKY = "#E1EAF7"
GOLD = "#C9A227"
SLATE = "#2C3E50"    
SLATE_LT = "#4D7494"

THEME_CSS = f"""
<style>
/* ---------- พื้นหลัง/ระยะห่าง ---------- */
.stApp {{ background: linear-gradient(180deg,#EAF1FB 0%,#F7F9FD 38%,#F3F6FB 100%); }}
.block-container {{ padding-top: 1.2rem; max-width: 820px; }}
header[data-testid="stHeader"] {{ background: transparent; }}

/* ---------- แบนเนอร์หัวเว็บ ---------- */
.hero {{
  position: relative; overflow: hidden; margin: .2rem 0 1.2rem 0;
  padding: 1.5rem 1.6rem 1.4rem 1.6rem; border-radius: 1rem; color: #fff;
  background-color: {SLATE}; 
  box-shadow: 0 10px 26px rgba(10,42,94,.28);
}}

/* ใช้ transform เพื่อซูมภาพพื้นหลัง (ชดเชยขอบขาวที่ติดมากับรูป) แล้วปรับตำแหน่งเครื่องบินให้ขยับลงและเข้าในกรอบ */
.hero-bg {{
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  z-index: 0;
  /* ซูมภาพ 120% (เพื่อดันขอบขาวออก) และเลื่อนภาพลง + ไปทางซ้ายนิดหน่อย เพื่อดึงเครื่องบินกลับมาให้เห็นทั้งลำ */
  transform: scale(1.2) translate(-3%, 8%); 
}}

.hero .hero-top {{ display:flex; align-items:center; gap:.85rem; position:relative; z-index:1; }}
.hero .hero-icon {{
  width: 3.6rem; height: 3.6rem; flex: 0 0 auto; display:flex; align-items:center; justify-content:center;
  font-size: 1.7rem; border-radius: 50%; background: rgba(255,255,255,.14);
  border: 2px solid {GOLD};
  box-shadow: 0 2px 6px rgba(0,0,0,0.3);
}}
.hero .hero-icon.has-logo {{ border-radius: .85rem; overflow: hidden; padding: 0; background: none; }}
.hero .hero-icon img {{ width: 100%; height: 100%; display:block; object-fit: cover; }}

/* Text-shadow เพื่อให้อ่านตัวหนังสือสีขาวบนพื้นฟ้าสว่างได้ชัดเจน */
.hero h1 {{ 
  margin:0; padding:0; font-size: 1.45rem; line-height:1.35; 
  font-weight:800; color:#fff; letter-spacing:.2px; 
  text-shadow: 1px 2px 5px rgba(0,0,0,0.65); 
}}
.hero .hero-sub {{ 
  margin:.25rem 0 0 0; font-size:.95rem; color:#fff; 
  text-shadow: 1px 2px 4px rgba(0,0,0,0.65); 
}}
.hero .hero-tags {{ margin-top:.9rem; display:flex; flex-wrap:wrap; gap:.4rem; position:relative; z-index:1; }}
.hero .hero-tags span {{
  font-size:.78rem; padding:.18rem .65rem; border-radius:1rem;
  background: rgba(10,42,94,.4); border:1px solid rgba(201,162,39,.65); color:#FFF4CC;
  text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
}}

/* ---------- ช่องพิมพ์คำถาม ---------- */
div[data-testid="stChatInput"] {{
  border: 2px solid {BLUE} !important; border-radius: .9rem !important;
  background: #fff !important; box-shadow: 0 4px 14px rgba(31,95,191,.15);
}}
div[data-testid="stChatInput"]:focus-within,
div[data-testid="stChatInput"] > div:focus-within {{
  border-color: {GOLD} !important; box-shadow: 0 0 0 3px rgba(201,162,39,.30) !important;
}}
div[data-testid="stChatInput"] button {{ background: {NAVY} !important; color:#fff !important; border-radius:.6rem !important; }}

/* ---------- ฟองข้อความ ---------- */
div[data-testid="stChatMessage"] {{
  background: #fff; border: 1px solid #D6E1F2; border-radius: .9rem;
  padding: .85rem 1rem; margin-bottom: .7rem; box-shadow: 0 2px 8px rgba(10,42,94,.06);
}}
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {{
  background: #EAF2FF; border-color: #BFD3F2; border-left: 4px solid {BLUE};
}}
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {{
  border-left: 4px solid {GOLD};
}}

[data-testid="stChatMessageAvatarUser"] {{ background: {BLUE} !important; }}
[data-testid="stChatMessageAvatarAssistant"] {{ background: {NAVY} !important; }}

/* ---------- ปุ่ม ---------- */
.stButton > button, .stDownloadButton > button {{
  border-radius: .6rem; border: 1px solid {BLUE}; color: {NAVY}; background:#fff; font-weight:600;
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
  background: {NAVY}; color:#fff; border-color:{NAVY};
}}
.stButton > button[kind="primary"] {{ background: {BLUE}; color:#fff; border-color:{BLUE}; }}
.stButton > button[kind="primary"]:hover {{ background:{NAVY}; border-color:{NAVY}; }}

/* ---------- แถบข้าง ---------- */
section[data-testid="stSidebar"] {{
  background: linear-gradient(180deg,#D7E5F8 0%,#E8F0FB 100%);
  border-right: 3px solid {GOLD};
}}
section[data-testid="stSidebar"] label[data-baseweb="radio"] {{
  padding: .45rem .6rem; border-radius: .6rem; margin-bottom: .2rem;
}}
section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) {{
  background: {NAVY}; }}
section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) * {{ color:#fff !important; }}

/* ---------- หัวข้อ/การ์ด/ลิงก์ ---------- */
h2, h3 {{ color: {NAVY}; }}
div[data-testid="stExpander"] {{ background:#fff; border:1px solid #D6E1F2; border-radius:.8rem; }}
.src-card {{ border-left-color: {GOLD} !important; background: rgba(201,162,39,.09) !important; }}
.cite-n {{ background:#E1EAF7; color:{NAVY}; border-color:#B7CBEB; }}
.cite-n:hover {{ background:{GOLD}; color:#fff; border-color:{GOLD}; }}
</style>
"""

def _logo_html() -> str:
    """โลโก้ที่ผู้ดูแลวางไว้ที่ assets/logo.png (ฝังในหน้าเว็บ) ถ้าไม่มีไฟล์ใช้ไอคอนเครื่องบินแทน"""
    try:
        b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode()
        return f'<div class="hero-icon has-logo"><img alt="โลโก้" src="data:image/png;base64,{b64}"></div>'
    except OSError:
        return '<div class="hero-icon">✈️</div>'


def _photo_style() -> str:
    """ภาพถ่ายเครื่องบินจริงเป็นพื้นหลัง header (assets/hero-photo.jpg) ถ้าไม่มีไฟล์ใช้พื้นสีเรียบแทน"""
    try:
        b64 = base64.b64encode(PHOTO_PATH.read_bytes()).decode()
        return (f"background-image:url(data:image/jpeg;base64,{b64});"
                "background-size: cover;"
                "background-position: center;"
                "background-repeat: no-repeat;")
    except OSError:
        return ""


HERO_HTML = """
<div class="hero">
  <!-- เลเยอร์พื้นหลัง -->
  <div class="hero-bg" style="__PHOTO__"></div>
  
  <div class="hero-top">
    __LOGO__
    <div>
      <h1>ผู้ช่วยงานพัสดุ ของกองทัพอากาศ (ทอ.)</h1>
      <p class="hero-sub">ถาม–ตอบระเบียบและเอกสารงานพัสดุ พร้อมอ้างอิงแหล่งที่มา</p>
    </div>
  </div>
  
  <!-- บรรทัดแรก: ป้ายแท็ก -->
  <div class="hero-tags">
    <span>📘 ระเบียบ/ข้อบังคับ</span><span>🔎 ค้นหาเร็ว</span><span>📌 อ้างอิงต้นฉบับ</span>
  </div>

  <!-- บรรทัดที่สอง: ชื่อผู้จัดทำ (บังคับขึ้นบรรทัดใหม่) -->
  <div class="hero-tags" style="margin-top: 0.4rem;">
    <span>ออกแบบโดย พ.อ.อ.กนก คงสีทอง</span>
  </div>
</div>
"""
HERO_HTML = HERO_HTML.replace("__LOGO__", _logo_html()).replace("__PHOTO__", _photo_style())
