import os
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
    # แก้ไขจุดที่ 1: เปลี่ยนมาใช้ .from_storage() เพื่อโหลดเซสชันที่เคยล็อกอินไว้อัตโนมัติ
    async with NotebookLMClient.from_storage() as client:
        # แก้ไขจุดที่ 2: เปลี่ยนเป็น client.chat.ask และดึงข้อมูลจาก .answer
        result = await client.chat.ask(NOTEBOOK_ID, prompt)
        return result.answer

if user_input:
    # แสดงคำถามของผู้ใช้
    with st.chat_message("user"):
        st.write(user_input)
    
    # ประมวลผลและแสดงคำตอบ
    with st.chat_message("assistant"):
        with st.spinner("กำลังค้นหาข้อมูลพัสดุ..."):
            # เนื่องจาก Streamlit เป็น Sync ต้องรัน Async ผ่าน asyncio
            answer = asyncio.run(get_answer(user_input))
            st.write(answer)