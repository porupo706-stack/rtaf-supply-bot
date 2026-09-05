# ════════════════════════════════════════════════════════════════════
#  RTAF Supply Bot — app.py  v3.0
#  ผู้ช่วยงานพัสดุ กองทัพอากาศ (ทอ.)
#  จัดทำโดย พ.อ.อ.กนก คงสีทอง
#  ใช้ google-genai (SDK ใหม่) + gemini-1.5-flash
# ════════════════════════════════════════════════════════════════════

import streamlit as st
import os
import glob
import time
from pathlib import Path
from google import genai
from google.genai import types

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
# 1. Custom CSS
# ────────────────────────────────────────────────
st.markdown("""
<style>
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
    .stChatMessage { border-radius: 10px; }
    [data-testid="stSidebar"] { background-color: #f0f4ff; }
    .status-ok  { color: #2e7d32; font-weight: 600; }
    .status-err { color: #c62828; font-weight: 600; }
    .stButton button {
        border-radius: 20px;
        border: 1px solid #3f51b5;
        color: #3f51b5;
        background: white;
        font-size: 0.82rem;
        padding: 0.3rem 0.8rem;
        transition: all 0.2s;
    }
    .stButton button:hover { background: #3f51b5; color: white; }
</style>
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────
# 2. API Key
# ────────────────────────────────────────────────
def get_api_key():
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"]
    return os.environ.get("GEMINI_API_KEY")

API_KEY = get_api_key()

if not API_KEY:
    st.error("❌ ไม่พบ GEMINI_API_KEY — ตั้งค่าใน Streamlit Secrets")
    st.stop()

# สร้าง client (google-genai SDK ใหม่)
client = genai.Client(api_key=API_KEY)
MODEL  = "gemini-3.5-flash-lite"

# ────────────────────────────────────────────────
# 3. โหลด PDF ระเบียบขึ้น Gemini File API
# ────────────────────────────────────────────────
REGULATIONS_DIR = Path("regulations")

@st.cache_resource(show_spinner=False)
def load_regulation_files():
    if not REGULATIONS_DIR.exists():
        return [], []

    pdf_paths = sorted(glob.glob(str(REGULATIONS_DIR / "**/*.pdf"), recursive=True))
    if not pdf_paths:
        return [], []

    uploaded_files = []
    file_names = []

    progress = st.progress(0, text="กำลังโหลดระเบียบ...")
    for i, path in enumerate(pdf_paths):
        try:
            with open(path, "rb") as f:
                response = client.files.upload(
                    file=f,
                    config=types.UploadFileConfig(mime_type="application/pdf")
                )
            uploaded_files.append(response)
            file_names.append(Path(path).stem)
        except Exception as e:
            st.warning(f"โหลดไฟล์ไม่สำเร็จ: {Path(path).name} — {e}")
        progress.progress(
            (i + 1) / len(pdf_paths),
            text=f"โหลด {i+1}/{len(pdf_paths)}: {Path(path).name}"
        )
    progress.empty()
    return uploaded_files, file_names

# ────────────────────────────────────────────────
# 4. System Prompt
# ────────────────────────────────────────────────
SYSTEM_PROMPT = """คุณคือผู้ช่วยงานพัสดุของกองทัพอากาศ (ทอ.) ที่มีความเชี่ยวชาญด้านระเบียบและกฎหมายพัสดุ

หน้าที่หลัก:
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

# ────────────────────────────────────────────────
# 5. ฟังก์ชันถาม-ตอบ (google-genai SDK ใหม่)
# ────────────────────────────────────────────────
def ask_regulation(question: str, reg_files: list, chat_history: list) -> str:
    try:
        # สร้าง contents list
        contents = []

        # ใส่ประวัติการสนทนา
        for h in chat_history:
            contents.append(types.Content(
                role="user",
                parts=[types.Part(text=h["user"])]
            ))
            contents.append(types.Content(
                role="model",
                parts=[types.Part(text=h["assistant"])]
            ))

        # คำถามปัจจุบัน + ไฟล์ระเบียบ (ใส่แค่ turn แรก)
        current_parts = []
        if not chat_history:
            for f in reg_files:
                current_parts.append(types.Part(
                    file_data=types.FileData(file_uri=f.uri, mime_type="application/pdf")
                ))
        current_parts.append(types.Part(text=question))

        contents.append(types.Content(role="user", parts=current_parts))

        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.2,
            )
        )
        return response.text

    except Exception as e:
        return f"⚠️ เกิดข้อผิดพลาด: {str(e)}\n\nกรุณาลองถามใหม่อีกครั้ง"

# ────────────────────────────────────────────────
# 6. Sidebar
# ────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ✈️ ผู้ช่วยงานพัสดุ ทอ.")
    st.markdown("---")

    with st.spinner("กำลังโหลดระเบียบ..."):
        reg_files, reg_names = load_regulation_files()

    if reg_files:
        st.markdown(f'<p class="status-ok">✅ พร้อมใช้งาน ({len(reg_files)} ไฟล์)</p>',
                    unsafe_allow_html=True)
        with st.expander("📂 ระเบียบที่โหลดแล้ว", expanded=False):
            for name in reg_names:
                st.markdown(f"• {name}")
    else:
        st.markdown('<p class="status-err">⚠️ ไม่พบไฟล์ระเบียบ</p>',
                    unsafe_allow_html=True)
        st.info("ใส่ไฟล์ PDF ในโฟลเดอร์ `regulations/` แล้ว deploy ใหม่")

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
    if st.button("🗑️ ล้างประวัติการสนทนา", use_container_width=True):
        st.session_state.messages = []
        st.session_state.chat_history = []
        st.rerun()

    st.markdown("---")
    st.markdown("""
    <small>
    จัดทำโดย พ.อ.อ.กนก คงสีทอง<br>
    Powered by Google Gemini API<br>
    v3.0 — google-genai SDK
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

if not reg_files:
    st.warning("⚠️ **ยังไม่มีไฟล์ระเบียบ** — ระบบตอบจากความรู้ทั่วไปก่อน")

# ────────────────────────────────────────────────
# 8. Session State
# ────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "quick_input" not in st.session_state:
    st.session_state.quick_input = None

# ────────────────────────────────────────────────
# 9. Welcome message
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
# 10. ประวัติการสนทนา
# ────────────────────────────────────────────────
for msg in st.session_state.messages:
    avatar = "🧑‍✈️" if msg["role"] == "user" else "✈️"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# ────────────────────────────────────────────────
# 11. รับ input
# ────────────────────────────────────────────────
user_input = st.chat_input("พิมพ์คำถามเกี่ยวกับระเบียบพัสดุ...")

if st.session_state.quick_input:
    user_input = st.session_state.quick_input
    st.session_state.quick_input = None

# ────────────────────────────────────────────────
# 12. ประมวลผล
# ────────────────────────────────────────────────
if user_input and user_input.strip():
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="🧑‍✈️"):
        st.markdown(user_input)

    with st.chat_message("assistant", avatar="✈️"):
        with st.spinner("กำลังค้นหาในระเบียบ..."):
            start = time.time()
            answer = ask_regulation(
                user_input,
                reg_files,
                st.session_state.chat_history,
            )
            elapsed = time.time() - start

        st.markdown(answer)
        st.caption(f"⏱ ตอบใน {elapsed:.1f} วินาที")

    st.session_state.messages.append({"role": "assistant", "content": answer})
    st.session_state.chat_history.append({
        "user": user_input,
        "assistant": answer,
    })

    if len(st.session_state.chat_history) > 10:
        st.session_state.chat_history = st.session_state.chat_history[-10:]
