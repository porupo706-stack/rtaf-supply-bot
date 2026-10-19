import os
import asyncio
import streamlit as st
import requests as req
from notebooklm import NotebookLMClient
from cryptography.fernet import Fernet, InvalidToken

from citations import CITATION_CSS, render_answer, render_sources_html

# =========================================================
# CONFIG — ดึงจาก Secrets ทั้งหมด (ไม่มีข้อมูลสำคัญใน code)
# =========================================================
NOTEBOOK_ID = st.secrets.get("NOTEBOOK_ID", "")

# True = ดึงเนื้อหาเต็มของไฟล์มาหาบริบทรอบข้อความที่อ้างอิง (เหมือน NotebookLM แสดงย่อหน้า)
#        ช้าลงเล็กน้อย แต่ได้ข้อความละเอียดกว่า
# False = แสดงเฉพาะข้อความที่ NotebookLM ส่งมาให้ (เร็วกว่า)
SHOW_CONTEXT = True

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

# CSS ของเลขอ้างอิง / การ์ดแหล่งข้อมูล
st.markdown(CITATION_CSS, unsafe_allow_html=True)

# =========================================================
# HEADER
# =========================================================
st.subheader("✈️ ผู้ช่วยงานพัสดุ ของกองทัพอากาศ (ทอ.)")
st.caption("ระบบถาม–ตอบระเบียบและเอกสารงานพัสดุ")

# =========================================================
# ดึง session จาก GitHub Gist (cache 1 ชั่วโมง)
# =========================================================
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_from_gist() -> str | None:
    gist_id  = st.secrets.get("GIST_ID", "")
    gh_token = st.secrets.get("GITHUB_TOKEN", "")
    enc_key  = st.secrets.get("SESSION_ENC_KEY", "")

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
# ตรวจ NOTEBOOK_ID
# =========================================================
if not NOTEBOOK_ID:
    st.error("⚠️ ไม่พบ NOTEBOOK_ID ใน Streamlit Secrets")
    st.info("กรุณาเพิ่ม NOTEBOOK_ID = '...' ใน App settings → Secrets")
    st.stop()

# =========================================================
# NOTEBOOKLM
# =========================================================
async def get_answer(prompt: str) -> dict:
    """คืน {"answer": str, "references": [ {number, source_id, title, cited_text, context} ]}"""
    async with NotebookLMClient.from_storage() as client:
        result = await client.chat.ask(NOTEBOOK_ID, prompt)
        raw_refs = list(getattr(result, "references", None) or [])

        # ชื่อไฟล์ของแต่ละแหล่งข้อมูล
        titles: dict[str, str] = {}
        if raw_refs:
            try:
                for s in await client.sources.list(NOTEBOOK_ID):
                    titles[s.id] = getattr(s, "title", None) or s.id
            except Exception:
                pass

        refs: list[dict] = []
        fulltexts: dict = {}
        for r in raw_refs:
            sid = getattr(r, "source_id", "") or ""
            cited = getattr(r, "cited_text", "") or ""
            context = ""

            # หาย่อหน้ารอบข้อความที่ถูกอ้างอิงจากเนื้อหาเต็มของไฟล์
            if SHOW_CONTEXT and sid and cited:
                try:
                    if sid not in fulltexts:
                        fulltexts[sid] = await client.sources.get_fulltext(NOTEBOOK_ID, sid)
                    ft = fulltexts[sid]
                    if ft is not None:
                        matches = ft.find_citation_context(cited)
                        if matches:
                            context = matches[0][0]
                except Exception:
                    fulltexts[sid] = None

            refs.append({
                "number": getattr(r, "citation_number", None) or 0,
                "source_id": sid,
                "title": titles.get(sid, ""),
                "cited_text": cited,
                "context": context,
            })

        return {"answer": result.answer, "references": refs}


# =========================================================
# แสดงข้อความแชท (ใช้ทั้งตอนตอบใหม่และตอนแสดงประวัติ)
# =========================================================
def render_message(message: dict):
    st.markdown(message["content"], unsafe_allow_html=True)
    refs = message.get("references") or []
    if refs:
        with st.expander(f"📚 แหล่งข้อมูลอ้างอิง ({len({r['number'] for r in refs})})"):
            st.markdown(render_sources_html(refs), unsafe_allow_html=True)


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
    st.info("กรุณาตั้งค่า GIST_ID + GITHUB_TOKEN + SESSION_ENC_KEY ใน Secrets")
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
        render_message(message)


# =========================================================
# CHAT INPUT
# =========================================================
user_input = st.chat_input("พิมพ์คำถามเกี่ยวกับงานพัสดุ...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("🔎 กำลังค้นหาข้อมูลจากฐานความรู้..."):
            try:
                data = asyncio.run(get_answer(user_input))
                msg = {
                    "role": "assistant",
                    "content": render_answer(data["answer"], data["references"]),
                    "references": data["references"],
                }
                render_message(msg)
                st.session_state.messages.append(msg)
            except Exception as e:
                if is_auth_error(e):
                    clear_gist_cache()
                    st.session_state["auth_expired"] = True
                    st.rerun()
                else:
                    st.error("❌ เกิดข้อผิดพลาดในการเชื่อมต่อ NotebookLM")
                    st.caption(f"รายละเอียด: {str(e)}")
