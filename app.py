import json
import os
import pickle
import re
import shutil
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path

import numpy as np
import streamlit as st
from pypdf import PdfReader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from google import genai
from google.genai import types


# ==========================================
# CONFIG
# ==========================================
APP_TITLE = "ผู้ช่วยงานพัสดุ ของกองทัพอากาศ (ทอ.)"
INDEX_DIR = Path("knowledge_index")
INDEX_FILE = INDEX_DIR / "index.pkl"
META_FILE = INDEX_DIR / "index_meta.json"

try:
    LLM_MODEL = st.secrets.get("GEMINI_MODEL", None) or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
except Exception:
    LLM_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
TOP_K = 6
MIN_SCORE = 0.04
INDEX_VERSION = 3


# ==========================================
# STREAMLIT CONFIG
# ==========================================
st.set_page_config(page_title=APP_TITLE, page_icon="✈️", layout="wide")

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
.source-box {
    padding: 0.75rem 1rem;
    border-left: 4px solid #2E7D32;
    background: rgba(76, 175, 80, 0.07);
    border-radius: 0.35rem;
    margin-top: 0.75rem;
}
</style>
""", unsafe_allow_html=True)


# ==========================================
# HELPERS
# ==========================================
def clean_api_key(api_key: str) -> str:
    if not api_key:
        return ""
    return api_key.strip().strip('"').strip("'")


def normalize_thai_text(text: str) -> str:
    text = text or ""
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def get_pdf_text_and_metadata(pdf_docs):
    docs = []
    failed_files = []
    for pdf in pdf_docs:
        try:
            pdf_reader = PdfReader(pdf)
            file_has_text = False
            for page_no, page in enumerate(pdf_reader.pages, start=1):
                text = normalize_thai_text(page.extract_text() or "")
                if text:
                    file_has_text = True
                    docs.append({"text": text, "source": pdf.name, "page": page_no})
            if not file_has_text:
                failed_files.append(f"{pdf.name} (ไม่พบข้อความที่อ่านได้ อาจเป็น PDF สแกนภาพ)")
        except Exception as exc:
            failed_files.append(f"{pdf.name} ({exc})")
    return docs, failed_files


def get_text_chunks(raw_docs):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", "", "\u200b"],
    )
    chunked_docs = []
    for doc in raw_docs:
        chunks = text_splitter.split_text(doc["text"])
        for chunk in chunks:
            chunk = normalize_thai_text(chunk)
            if not chunk:
                continue
            chunked_docs.append(
                Document(page_content=chunk, metadata={"source": doc["source"], "page": doc["page"]})
            )
    return chunked_docs


def clear_knowledge_index():
    if INDEX_DIR.exists():
        shutil.rmtree(INDEX_DIR, ignore_errors=True)


def save_knowledge_index(vectorizer, matrix, docs):
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"vectorizer": vectorizer, "matrix": matrix, "docs": docs}
    with INDEX_FILE.open("wb") as file:
        pickle.dump(payload, file, protocol=pickle.HIGHEST_PROTOCOL)
    META_FILE.write_text(
        json.dumps({
            "version": INDEX_VERSION,
            "retrieval": "TF-IDF character n-gram (local)",
            "chunks": len(docs),
            "llm_model": LLM_MODEL,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_knowledge_index(text_chunks):
    if not text_chunks:
        raise ValueError("ไม่พบข้อความจากเอกสารสำหรับสร้างฐานความรู้")
    texts = [doc.page_content for doc in text_chunks]
    vectorizer = TfidfVectorizer(
        analyzer="char",
        ngram_range=(2, 5),
        min_df=1,
        sublinear_tf=True,
        max_features=250_000,
    )
    matrix = vectorizer.fit_transform(texts)
    clear_knowledge_index()
    save_knowledge_index(vectorizer, matrix, text_chunks)
    return len(text_chunks)


def is_knowledge_ready():
    if not INDEX_FILE.exists() or not META_FILE.exists():
        return False
    try:
        metadata = json.loads(META_FILE.read_text(encoding="utf-8"))
        return metadata.get("version") == INDEX_VERSION
    except Exception:
        return False


def load_knowledge_index():
    if not is_knowledge_ready():
        raise FileNotFoundError("ไม่พบฐานความรู้ กรุณาอัปโหลด PDF และกด 'ประมวลผลเอกสาร' ก่อนครับ")
    with INDEX_FILE.open("rb") as file:
        payload = pickle.load(file)
    return payload["vectorizer"], payload["matrix"], payload["docs"]


def retrieve_documents(user_question, top_k=TOP_K):
    vectorizer, matrix, docs = load_knowledge_index()
    query_vector = vectorizer.transform([normalize_thai_text(user_question)])
    scores = cosine_similarity(query_vector, matrix).ravel()
    if scores.size == 0:
        return []
    ranked_indices = np.argsort(scores)[::-1]
    results = []
    for idx in ranked_indices[:top_k]:
        score = float(scores[idx])
        if score < MIN_SCORE:
            continue
        results.append({"doc": docs[idx], "score": score})
    return results


def format_docs(results):
    if not results:
        return "ไม่พบข้อมูลอ้างอิงที่เกี่ยวข้องเพียงพอ"
    parts = []
    seen = set()
    for item in results:
        doc = item["doc"]
        source = doc.metadata.get("source", "ไม่ทราบ")
        page = doc.metadata.get("page", "?")
        key = (source, page, doc.page_content[:120])
        if key in seen:
            continue
        seen.add(key)
        parts.append(f"[เอกสาร: {source}, หน้า: {page}]\nรายละเอียด: {doc.page_content}")
    return "\n---\n".join(parts)


def format_chat_history(messages):
    formatted = []
    for msg in messages[:-1]:
        role = "ผู้ใช้" if msg["role"] == "user" else "ผู้ช่วย"
        formatted.append(f"{role}: {msg['content']}")
    return "\n".join(formatted[-10:])


def _call_gemini(client, prompt: str) -> str:
    """เรียก Gemini API — ปิด AFC; fallback ถ้า SDK เวอร์ชันเก่าไม่รองรับ config นี้"""
    # วิธีที่ 1: ปิด AFC ผ่าน GenerateContentConfig (google-genai >= 0.8)
    try:
        response = client.models.generate_content(
            model=LLM_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True,
                ),
            ),
        )
        return response.text
    except (AttributeError, TypeError):
        # SDK เวอร์ชันที่ไม่มี AutomaticFunctionCallingConfig → เรียกตรง ๆ
        pass

    # วิธีที่ 2: เรียกโดยไม่มี AFC config (ปลอดภัยเสมอเพราะไม่ได้ส่ง tools)
    response = client.models.generate_content(
        model=LLM_MODEL,
        contents=prompt,
    )
    return response.text


def generate_answer(user_question, api_key, chat_history):
    """ใช้ google-genai SDK ใหม่ — รองรับ Auth Key AQ. format"""
    try:
        results = retrieve_documents(user_question, TOP_K)
        context = format_docs(results)

        prompt = f"""คุณคือ "ผู้ช่วยงานพัสดุของกองทัพอากาศ (ทอ.)"

หน้าที่:
ตอบคำถามโดยยึดข้อมูลใน Context เท่านั้น
ห้ามเติมกฎหมาย ระเบียบ ตัวเลข วันที่ วงเงิน หรือขั้นตอนจากความรู้ภายนอก Context

ประวัติการสนทนา:
{chat_history}

Context จากเอกสาร:
{context}

คำถามปัจจุบัน:
{user_question}

กฎสำคัญ:
1. ตอบเฉพาะข้อเท็จจริงที่ Context สนับสนุน
2. ทุกข้อเท็จจริงต้องมีแหล่งอ้างอิงในรูปแบบ [เอกสาร: ชื่อไฟล์, หน้า: X]
3. หาก Context ไม่เพียงพอ ให้ตอบว่า "ไม่มีข้อมูลเพียงพอในระเบียบที่ให้อ้างอิง" และห้ามเดา
4. หากมีหลายเอกสาร ให้แยกแหล่งอ้างอิงให้ชัดเจน
5. ใช้ภาษาไทยทางการ อ่านง่าย และตอบตรงคำถาม

คำตอบ:"""

        client = genai.Client(api_key=api_key)
        return _call_gemini(client, prompt)

    except Exception as exc:
        error_text = str(exc)
        lower_error = error_text.lower()

        if (
            "api_key" in lower_error
            or "permission_denied" in lower_error
            or "unauthenticated" in lower_error
            or ("invalid" in lower_error and "key" in lower_error)
        ):
            return "❌ API Key ไม่ถูกต้องหรือไม่มีสิทธิ์ใช้งาน กรุณาตรวจสอบ GEMINI_API_KEY"

        if "resource_exhausted" in lower_error or "429" in lower_error or "quota" in lower_error:
            return "❌ Gemini API เกินโควตา กรุณารอสักครู่แล้วลองใหม่ (Free tier: 15 req/นาที)"

        if "not found" in lower_error or "404" in lower_error or "not_found" in lower_error:
            return (
                f"❌ ไม่พบโมเดล `{LLM_MODEL}`\n\n"
                f"**Error จริง:** `{error_text}`\n\n"
                "กรุณาเปลี่ยน GEMINI_MODEL ใน Streamlit Secrets เป็น:\n"
                "- `gemini-1.5-flash` ← **แนะนำ** (เสถียรที่สุด)\n"
                "- `gemini-1.5-pro`\n"
                "- `gemini-2.0-flash-exp`"
            )

        return f"❌ เกิดข้อผิดพลาด:\n```\n{error_text}\n```"


# ==========================================
# MAIN UI
# ==========================================
def main():
    st.subheader("✈️ ผู้ช่วยงานพัสดุ ของกองทัพอากาศ (ทอ.)")
    st.caption("ระบบถาม–ตอบระเบียบและเอกสารงานพัสดุ โดยค้นจากเอกสารที่อัปโหลด และให้ Gemini ช่วยเรียบเรียงคำตอบ")

    api_key_secret = ""
    try:
        api_key_secret = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        api_key_secret = ""

    with st.sidebar:
        st.subheader("⚙️ การตั้งค่าระบบ")

        api_key = clean_api_key(
            st.text_input(
                "Google Gemini API Key",
                value=api_key_secret,
                type="password",
                help="รองรับ Auth Key AQ. และ AIzaSy...",
            )
        )

        if not api_key:
            st.markdown("[สร้าง API Key ที่ Google AI Studio](https://aistudio.google.com/app/apikey)")

        st.caption(f"โมเดลตอบคำถาม: `{LLM_MODEL}`")
        st.caption("🔎 การค้นเอกสาร: TF-IDF Local (ไม่ใช้ Embedding API)")

        st.divider()

        st.subheader("📁 นำเข้าความรู้")
        pdf_docs = st.file_uploader("อัปโหลดไฟล์ PDF", accept_multiple_files=True, type=["pdf"])

        if st.button("ประมวลผลเอกสาร", type="primary", use_container_width=True):
            if not pdf_docs:
                st.error("กรุณาอัปโหลดไฟล์ PDF อย่างน้อย 1 ไฟล์")
            else:
                with st.spinner("กำลังอ่าน PDF และสร้างฐานความรู้แบบ Local..."):
                    try:
                        raw_docs, failed_files = get_pdf_text_and_metadata(pdf_docs)
                        if not raw_docs:
                            st.error("ไม่สามารถอ่านข้อความจาก PDF ที่อัปโหลดได้ ไฟล์อาจเป็น PDF แบบสแกนภาพ")
                        else:
                            text_chunks = get_text_chunks(raw_docs)
                            chunk_count = build_knowledge_index(text_chunks)
                            st.success(
                                f"สร้างฐานความรู้สำเร็จ: {chunk_count:,} chunks "
                                f"(ไม่เสีย Gemini Embedding quota)"
                            )
                            if failed_files:
                                st.warning("ไฟล์ที่ไม่สามารถอ่านได้:\n- " + "\n- ".join(failed_files))
                            st.session_state["index_ready"] = True
                    except Exception as exc:
                        st.error(f"❌ สร้างฐานความรู้ไม่สำเร็จ: {exc}")

        if is_knowledge_ready():
            st.success("✅ ฐานความรู้พร้อมใช้งาน")
        else:
            st.info("ℹ️ ยังไม่มีฐานความรู้พร้อมใช้งาน")

        if st.button("ล้างประวัติการสนทนา", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("พิมพ์คำถามเกี่ยวกับงานพัสดุ...")

    if prompt:
        if not api_key:
            st.warning(
                "กรุณาใส่ Google Gemini API Key ที่แถบด้านซ้าย "
                "หรือกำหนด GEMINI_API_KEY ใน Streamlit Secrets"
            )
            return
        if not is_knowledge_ready():
            st.warning("ยังไม่มีฐานความรู้ที่พร้อมใช้งาน กรุณาอัปโหลด PDF และกด 'ประมวลผลเอกสาร' ก่อนครับ")
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
