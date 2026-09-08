import json
import os
import shutil
from pathlib import Path

import streamlit as st
from PyPDF2 import PdfReader
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


# ==========================================
# CONFIG
# ==========================================
APP_TITLE = "ผู้ช่วยงานพัสดุ ของกองทัพอากาศ (ทอ.)"
INDEX_DIR = Path("faiss_index")
INDEX_META_FILE = INDEX_DIR / "index_meta.json"

# โมเดลที่ยังใช้งานได้ใน Gemini API
EMBEDDING_MODEL = "models/gemini-embedding-001"
LLM_MODEL = "gemini-2.5-pro"

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
TOP_K = 5


# ==========================================
# ตั้งค่าหน้าจอ Streamlit
# ==========================================
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="✈️",
    layout="wide",
)

st.markdown(
    """
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

    .source-box {
        padding: 0.75rem 1rem;
        border-left: 4px solid #2E7D32;
        background: rgba(76, 175, 80, 0.07);
        border-radius: 0.35rem;
        margin-top: 0.75rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ==========================================
# HELPERS
# ==========================================
def clean_api_key(api_key: str) -> str:
    """ตัดช่องว่าง/เครื่องหมาย quote ที่อาจติดมาจาก Secrets หรือการ copy."""
    if not api_key:
        return ""
    return api_key.strip().strip('"').strip("'")


def get_pdf_text_and_metadata(pdf_docs):
    """อ่าน PDF และเก็บข้อความพร้อมชื่อไฟล์/เลขหน้า."""
    docs = []
    failed_files = []

    for pdf in pdf_docs:
        try:
            pdf_reader = PdfReader(pdf)
            file_has_text = False

            for page_no, page in enumerate(pdf_reader.pages, start=1):
                text = (page.extract_text() or "").strip()

                if text:
                    file_has_text = True
                    docs.append(
                        {
                            "text": text,
                            "source": pdf.name,
                            "page": page_no,
                        }
                    )

            if not file_has_text:
                failed_files.append(f"{pdf.name} (ไม่พบข้อความที่อ่านได้)")

        except Exception as exc:
            failed_files.append(f"{pdf.name} ({exc})")

    return docs, failed_files


def get_text_chunks(raw_docs):
    """แบ่งข้อความเป็น chunks พร้อม metadata ต้นทาง."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""],
    )

    chunked_docs = []

    for doc in raw_docs:
        chunks = text_splitter.split_text(doc["text"])

        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue

            chunked_docs.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "source": doc["source"],
                        "page": doc["page"],
                    },
                )
            )

    return chunked_docs


def make_embeddings(api_key: str):
    """สร้าง Gemini embedding client."""
    return GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=api_key,
    )


def clear_vector_store():
    """ลบฐาน FAISS เดิมก่อนสร้างใหม่."""
    if INDEX_DIR.exists():
        shutil.rmtree(INDEX_DIR, ignore_errors=True)


def save_index_metadata():
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    metadata = {
        "embedding_model": EMBEDDING_MODEL,
        "llm_model": LLM_MODEL,
        "version": 2,
    }

    INDEX_META_FILE.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def is_vector_store_ready():
    """ตรวจว่ามี FAISS และสร้างด้วย embedding รุ่นปัจจุบันหรือไม่."""
    index_file = INDEX_DIR / "index.faiss"
    store_file = INDEX_DIR / "index.pkl"

    if not index_file.exists() or not store_file.exists():
        return False

    if not INDEX_META_FILE.exists():
        return False

    try:
        metadata = json.loads(INDEX_META_FILE.read_text(encoding="utf-8"))
        return metadata.get("embedding_model") == EMBEDDING_MODEL
    except Exception:
        return False


def get_vector_store(text_chunks, api_key):
    """สร้าง FAISS index ด้วย Gemini Embeddings และบันทึก metadata."""
    if not text_chunks:
        raise ValueError("ไม่พบข้อความจากเอกสารสำหรับสร้างฐานความรู้")

    embeddings = make_embeddings(api_key)

    # ป้องกัน index เก่าที่สร้างด้วย embedding คนละรุ่น
    clear_vector_store()

    vector_store = FAISS.from_documents(
        text_chunks,
        embedding=embeddings,
    )

    vector_store.save_local(str(INDEX_DIR))
    save_index_metadata()

    return len(text_chunks)


def format_docs(docs):
    """แปลงผลค้นหาเป็น Context พร้อม metadata."""
    if not docs:
        return "ไม่พบข้อมูลอ้างอิงที่เกี่ยวข้อง"

    parts = []

    for doc in docs:
        source = doc.metadata.get("source", "ไม่ทราบ")
        page = doc.metadata.get("page", "?")

        parts.append(
            f"[เอกสาร: {source}, หน้า: {page}]\n"
            f"รายละเอียด: {doc.page_content}"
        )

    return "\n---\n".join(parts)


def format_chat_history(messages):
    """จัดรูปแบบประวัติสนทนา โดยไม่รวมคำถามล่าสุด."""
    formatted = []

    for msg in messages[:-1]:
        role = "ผู้ใช้" if msg["role"] == "user" else "ผู้ช่วย"
        formatted.append(f"{role}: {msg['content']}")

    return "\n".join(formatted)


def load_vector_store(api_key: str):
    """โหลด FAISS index ที่สร้างด้วย embedding รุ่นปัจจุบัน."""
    if not is_vector_store_ready():
        raise FileNotFoundError(
            "ไม่พบฐานความรู้ หรือฐานความรู้ถูกสร้างด้วย embedding รุ่นเก่า "
            "กรุณาอัปโหลด PDF แล้วกด 'ประมวลผลเอกสาร' ใหม่"
        )

    embeddings = make_embeddings(api_key)

    return FAISS.load_local(
        str(INDEX_DIR),
        embeddings,
        allow_dangerous_deserialization=True,
    )


def generate_answer(user_question, api_key, chat_history):
    """RAG ด้วย LCEL โดยไม่ใช้ langchain.chains."""
    try:
        vector_store = load_vector_store(api_key)
        retriever = vector_store.as_retriever(
            search_kwargs={"k": TOP_K}
        )

        prompt_template = """คุณคือ "ผู้ช่วยงานพัสดุของกองทัพอากาศ (ทอ.)"

ภารกิจ:
ตอบคำถามโดยยึดข้อมูลจาก Context ที่ค้นพบจากเอกสารของผู้ใช้เท่านั้น
ห้ามเติมกฎหมาย ระเบียบ ตัวเลข วันที่ หรือขั้นตอนจากความรู้ภายนอก Context

ประวัติการสนทนา:
{chat_history}

Context:
{context}

คำถามปัจจุบัน:
{input}

ข้อกำหนดสำคัญ:
1. ตอบเฉพาะสิ่งที่ Context สนับสนุน
2. ทุกข้อเท็จจริงจากเอกสารต้องระบุแหล่งอ้างอิงในรูปแบบ [เอกสาร: ชื่อไฟล์, หน้า: X]
3. หาก Context ไม่เพียงพอ ให้ตอบว่า
   "ไม่มีข้อมูลเพียงพอในระเบียบที่ให้อ้างอิง"
   และอย่าเดาหรือสร้างข้อมูลขึ้นมาเอง
4. หากมีหลายเอกสาร ให้แยกการอ้างอิงให้ชัดเจน
5. ใช้ภาษาไทยที่เป็นทางการ อ่านง่าย และตรงประเด็น

คำตอบ:
"""

        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=["context", "input", "chat_history"],
        )

        model = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            temperature=0.1,
            google_api_key=api_key,
        )

        chain = (
            {
                "context": retriever | RunnableLambda(format_docs),
                "input": RunnablePassthrough(),
                "chat_history": RunnableLambda(lambda _: chat_history),
            }
            | prompt
            | model
            | StrOutputParser()
        )

        return chain.invoke(user_question)

    except Exception as exc:
        error_text = str(exc)

        if "API key" in error_text or "api key" in error_text:
            return "❌ API Key ไม่ถูกต้องหรือไม่ได้รับอนุญาต กรุณาตรวจสอบ GEMINI_API_KEY"

        if "404" in error_text and "embedding" in error_text.lower():
            return (
                "❌ Gemini Embedding ใช้งานไม่ได้กับ API Key นี้ "
                "กรุณาตรวจสอบว่า API Key ใช้กับ Gemini API ได้ และลองกด "
                "'ประมวลผลเอกสาร' ใหม่อีกครั้ง"
            )

        if "quota" in error_text.lower() or "429" in error_text:
            return "❌ เกินโควตา Gemini API ชั่วคราว กรุณาลองใหม่ภายหลัง"

        return f"❌ เกิดข้อผิดพลาดในการประมวลผล: {error_text}"


# ==========================================
# MAIN UI
# ==========================================
def main():
    st.subheader("✈️ ผู้ช่วยงานพัสดุ ของกองทัพอากาศ (ทอ.)")
    st.caption("ระบบถาม–ตอบระเบียบและเอกสารงานพัสดุ โดยอ้างอิงจากเอกสารที่อัปโหลด")

    api_key_secret = ""
    try:
        api_key_secret = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        api_key_secret = ""

    api_key = ""

    with st.sidebar:
        st.subheader("⚙️ การตั้งค่าระบบ")

        api_key = clean_api_key(
            st.text_input(
                "Google Gemini API Key",
                value=api_key_secret,
                type="password",
                help="ควรเก็บค่าไว้ใน Streamlit Secrets ด้วยชื่อ GEMINI_API_KEY",
            )
        )

        if not api_key:
            st.markdown(
                "[สร้าง API Key ที่ Google AI Studio]"
                "(https://aistudio.google.com/app/apikey)"
            )

        st.divider()

        st.subheader("📁 นำเข้าความรู้")
        pdf_docs = st.file_uploader(
            "อัปโหลดไฟล์ PDF",
            accept_multiple_files=True,
            type=["pdf"],
        )

        if st.button(
            "ประมวลผลเอกสาร",
            type="primary",
            use_container_width=True,
        ):
            if not api_key:
                st.error("กรุณาใส่ Google Gemini API Key ก่อนครับ")
            elif not pdf_docs:
                st.error("กรุณาอัปโหลดไฟล์ PDF อย่างน้อย 1 ไฟล์")
            else:
                with st.spinner("กำลังอ่าน PDF และสร้างฐานความรู้..."):
                    try:
                        raw_docs, failed_files = get_pdf_text_and_metadata(pdf_docs)

                        if not raw_docs:
                            st.error(
                                "ไม่สามารถอ่านข้อความจาก PDF ที่อัปโหลดได้ "
                                "ไฟล์อาจเป็น PDF แบบสแกนภาพ"
                            )
                        else:
                            text_chunks = get_text_chunks(raw_docs)
                            chunk_count = get_vector_store(text_chunks, api_key)

                            st.success(
                                f"สร้างฐานความรู้สำเร็จ: {chunk_count:,} chunks"
                            )

                            if failed_files:
                                st.warning(
                                    "ไฟล์/หน้าที่ไม่สามารถอ่านได้:\n- "
                                    + "\n- ".join(failed_files)
                                )

                            # รีเฟรชสถานะหลังสร้าง index
                            st.session_state["index_ready"] = True

                    except Exception as exc:
                        st.error(f"❌ สร้างฐานความรู้ไม่สำเร็จ: {exc}")

        if is_vector_store_ready():
            st.success("✅ ฐานความรู้พร้อมใช้งาน")
        else:
            st.info("ℹ️ ยังไม่มีฐานความรู้พร้อมใช้งาน")

        if st.button(
            "ล้างประวัติการสนทนา",
            use_container_width=True,
        ):
            st.session_state.messages = []
            st.rerun()

    # ==========================================
    # Chat history
    # ==========================================
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # ==========================================
    # Chat input
    # ==========================================
    prompt = st.chat_input("พิมพ์คำถามเกี่ยวกับงานพัสดุ...")

    if prompt:
        if not api_key:
            st.warning(
                "กรุณาใส่ Google Gemini API Key ที่แถบด้านซ้าย "
                "หรือกำหนด GEMINI_API_KEY ใน Streamlit Secrets"
            )
            return

        if not is_vector_store_ready():
            st.warning(
                "ยังไม่มีฐานความรู้ที่พร้อมใช้งาน "
                "กรุณาอัปโหลด PDF และกด 'ประมวลผลเอกสาร' ก่อนครับ"
            )
            return

        st.session_state.messages.append(
            {"role": "user", "content": prompt}
        )

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("🔎 กำลังค้นหาข้อมูลจากระเบียบ..."):
                chat_history = format_chat_history(
                    st.session_state.messages
                )
                answer = generate_answer(
                    prompt,
                    api_key,
                    chat_history,
                )
                st.markdown(answer)

        st.session_state.messages.append(
            {"role": "assistant", "content": answer}
        )


if __name__ == "__main__":
    main()
