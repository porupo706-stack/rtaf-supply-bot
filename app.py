import os
import pathlib
import shutil

# 1. คัดลอกไฟล์ storage_state.json ไปไว้ในโฟลเดอร์ระบบ "ตั้งแต่บรรทัดแรกสุด" ก่อนเริ่มทำงานใดๆ
try:
    home_dir = pathlib.Path.home()
    target_dir = home_dir / ".notebooklm" / "profiles" / "default"
    target_dir.mkdir(parents=True, exist_ok=True)
    if os.path.exists("storage_state.json"):
        shutil.copy("storage_state.json", target_dir / "storage_state.json")
except Exception as e:
    print(f"Setup auth error: {e}")

# 2. ติดตั้ง Playwright browser สำหรับรันเบราว์เซอร์เบื้องหลัง
os.system("playwright install chromium")

import streamlit as st
import asyncio
from notebooklm import NotebookLMClient

NOTEBOOK_ID = "53c42aa4-91a9-46b0-9094-2b480d0f0c5f"

st.title("✈️ ผู้ช่วยงานพัสดุ ทอ.")
st.caption("ถาม-ตอบ ระเบียบและเอกสารพัสดุผ่าน NotebookLM")

# กล่องรับข้อความจากผู้ใช้
user_input = st.chat_input("พิมพ์คำถามเกี่ยวกับงานพัสดุ ที่นี่...")

async def get_answer(prompt):
    async with NotebookLMClient.from_storage() as client:
        result = await client.chat.ask(NOTEBOOK_ID, prompt)
        return result.answer

if user_input:
    # แสดงคำถามของผู้ใช้
    with st.chat_message("user"):
        st.write(user_input)
    
    # ประมวลผลและแสดงคำตอบ
    with st.chat_message("assistant"):
        with st.spinner("กำลังค้นหาข้อมูลพัสดุ..."):
            answer = asyncio.run(get_answer(user_input))
            st.write(answer)
