import os
import asyncio
import concurrent.futures
import streamlit as st
from notebooklm import NotebookLMClient

# =========================================================
# CONFIG
# =========================================================
NOTEBOOK_ID = st.secrets.get("NOTEBOOK_ID", "")

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="ผู้ช่วยงานพัสดุ ของกองทัพอากาศ (ทอ.)",
    page_icon="✈️",
    layout="centered",
)

st.markdown("""
<style>
div[data-testid="stChatInput"] {
    border-color: #4CAF50 !important;
    border-radius: 0.5rem !important;
}
div[data-testid="stChatInput"]:focus-within,
div[data-testid="stChatInput"] > div:focus-within {
    border-color: #2E7D32 !important;
    box-shadow: 0 0 0 1px #2E7D32 !important;
    border-radius: 0.5rem !important;
}
</style>
""", unsafe_allow_html=True)

st.subheader("✈️ ผู้ช่วยงานพัสดุ ของกองทัพอากาศ (ทอ.)")
st.caption("ระบบถาม–ตอบระเบียบและเอกสารงานพัสดุ")

# =========================================================
# ตรวจ NOTEBOOK_ID
# =========================================================
if not NOTEBOOK_ID:
    st.error("⚠️ ไม่พบ NOTEBOOK_ID ใน Streamlit Secrets")
    st.info("กรุณาเพิ่ม NOTEBOOK_ID = '...' ใน App settings → Secrets")
    st.stop()

# =========================================================
# ตั้งค่า Auth จาก NOTEBOOKLM_AUTH_JSON (ที่มี master token)
#
# ไม่ต้องการอีกต่อไป:
#   - GIST_ID / GITHUB_TOKEN / SESSION_ENC_KEY
#   - auto_refresh.py / refresh_session.py / refresh_session.bat
#
# master token จะ mint cookie ใหม่อัตโนมัติทุกครั้งที่ session หมดอายุ
# =========================================================
_auth_json = st.secrets.get("NOTEBOOKLM_AUTH_JSON", "")

if not _auth_json:
    st.error("⚠️ ไม่พบ NOTEBOOKLM_AUTH_JSON ใน Streamlit Secrets")
    with st.expander("📋 วิธีตั้งค่า (คลิกเพื่อดู)"):
        st.markdown("""
**รันบนเครื่องตัวเอง 1 ครั้ง:**
```bash
notebooklm login --master-token --account your@gmail.com
```

**คัดลอก JSON จากไฟล์:**
```
~/.notebooklm/profiles/default/storage_state.json
```
*(Windows: `C:\\Users\\<username>\\.notebooklm\\profiles\\default\\storage_state.json`)*

**วางใน Streamlit → App settings → Secrets:**
```toml
NOTEBOOK_ID       = "53c42aa4-91a9-46b0-9094-2b480d0f0c5f"
NOTEBOOKLM_AUTH_JSON = '{ ... วาง JSON ที่คัดลอกทั้งก้อนตรงนี้ ... }'
```
        """)
    st.stop()

# ตั้ง env var → notebooklm-py ใช้ master token refresh cookie อัตโนมัติ
# ไม่ต้องการ browser หรือ Playwright บน Streamlit Cloud
os.environ["NOTEBOOKLM_AUTH_JSON"] = _auth_json


# =========================================================
# NOTEBOOKLM — async query
# =========================================================
async def _ask(question: str) -> str:
    async with NotebookLMClient.from_storage() as client:
        result = await client.chat.ask(NOTEBOOK_ID, question)
        return result.answer


def get_answer(question: str) -> str:
    """
    รัน coroutine ใน thread แยก
    หลีกเลี่ยง "event loop already running" ใน Streamlit
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _ask(question)).result(timeout=60)


# =========================================================
# CHAT HISTORY
# =========================================================
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# =========================================================
# CHAT INPUT
# =========================================================
if user_input := st.chat_input("พิมพ์คำถามเกี่ยวกับงานพัสดุ..."):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("🔎 กำลังค้นหาข้อมูลจากฐานความรู้..."):
            try:
                answer = get_answer(user_input)
                st.markdown(answer)
                st.session_state.messages.append(
                    {"role": "assistant", "content": answer}
                )
            except Exception as e:
                st.error("❌ เกิดข้อผิดพลาด กรุณาลองใหม่อีกครั้ง")
                st.caption(f"รายละเอียด: {str(e)}")
