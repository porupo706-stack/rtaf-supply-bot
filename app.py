import streamlit as st
import os
from PyPDF2 import PdfReader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

# ตั้งค่าหน้าจอ Streamlit
st.set_page_config(
    page_title="ผู้ช่วยงานพัสดุ ของกองทัพอากาศ (ทอ.)",
    page_icon="✈️",
    layout="wide"
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

# ==========================================
# 1. ฟังก์ชันสำหรับการอ่านและฝังข้อมูล (Ingestion)
# ==========================================
def get_pdf_text_and_metadata(pdf_docs):
    """อ่านไฟล์ PDF และดึงข้อความพร้อมระบุชื่อไฟล์และหน้า (Metadata)"""
    docs = []
    for pdf in pdf_docs:
        pdf_reader = PdfReader(pdf)
        for i, page in enumerate(pdf_reader.pages):
            text = page.extract_text()
            if text:
                docs.append({
                    "text": text,
                    "source": pdf.name,
                    "page": i + 1
                })
    return docs

def get_text_chunks(raw_docs):
    """หั่นข้อความเป็น Chunk ย่อยๆ โดยพก Metadata ไปด้วย"""
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunked_docs = []
    for doc in raw_docs:
        chunks = text_splitter.split_text(doc["text"])
        for chunk in chunks:
            chunked_docs.append(Document(
                page_content=chunk,
                metadata={"source": doc["source"], "page": doc["page"]}
            ))
    return chunked_docs

def get_vector_store(text_chunks, api_key):
    """สร้าง Vector Database ด้วย FAISS และ Gemini Embeddings"""
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004",
        google_api_key=api_key
    )
    vector_store = FAISS.from_documents(text_chunks, embedding=embeddings)
    vector_store.save_local("faiss_index")

# ==========================================
# 2. ฟังก์ชัน RAG ด้วย LCEL (ไม่ใช้ langchain.chains เลย)
# ==========================================
def format_docs(docs):
    """แปลง Document list เป็น string พร้อม metadata"""
    result = ""
    for doc in docs:
        source = doc.metadata.get("source", "ไม่ทราบ")
        page = doc.metadata.get("page", "?")
        result += f"[เอกสาร: {source}, หน้า: {page}]\nรายละเอียด: {doc.page_content}\n---\n"
    return result

def generate_answer(user_question, api_key, chat_history):
    """ประมวลผลคำถาม ดึงข้อมูล และให้ AI ตอบโดยใช้ LCEL"""
    if not os.path.exists("faiss_index/index.faiss"):
        return "⚠️ ไม่พบฐานข้อมูลความรู้ กรุณาอัปโหลดระเบียบพัสดุและคลิก 'ประมวลผลเอกสาร' ที่แถบด้านซ้ายก่อนครับ"

    # โหลด Vector Store
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004",
        google_api_key=api_key
    )
    vector_store = FAISS.load_local(
        "faiss_index", embeddings,
        allow_dangerous_deserialization=True
    )
    retriever = vector_store.as_retriever(search_kwargs={"k": 5})

    # สร้าง Prompt
    prompt_template = """คุณคือผู้ช่วย AI ชำนาญการด้านงานพัสดุของกองทัพอากาศ (ทอ.) หน้าที่ของคุณคือตอบคำถามจากข้อมูลระเบียบที่กำหนดให้ (Context) เท่านั้น

ประวัติการสนทนา (Chat History):
{chat_history}

ข้อมูลอ้างอิงที่ค้นพบ (Context):
{context}

คำถามปัจจุบัน:
{input}

กฎเหล็กของคุณ (Source-Grounded AI):
1. ตอบคำถามโดยอิงข้อเท็จจริงจาก 'ข้อมูลอ้างอิง (Context)' ด้านบนเท่านั้น ห้ามใช้ความรู้นอกเหนือจากนี้
2. ทุกครั้งที่คุณให้ข้อเท็จจริง **ต้องมีการแนบการอ้างอิงแหล่งที่มา** ต่อท้ายเสมอ ในรูปแบบ [เอกสาร: ชื่อไฟล์, หน้า: X]
3. หากข้อมูลในเอกสารไม่เพียงพอ ให้ตอบตรงๆ ว่า "ไม่มีข้อมูลเพียงพอในระเบียบที่ให้อ้างอิง" ห้ามเดาหรือแต่งข้อมูลขึ้นมาเองเด็ดขาด
4. ตอบด้วยภาษาไทยที่สละสลวย เป็นทางการ และเข้าใจง่าย

คำตอบ (พร้อมการอ้างอิง):"""

    prompt = PromptTemplate(
        template=prompt_template,
        input_variables=["context", "input", "chat_history"]
    )

    # สร้าง LLM
    model = ChatGoogleGenerativeAI(
        model="gemini-1.5-pro",
        temperature=0.1,
        google_api_key=api_key
    )

    # สร้าง LCEL Chain (ไม่ใช้ langchain.chains เลย)
    chain = (
        {
            "context": retriever | RunnableLambda(format_docs),
            "input": RunnablePassthrough(),
            "chat_history": RunnableLambda(lambda _: chat_history)
        }
        | prompt
        | model
        | StrOutputParser()
    )

    return chain.invoke(user_question)

def format_chat_history(messages):
    """จัดรูปแบบประวัติแชทเพื่อส่งให้ AI"""
    formatted = ""
    for msg in messages[:-1]:
        role = "User" if msg["role"] == "user" else "AI"
        formatted += f"{role}: {msg['content']}\n"
    return formatted

# ==========================================
# 3. ส่วนแสดงผล UI ของ Streamlit
# ==========================================
def main():
    st.subheader("✈️ ผู้ช่วยงานพัสดุ ของกองทัพอากาศ (ทอ.)")
    st.caption("ระบบถาม–ตอบระเบียบและเอกสารงานพัสดุ (อ้างอิงจากเอกสารจริง)")

    api_key_secret = st.secrets.get("GEMINI_API_KEY", "")

    with st.sidebar:
        st.subheader("⚙️ การตั้งค่าระบบ")
        api_key = st.text_input("ใส่ Google Gemini API Key", value=api_key_secret, type="password")
        if not api_key:
            st.markdown("[รับ API Key ได้ที่ Google AI Studio](https://aistudio.google.com/app/apikey)")

        st.divider()

        st.subheader("📁 นำเข้าความรู้ (ระเบียบพัสดุ ทอ.)")
        pdf_docs = st.file_uploader("อัปโหลดไฟล์ PDF ที่นี่", accept_multiple_files=True, type=["pdf"])

        if st.button("ประมวลผลเอกสาร"):
            if not api_key:
                st.error("กรุณาใส่ API Key ก่อนครับ")
            elif not pdf_docs:
                st.error("กรุณาอัปโหลดไฟล์ PDF อย่างน้อย 1 ไฟล์")
            else:
                with st.spinner("กำลังอ่านและสร้างฐานข้อมูลระเบียบ..."):
                    raw_docs = get_pdf_text_and_metadata(pdf_docs)
                    text_chunks = get_text_chunks(raw_docs)
                    get_vector_store(text_chunks, api_key)
                    st.success("อัปเดตฐานความรู้เสร็จสิ้น! เริ่มถามคำถามได้เลย")

        if st.button("ล้างประวัติการสนทนา"):
            st.session_state.messages = []
            st.rerun()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("พิมพ์คำถามเกี่ยวกับงานพัสดุ..."):
        if not api_key:
            st.warning("กรุณาใส่ API Key ที่แท็บด้านซ้ายมือก่อนครับ หรือตั้งค่าใน Streamlit Secrets")
            return

        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("🔎 กำลังค้นหาข้อมูลจากระเบียบ..."):
                chat_history = format_chat_history(st.session_state.messages)
                answer = generate_answer(prompt, api_key, chat_history)
                st.markdown(answer)

        st.session_state.messages.append({"role": "assistant", "content": answer})

if __name__ == "__main__":
    main()
