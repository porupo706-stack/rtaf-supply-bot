import os
import json
import asyncio
import streamlit as st

from notebooklm import NotebookLMClient


# =========================================================
# CONFIG
# =========================================================

NOTEBOOK_ID = "53c42aa4-91a9-46b0-9094-2b480d0f0c5f"


# =========================================================
# PAGE
# =========================================================

st.set_page_config(
    page_title="ผู้ช่วยงานพัสดุ ของกองทัพอากาศ (ทอ.)",
    page_icon="✈️",
    layout="centered"
)


# =========================================================
# HEADER
# =========================================================

# ใช้ st.subheader แทน st.title เพื่อให้ขนาดเล็กลงพอดีกับมือถือ พร้อมเพิ่มเส้นคั่นสีฟ้า
st.subheader("✈️ ผู้ช่วยงานพัสดุ ของกองทัพอากาศ (ทอ.)", divider="blue")

st.caption(
    "ระบบถาม–ตอบระเบียบและเอกสารงานพัสดุ "
    "ขับเคลื่อนด้วย NotebookLM"
)


# =========================================================
# AUTH
# =========================================================

def setup_auth():

    try:
        auth_json = st.secrets["NOTEBOOKLM_AUTH_JSON"]
    except Exception:
        return False

    if not auth_json:
        return False

    os.environ["NOTEBOOKLM_AUTH_JSON"] = auth_json

    return True


# =========================================================
# NOTEBOOKLM
# =========================================================

async def get_answer(prompt):

    async with NotebookLMClient.from_storage() as client:

        result = await client.chat.ask(
            NOTEBOOK_ID,
            prompt
        )

        return result.answer


# =========================================================
# CHECK AUTH
# =========================================================

if not setup_auth():

    st.error(
        "ยังไม่ได้ตั้งค่า NotebookLM Authentication"
    )

    st.info(
        "กรุณาตั้งค่า NOTEBOOKLM_AUTH_JSON "
        "ใน Streamlit Secrets"
    )

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

user_input = st.chat_input(
    "พิมพ์คำถามเกี่ยวกับงานพัสดุ..."
)


if user_input:

    # User
    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_input
        }
    )

    with st.chat_message("user"):

        st.markdown(user_input)


    # AI
    with st.chat_message("assistant"):

        with st.spinner(
            "🔎 กำลังค้นหาข้อมูลจากฐานความรู้..."
        ):

            try:

                answer = asyncio.run(
                    get_answer(user_input)
                )

                st.markdown(answer)

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": answer
                    }
                )

            except Exception as e:

                st.error(
                    "เกิดข้อผิดพลาดในการเชื่อมต่อ NotebookLM"
                )

                st.caption(
                    f"รายละเอียด: {str(e)}"
                )
