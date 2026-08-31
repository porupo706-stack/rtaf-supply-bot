import os
import pathlib
import shutil
import asyncio
import streamlit as st
import PyPDF2
import pandas as pd

# =========================================================
# AUTO SETUP AUTH (คัดลอกไฟล์ Session)
# =========================================================
try:
    home_dir = pathlib.Path.home()
    target_dir = home_dir / ".notebooklm" / "profiles" / "default"
    target_dir.mkdir(parents=True, exist_ok=True)
    if os.path.exists("storage_state.json"):
        shutil.copy("storage_state.json", target_dir / "storage_state.json")
except Exception as e:
    print(f"Setup auth error: {e}")

# ติดตั้ง Playwright browser
os.system("playwright install chromium")

from notebooklm import NotebookLMClient

# =========================================================
# CONFIG
# =========================================================
NOTEBOOK_ID = "53c42aa4-91a9-46b0-9094-2b480d0f0c5f"

st.set_page_config(
    page_title="ผู้ช่วยงานพัสดุ ทอ.",
    page_icon="✈️",
    layout="centered"
)

# =========================================================
# HEADER
# =========================================================
st.subheader("✈️ ผู้ช่วยงานพัสดุ ของกองทัพอากาศ (ทอ.)")
st.caption("ระบบถาม–ตอบระเบียบและเอกสารงานพัสดุ ขับเคลื่อนด้วย NotebookLM")

# =========================================================
# NOTEBOOKLM FUNCTION
# =========================================================
async def get_answer(prompt):
    async with NotebookLMClient.from_storage() as client:
        result = await client.chat.ask(NOTEBOOK_ID, prompt)
        return result.answer

# =========================================================
# CHAT HISTORY
# =========================================================
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# =========================================================
# FILE UPLOAD (อัปโหลดไฟล์ถามเฉพาะกิจ)
# =========================================================
uploaded_file = st.file_uploader(
    "📎 แนบไฟล์ประกอบคำถาม (รองรับไฟล์ PDF, TXT, CSV ขนาดไม่เกิน 10 หน้า)", 
    type=["txt", "csv", "pdf"]
)

# =========================================================
# CHAT INPUT
# =========================================================
user_input = st.chat_input("พิมพ์คำถามเกี่ยวกับงานพัสดุ...")

if user_input:
    
    # 1. แสดงข้อความผู้ใช้บนหน้าจอ
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 2. จัดเตรียมคำถามที่จะส่งให้ AI (เช็คว่ามีไฟล์แนบไหม)
    final_prompt = user_input
    
    if uploaded_file is not None:
        file_content = ""
        try:
            # แยกวิธีอ่านตามประเภทไฟล์
            if uploaded_file.name.endswith(".txt"):
                file_content = uploaded_file.getvalue().decode("utf-8")
            elif uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
                file_content = df.to_string()
            elif uploaded_file.name.endswith(".pdf"):
                pdf_reader = PyPDF2.PdfReader(uploaded_file)
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    if text:
                        file_content += text + "\n"
            
            # ป้องกันข้อความยาวเกินไปจนแชทพัง (ตัดรับแค่ 5000 ตัวอักษรแรก)
            file_content = file_content[:5000] 
            
            # รวมไฟล์เข้ากับคำถามอย่างแนบเนียน
            final_prompt = (
                f"อ้างอิงข้อมูลจากไฟล์ที่แนบมานี้:\n"
                f"-------------------\n{file_content}\n-------------------\n\n"
                f"จากข้อมูลด้านบน จงตอบคำถามนี้: {user_input}"
            )
        except Exception as e:
            st.error(f"❌ อ่านไฟล์แนบไม่ได้: {str(e)}")

    # 3. ส่งคำถามไปหา NotebookLM
    with st.chat_message("assistant"):
        with st.spinner("🔎 กำลังวิเคราะห์ข้อมูลและหาคำตอบ..."):
            try:
                # ส่ง final_prompt ที่อาจจะรวมเนื้อหาไฟล์ไว้แล้วไปให้ AI
                answer = asyncio.run(get_answer(final_prompt))
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
            except Exception as e:
                st.error("เกิดข้อผิดพลาดในการเชื่อมต่อ NotebookLM")
                st.caption(f"รายละเอียด: {str(e)}")
