# ════════════════════════════════════════════════════════════════════
#  RTAF Supply Bot — app.py
#  ผู้ช่วยงานพัสดุ กองทัพอากาศ (ทอ.)
#  จัดทำโดย พ.อ.อ.กนก คงสีทอง
#
#  เวอร์ชันนี้ใช้ Google Gemini API แทน notebooklm-py
#  ✅ ไม่มีปัญหา session หลุด
#  ✅ รองรับผู้ใช้หลายคนพร้อมกัน
#  ✅ Deploy บน Streamlit Cloud ได้เต็มที่
# ════════════════════════════════════════════════════════════════════

import streamlit as st
import google.generativeai as genai
import os
import glob
import time
from pathlib import Path

# ────────────────────────────────────────────────
# 0. Page config (ต้องเป็น call แรกสุด)
# ────────────────────────────────────────────────
st.set_page_config(
    page_title="ผู้ช่วยงานพัสดุ ทอ.",
    page_icon="✈️",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ────────────────────────────────────────────────
# 1. Custom CSS — รักษาหน้าตาเดิมของ app
# ────────────────────────────────────────────────
st.markdown("""
<style>
    /* Header */
    .main-header {
        background: linear-gradient(135deg, #1a237e 0%, #283593 50%, #1565c0 100%);
        color: white;
        padding: 1.2rem 1.5rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        text-align: center;
        box-shadow: 0 4px 15px rgba(26,35,126,0.3);
    }
    .main-header h1 { font-size: 1.6rem; margin: 0; font-weight: 700; }
    .main-header p  { font-size: 0.85rem; margin: 0.3rem 0 0; opacity: 0.85; }

    /* Chat messages */
    .stChatMessage { border-radius: 10px; }

    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #f0f4ff; }

    /* Status badge */
    .status-ok  { color: #2e7d32; font-weight: 600; }
    .status-err { color: #c62828; font-weight: 600; }

    /* Quick question buttons */
    .stButton button {
        border-radius: 20px;
        border: 1px solid #3f51b5;
        color: #3f51b5;
        background: white;
        font-size: 0.82rem;
        padding: 0.3rem 0.8rem;
        transition: all 0.2s;
    }
    .stButton button:hover {
        background: #3f51b5;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────
# 2. ตั้งค่า Gemini API Key
#    — อ่านจาก Streamlit Secrets (deploy) หรือ .env (local)
# ────────────────────────────────────────────────
def get_api_key() -> str | None:
    # วิธี 1: Streamlit Secrets (ใช้ตอน deploy บน Streamlit Cloud)
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"]
    # วิธี 2: Environment variable (local dev)
    return os.environ.get("GEMINI_API_KEY")

API_KEY = get_api_key()

if not API_KEY:
    st.error("""
    ❌ ไม่พบ GEMINI_API_KEY

    **วิธีตั้งค่า:**
    - Streamlit Cloud → App settings → Secrets → เพิ่ม `GEMINI_API_KEY = "AIzaSy..."`
    - Local → สร้างไฟล์ `.streamlit/secrets.toml` แล้วใส่ `GEMINI_API_KEY = "AIzaSy..."`

    รับ API Key ฟรีได้ที่ https://aistudio.google.com
    """)
    st.stop()

genai.configure(api_key=API_KEY)

# ────────────────────────────────────────────────
# 3. โหลดไฟล์ระเบียบ ทอ. ขึ้น Gemini File API
#    — cache_resource = โหลดครั้งเดียวตลอด lifetime ของ app
#      ทุก user ใช้ file reference เดิม ไม่มีการแย่ง session
# ────────────────────────────────────────────────
REGULATIONS_DIR = Path("regulations")       # สร้างโฟลเดอร์นี้แล้วใส่ PDF ระเบียบ

@st.cache_resource(show_spinner=False)
def load_regulation_files():
    """
    Upload PDF ระเบียบทั้งหมดขึ้น Gemini File API
    Return list ของ File objects พร้อม metadata
    """
    if not REGULATIONS_DIR.exists():
        return [], []

    pdf_paths = sorted(glob.glob(str(REGULATIONS_DIR / "**/*.pdf"), recursive=True))
    if not pdf_paths:
        return [], []

    uploaded_files = []
    file_names     = []

    progress = st.progress(0, text="กำลังโหลดระเบียบ...")
    for i, path in enumerate(pdf_paths):
        try:
            f = genai.upload_file(path, mime_type="application/pdf")
            uploaded_files.append(f)
            file_names.append(Path(path).stem)
        except Exception as e:
            st.warning(f"โหลดไฟล์ไม่สำเร็จ: {Path(path).name} — {e}")
        progress.progress((i + 1) / len(pdf_paths),
                          text=f"โหลด {i+1}/{len(pdf_paths)}: {Path(path).name}")
    progress.empty()

    return uploaded_files, file_names

# ────────────────────────────────────────────────
# 4. สร้าง Gemini model พร้อม system instruction
# ────────────────────────────────────────────────
SYSTEM_PROMPT = """คุณคือผู้ช่วยงานพัสดุของกองทัพอากาศ (ทอ.) ที่มีความเชี่ยวชาญด้านระเบียบและกฎหมายพัสดุ

หน้าที่หลักของคุณ:
1. ตอบคำถามเกี่ยวกับระเบียบการจัดซื้อจัดจ้างและบริหารพัสดุภาครัฐ
2. ช่วยค้นหาข้อกำหนด วงเงิน เงื่อนไข และขั้นตอนจากระเบียบที่ให้ไว้
3. อธิบายความหมายและการปฏิบัติตามระเบียบให้เข้าใจง่าย
4. แนะนำแนวทางปฏิบัติที่ถูกต้องตามระเบียบ

กฎการตอบ:
- ตอบเป็นภาษาไทย ชัดเจน กระชับ ตรงประเด็น
- อ้างอิงข้อ/มาตราจากระเบียบที่เกี่ยวข้องเสมอเมื่อมีข้อมูล
- ถ้าไม่พบในระเบียบที่ให้ไว้ ให้บอกตรงๆ ว่า "ไม่พบข้อมูลในระเบียบที่มี"
- ไม่ตอบคำถามที่ไม่เกี่ยวกับงานพัสดุและกฎหมายที่เกี่ยวข้อง
- หากคำถามไม่ชัดเจน ให้ถามเพื่อขอรายละเอียดเพิ่มเติม"""

@st.cache_resource
def get_model():
    return genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM_PROMPT,
    )

# ────────────────────────────────────────────────
# 5. ฟังก์ชันถาม-ตอบ
# ────────────────────────────────────────────────
def ask_regulation(question: str,
                   reg_files: list,
                   chat_history: list) -> str:
    """
    ส่งคำถามไปยัง Gemini พร้อม:
    - ไฟล์ระเบียบทั้งหมด (context)
    - ประวัติการสนทนา (multi-turn)
    """
    model = get_model()

    # สร้าง messages list พร้อม file references
    # ใส่ไฟล์ระเบียบใน turn แรกเพื่อประหยัด token
    if not chat_history:
        # Turn แรก: แนบไฟล์พร้อมคำถาม
        content_parts = []
        for f in reg_files:
            content_parts.append(f)
        content_parts.append(question)
        messages = [{"role": "user", "parts": content_parts}]
    else:
        # Turn ถัดไป: ใช้ history + คำถามใหม่
        # (ไฟล์ถูก cache ใน context แล้ว)
        messages = []
        for h in chat_history:
            messages.append({"role": "user",      "parts": [h["user"]]})
            messages.append({"role": "model",     "parts": [h["assistant"]]})
        messages.append({"role": "user", "parts": [question]})

    try:
        chat = model.start_chat(history=messages[:-1])
        response = chat.send_message(messages[-1]["parts"])
        return response.text
    except Exception as e:
        return f"⚠️ เกิดข้อผิดพลาด: {str(e)}\n\nกรุณาลองถามใหม่อีกครั้ง"

# ────────────────────────────────────────────────
# 6. Sidebar
# ────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ✈️ ผู้ช่วยงานพัสดุ ทอ.")
    st.markdown("---")

    # โหลดไฟล์ระเบียบ
    with st.spinner("กำลังโหลดระเบียบ..."):
        reg_files, reg_names = load_regulation_files()

    # แสดงสถานะ
    if reg_files:
        st.markdown(f'<p class="status-ok">✅ พร้อมใช้งาน ({len(reg_files)} ไฟล์)</p>',
                    unsafe_allow_html=True)
        with st.expander("📂 ระเบียบที่โหลดแล้ว", expanded=False):
            for name in reg_names:
                st.markdown(f"• {name}")
    else:
        st.markdown('<p class="status-err">⚠️ ไม่พบไฟล์ระเบียบ</p>',
                    unsafe_allow_html=True)
        st.info("""
        **วิธีเพิ่มระเบียบ:**
        1. สร้างโฟลเดอร์ `regulations/` ใน repo
        2. ใส่ไฟล์ PDF ระเบียบ ทอ. ลงไป
        3. Push ขึ้น GitHub แล้ว deploy ใหม่
        """)

    st.markdown("---")
    st.markdown("**⚡ คำถามด่วน**")

    quick_questions = [
        "วงเงินจัดซื้อโดยวิธีเฉพาะเจาะจงสูงสุดเท่าไหร่",
        "ขั้นตอนการจัดซื้อแบบ e-bidding",
        "คณะกรรมการตรวจรับพัสดุมีหน้าที่อะไรบ้าง",
        "การจำหน่ายพัสดุชำรุดทำอย่างไร",
        "หลักเกณฑ์การยืมพัสดุ",
    ]

    for q in quick_questions:
        if st.button(q, key=f"quick_{q}", use_container_width=True):
            st.session_state["quick_input"] = q

    st.markdown("---")

    # ปุ่มล้างประวัติ
    if st.button("🗑️ ล้างประวัติการสนทนา", use_container_width=True):
        st.session_state.messages = []
        st.session_state.chat_history = []
        st.rerun()

    st.markdown("---")
    st.markdown("""
    <small>
    จัดทำโดย พ.อ.อ.กนก คงสีทอง<br>
    Powered by Google Gemini API<br>
    v2.0 — ไม่มีปัญหา session
    </small>
    """, unsafe_allow_html=True)

# ────────────────────────────────────────────────
# 7. Main Content
# ────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>✈️ ผู้ช่วยงานพัสดุ กองทัพอากาศ</h1>
    <p>ระบบสืบค้นระเบียบการจัดซื้อจัดจ้างและบริหารพัสดุ ทอ.</p>
</div>
""", unsafe_allow_html=True)

# แสดงข้อความถ้าไม่มีไฟล์ระเบียบ
if not reg_files:
    st.warning("""
    ⚠️ **ยังไม่มีไฟล์ระเบียบ**

    ระบบสามารถตอบคำถามทั่วไปได้ แต่จะตอบได้แม่นยำกว่า
    เมื่อใส่ไฟล์ PDF ระเบียบ ทอ. ไว้ในโฟลเดอร์ `regulations/`
    """)

# ────────────────────────────────────────────────
# 8. Session State
# ────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []  # เก็บ {"user":..., "assistant":...}
if "quick_input" not in st.session_state:
    st.session_state.quick_input = None

# ────────────────────────────────────────────────
# 9. แสดง welcome message ถ้ายังไม่มีข้อความ
# ────────────────────────────────────────────────
if not st.session_state.messages:
    with st.chat_message("assistant", avatar="✈️"):
        st.markdown("""
สวัสดีครับ ผมคือผู้ช่วยงานพัสดุ ทอ. พร้อมช่วยสืบค้นระเบียบและตอบคำถามเกี่ยวกับ:

- 📋 **ระเบียบการจัดซื้อจัดจ้าง** — วงเงิน วิธีการ เงื่อนไข
- 🏭 **การบริหารคลังพัสดุ** — การรับ-จ่าย การตรวจนับ การจำหน่าย
- 📝 **ขั้นตอนและแบบฟอร์ม** — เอกสารที่ต้องใช้
- ⚖️ **ข้อกฎหมายที่เกี่ยวข้อง** — พรบ. และระเบียบที่บังคับใช้

กรุณาพิมพ์คำถามได้เลยครับ 🙏
        """)

# ────────────────────────────────────────────────
# 10. แสดงประวัติการสนทนา
# ────────────────────────────────────────────────
for msg in st.session_state.messages:
    avatar = "🧑‍✈️" if msg["role"] == "user" else "✈️"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# ────────────────────────────────────────────────
# 11. รับ input (จาก chat box หรือ quick button)
# ────────────────────────────────────────────────
user_input = st.chat_input("พิมพ์คำถามเกี่ยวกับระเบียบพัสดุ...")

# รับจาก quick button (sidebar)
if st.session_state.quick_input:
    user_input = st.session_state.quick_input
    st.session_state.quick_input = None

# ────────────────────────────────────────────────
# 12. ประมวลผลคำถาม
# ────────────────────────────────────────────────
if user_input and user_input.strip():
    # แสดงคำถามของ user
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="🧑‍✈️"):
        st.markdown(user_input)

    # แสดง typing indicator + ส่งคำถาม
    with st.chat_message("assistant", avatar="✈️"):
        with st.spinner("กำลังค้นหาในระเบียบ..."):
            start = time.time()

            # ถ้าไม่มีไฟล์ ให้ตอบจาก knowledge ทั่วไป
            if reg_files:
                answer = ask_regulation(
                    user_input,
                    reg_files,
                    st.session_state.chat_history,
                )
            else:
                # fallback: ตอบโดยไม่มี file context
                model = get_model()
                response = model.generate_content(user_input)
                answer = response.text + "\n\n---\n*⚠️ หมายเหตุ: ตอบจากความรู้ทั่วไป ยังไม่ได้โหลดไฟล์ระเบียบ ทอ.*"

            elapsed = time.time() - start

        st.markdown(answer)
        st.caption(f"⏱ ตอบใน {elapsed:.1f} วินาที")

    # บันทึกลง session state
    st.session_state.messages.append({"role": "assistant", "content": answer})
    st.session_state.chat_history.append({
        "user":      user_input,
        "assistant": answer,
    })

    # จำกัด history ไม่เกิน 10 rounds (ประหยัด token)
    if len(st.session_state.chat_history) > 10:
        st.session_state.chat_history = st.session_state.chat_history[-10:]

