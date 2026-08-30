import os
import asyncio

import streamlit as st

from db import (
    init_db,
    save_log
)

from cache import (
    get_cache,
    save_cache
)

from router import (
    route_notebook
)

from admin import (
    show_dashboard
)

from notebooklm_service import (
    ask_notebook
)


# =================================================
# CONFIG
# =================================================

st.set_page_config(
    page_title="ผู้ช่วยงานพัสดุ ทอ.",
    page_icon="✈️",
    layout="centered"
)

init_db()


# =================================================
# AUTH
# =================================================

try:

    os.environ[
        "NOTEBOOKLM_AUTH_JSON"
    ] = st.secrets[
        "NOTEBOOKLM_AUTH_JSON"
    ]

except Exception:

    st.error(
        "ไม่พบ NOTEBOOKLM_AUTH_JSON"
    )

    st.stop()


# =================================================
# SIDEBAR
# =================================================

st.sidebar.title(
    "⚙️ เมนู"
)

show_admin = st.sidebar.checkbox(
    "Dashboard"
)

if show_admin:

    show_dashboard()
    st.stop()


# =================================================
# HEADER
# =================================================

st.title(
    "✈️ ผู้ช่วยงานพัสดุ ทอ."
)

st.caption(
    "ระบบถาม–ตอบระเบียบและเอกสารงานพัสดุ ขับเคลื่อนด้วย NotebookLM"
)


# =================================================
# CHAT
# =================================================

if "messages" not in st.session_state:

    st.session_state.messages = []


for message in st.session_state.messages:

    with st.chat_message(
        message["role"]
    ):

        st.markdown(
            message["content"]
        )


# =================================================
# INPUT
# =================================================

prompt = st.chat_input(
    "พิมพ์คำถามเกี่ยวกับงานพัสดุ..."
)

if prompt:

    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt
        }
    )

    with st.chat_message(
        "user"
    ):
        st.markdown(prompt)

    with st.chat_message(
        "assistant"
    ):

        with st.spinner(
            "🔎 กำลังค้นหาข้อมูล..."
        ):

            try:

                notebook_id = route_notebook(
                    prompt
                )

                cached = get_cache(
                    prompt
                )

                if cached:

                    answer = cached
                    cache_hit = True

                else:

                    result = asyncio.run(
                        ask_notebook(
                            notebook_id,
                            prompt
                        )
                    )

                    try:

                        answer = result.answer

                    except Exception:

                        answer = str(result)

                    save_cache(
                        prompt,
                        answer
                    )

                    cache_hit = False

                st.markdown(
                    answer
                )

                if cache_hit:

                    st.caption(
                        "⚡ ตอบจาก Cache"
                    )

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": answer
                    }
                )

                save_log(
                    prompt,
                    answer,
                    notebook_id,
                    cache_hit
                )

            except Exception as e:

                st.error(
                    "เชื่อมต่อ NotebookLM ไม่สำเร็จ"
                )

                st.code(
                    str(e)
                )