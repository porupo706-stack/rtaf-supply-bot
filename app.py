import os
import asyncio
import streamlit as st
import requests as req
from notebooklm import NotebookLMClient
from cryptography.fernet import Fernet, InvalidToken

# =========================================================
# CONFIG
# =========================================================
NOTEBOOK_ID = "53c42aa4-91a9-46b0-9094-2b480d0f0c5f"

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="RTAF Chat Assistant | ศูนย์บริการข้อมูลงานพัสดุ",
    page_icon="✈️",
    layout="centered",
)

# --- ปรับแต่ง UI ด้วย Custom CSS (สไตล์ Modern & Minimalist) ---
st.markdown("""
<style>
/* ซ่อน Header เมนู (ปุ่ม 3 จุด มุมขวาบน) และ Footer ของ Streamlit เพื่อความสะอาดตา */
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}

/* เปลี่ยนพื้นหลังหลักให้เป็นสีเทาขาวสว่างๆ */
.stApp {
    background-color: #F8F9FA;
}

/* เปลี่ยนสีขอบช่องแชทจากสีเขียว เป็นสีน้ำเงิน ทอ. และปรับให้ขอบมน */
div[data-testid="stChatInput"] {
    border-color: #004B87 !important; 
    border-radius: 1rem !important; 
    background-color: #FFFFFF !important;
}
div[data-testid="stChatInput"]:focus-within,
div[data-testid="stChatInput"] > div:focus-within {
    border-color: #004B87 !important; 
    box-shadow: 0 0 0 1.5px #004B87 !important;
    border-radius: 1rem !important; 
}
</style>

<!-- ส่วน Header โลโก้และชื่อแอป จัดกึ่งกลาง -->
<div style="text-align: center; margin-top: -3rem; margin-bottom: 2rem;">
    <img src="https://upload.wikimedia.org/wikipedia/commons/e/e5/Seal_of_the_Royal_Thai_Air_Force.svg" width="110" alt="RTAF Logo" style="margin-bottom: 15px;">
    <h2 style="color: #004B87; font-weight: 800; font-family: sans-serif; margin-bottom: 0px;">RTAF CHAT ASSISTANT</h2>
    <p style="color: #6C757D; font-size: 1.1rem; margin-top: 5px;">ศูนย์บริการข้อมูลงานพัสดุออนไลน์ | กองทัพอากาศ</p>
</div>
""", unsafe_allow_html=True)


# =========================================================
# ดึง session จาก GitHub Gist (cache 1 ชั่วโมง)
# =========================================================
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_from_gist() -> str | None:
    gist_id    = st.secrets.get("GIST_ID", "")
    gh_token   = st.secrets.get("GITHUB_TOKEN", "")
    enc_key    = st.secrets.get("SESSION_ENC_KEY", "")

    if not all([gist_id, gh_token, enc_key]):
        return None  

    try:
        resp = req.get(
            f"https://api.github.com/gists/{gist_id}",
            headers={"Authorization": f"token {gh_token}"},
            timeout=10,
        )
        if resp.status_code != 200:
            return None

        encrypted = resp.json()["files"]["session.enc"]["content"]
        return Fernet(enc_key.encode()).decrypt(encrypted.encode()).decode()

    except (InvalidToken, KeyError, Exception):
        return None

# =========================================================
# ตั้งค่า Auth
# =========================================================
def setup_auth() -> bool:
    auth_json = fetch_from_gist()

    if not auth_json:
        try:
            auth_json = st.secrets["NOTEBOOKLM_AUTH_JSON"]
        except Exception:
            pass

    if not auth_json:
        return False

    os.environ["NOTEBOOKLM_AUTH_JSON"] = auth_json
    return True

def is_auth_error(e: Exception) -> bool:
    keywords = ["auth", "login", "credential", "unauthorized",
                "403", "session", "google", "oauth", "token", "invalid"]
    return any(kw in str(e).lower() for kw in keywords)

def clear_gist_cache():
    fetch_from_gist.clear()

# =========================================================
# NOTEBOOKLM
# =========================================================
async def get_answer(prompt: str) -> str:
    async with NotebookLMClient.from_storage() as client:
        result = await client.chat.ask(NOTEBOOK_ID, prompt)
        return result.answer

# =========================================================
# หน้า "Session หมดอายุ"
# =========================================================
if st.session_state.get("auth_expired", False):
    st.error("🔐 Session Google หมดอายุแล้ว")
    st.markdown("""
**วิธีแก้ (ทำแค่นี้เดียว):**

1. Double-click **`refresh_session.bat`** ในคอมพิวเตอร์
2. Login Google บน browser ที่เปิดขึ้นมา
3. รอจนขึ้นว่า "สำเร็จ"
4. กดปุ่ม **"รีเฟรช"** ด้านล่าง

> ไม่ต้องแตะ Streamlit Secrets อีกแล้ว ✅
""")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 รีเฟรช", type="primary", use_container_width=True):
            clear_gist_cache()
            st.session_state["auth_expired"] = False
            st.rerun()
    with col2:
        if st.button("🗑️ ล้าง cache แล้วลองใหม่", use_container_width=True):
            clear_gist_cache()
            st.session_state["auth_expired"] = False
            st.rerun()
    st.stop()

# =========================================================
# ตรวจ auth
# =========================================================
if not setup_auth():
    st.error("⚠️ ยังไม่ได้ตั้งค่า NotebookLM Authentication")
    st.info("กรุณาตั้งค่า **NOTEBOOKLM_AUTH_JSON** ใน Streamlit Secrets\n\n"
            "หรือตั้งค่า GIST_ID + GITHUB_TOKEN + SESSION_ENC_KEY แล้วรัน refresh_session.bat")
    if st.button("🔄 ลองใหม่", use_container_width=True):
        clear_gist_cache()
        st.rerun()
    st.stop()

# =========================================================
# CHAT HISTORY
# =========================================================
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# =========================================================
# CHAT INPUT
# =========================================================
user_input = st.chat_input("พิมพ์คำถามเกี่ยวกับระเบียบและงานพัสดุ...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("🔎 กำลังค้นหาข้อมูลระเบียบจากฐานความรู้..."):
            try:
                answer = asyncio.run(get_answer(user_input))
                st.markdown(answer)
                st.session_state.messages.append(
                    {"role": "assistant", "content": answer}
                )
            except Exception as e:
                if is_auth_error(e):
                    clear_gist_cache()
                    st.session_state["auth_expired"] = True
                    st.rerun()
                else:
                    st.error("❌ เกิดข้อผิดพลาดในการเชื่อมต่อ NotebookLM")
                    st.caption(f"รายละเอียด: {str(e)}")
