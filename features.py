"""
features.py — ฟีเจอร์เสริมของ notebooklm-py สำหรับผู้ช่วยงานพัสดุ ทอ.

ไม่พึ่ง streamlit จึงทดสอบ/เรียกใช้แยกได้ ทุกฟังก์ชัน async รับ notebook_id
และเปิด client ของตัวเองด้วย NotebookLMClient.from_storage()
(app.py ตั้ง NOTEBOOKLM_AUTH_JSON ไว้ให้แล้ว)
"""
from __future__ import annotations

import asyncio
import hmac
import json
import re
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from notebooklm import (
    AudioFormat,
    AudioLength,
    InfographicDetail,
    InfographicOrientation,
    MindMapKind,
    NotebookLMClient,
    QuizDifficulty,
    QuizQuantity,
    ReportFormat,
    SlideDeckFormat,
    SlideDeckLength,
)

# =========================================================
# ค่าคงที่ — ชนิดสื่อที่สร้างได้ (ชื่อไทยที่แสดงในหน้าเว็บ)
# =========================================================
STUDIO_TYPES: dict[str, str] = {
    "audio": "🎙️ พอดแคสต์สรุป (Audio Overview)",
    "report": "📄 รายงาน / คู่มือสรุป",
    "slides": "📊 สไลด์นำเสนอ",
    "quiz": "📝 แบบทดสอบ (Quiz)",
    "flashcards": "🗂️ แฟลชการ์ด",
    "mindmap": "🧠 แผนผังความคิด (Mind Map)",
    "datatable": "📋 ตารางข้อมูล",
    "infographic": "🖼️ อินโฟกราฟิก",
}

AUDIO_FORMATS = {
    "เจาะลึก (Deep Dive)": AudioFormat.DEEP_DIVE,
    "สรุปสั้น (Brief)": AudioFormat.BRIEF,
    "วิพากษ์ (Critique)": AudioFormat.CRITIQUE,
    "โต้วาที (Debate)": AudioFormat.DEBATE,
}
AUDIO_LENGTHS = {
    "สั้น": AudioLength.SHORT,
    "ปกติ": AudioLength.DEFAULT,
    "ยาว": AudioLength.LONG,
}
REPORT_FORMATS = {
    "สรุปบรรยาย (Briefing Doc)": ReportFormat.BRIEFING_DOC,
    "คู่มือการเรียนรู้ (Study Guide)": ReportFormat.STUDY_GUIDE,
    "บทความ (Blog Post)": ReportFormat.BLOG_POST,
    "อธิบายแนวคิด": ReportFormat.CONCEPT_EXPLANATION,
}
SLIDE_FORMATS = {
    "แบบละเอียด": SlideDeckFormat.DETAILED_DECK,
    "แบบผู้นำเสนอ": SlideDeckFormat.PRESENTER_SLIDES,
}
SLIDE_LENGTHS = {"ปกติ": SlideDeckLength.DEFAULT, "สั้น": SlideDeckLength.SHORT}
QUIZ_QUANTITY = {
    "น้อย": QuizQuantity.FEWER,
    "ปกติ": QuizQuantity.STANDARD,
    "มาก": QuizQuantity.MORE,
}
QUIZ_DIFFICULTY = {
    "ง่าย": QuizDifficulty.EASY,
    "ปานกลาง": QuizDifficulty.MEDIUM,
    "ยาก": QuizDifficulty.HARD,
}
INFO_ORIENTATION = {
    "แนวนอน": InfographicOrientation.LANDSCAPE,
    "แนวตั้ง": InfographicOrientation.PORTRAIT,
    "จัตุรัส": InfographicOrientation.SQUARE,
}
INFO_DETAIL = {
    "กระชับ": InfographicDetail.CONCISE,
    "ปกติ": InfographicDetail.STANDARD,
    "ละเอียด": InfographicDetail.DETAILED,
}

# ชนิด artifact (ค่า .kind.name) -> (นามสกุลไฟล์เริ่มต้น, mime)
_FILE_INFO = {
    "AUDIO": ("m4a", "audio/mp4"),
    "VIDEO": ("mp4", "video/mp4"),
    "REPORT": ("md", "text/markdown"),
    "QUIZ": ("json", "application/json"),
    "FLASHCARDS": ("json", "application/json"),
    "SLIDE_DECK": ("pdf", "application/pdf"),
    "INFOGRAPHIC": ("png", "image/png"),
    "DATA_TABLE": ("csv", "text/csv"),
    "MIND_MAP": ("json", "application/json"),
}
KIND_LABEL = {
    "AUDIO": "🎙️ พอดแคสต์",
    "VIDEO": "🎬 วิดีโอ",
    "REPORT": "📄 รายงาน",
    "QUIZ": "📝 แบบทดสอบ",
    "FLASHCARDS": "🗂️ แฟลชการ์ด",
    "SLIDE_DECK": "📊 สไลด์",
    "INFOGRAPHIC": "🖼️ อินโฟกราฟิก",
    "DATA_TABLE": "📋 ตารางข้อมูล",
    "MIND_MAP": "🧠 แผนผังความคิด",
}

# =========================================================
# ตัวช่วยทั่วไป
# =========================================================
def run(coro):
    """เรียก coroutine จากโค้ด streamlit (sync)"""
    return asyncio.run(coro)


def check_admin_password(entered: str, expected: str) -> bool:
    """เทียบรหัสผ่านแบบ constant-time; ถ้ายังไม่ตั้งรหัสไว้ ถือว่าไม่อนุญาต"""
    if not expected or not entered:
        return False
    return hmac.compare_digest(entered.encode(), expected.encode())


def _safe_filename(name: str, fallback: str = "file") -> str:
    name = re.sub(r"[^\w\-. ()ก-๙]", "_", name or "").strip(" ._")
    return name[:80] or fallback


# =========================================================
# CHAT: คำถามแนะนำ / ส่งออก / บันทึกโน้ต
# =========================================================
def strip_html(text: str) -> str:
    """ลบแท็ก HTML ของชิปอ้างอิง เหลือเลขอ้างอิง [n] สำหรับส่งออก"""
    text = re.sub(r'<span class="cite-n">(\d+)</span>', r"[\1]", text)
    text = re.sub(r'<span class="cite-tip">.*?</span></span>', "", text, flags=re.S)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


_MD_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
_MD_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)|(?<!_)_(?!_)(.+?)(?<!_)_(?!_)")
_MD_HEADER = re.compile(r"^#{1,6}\s*", re.MULTILINE)
_MD_BULLET = re.compile(r"^(\s*)[*\-]\s+", re.MULTILINE)


def strip_markdown(text: str) -> str:
    """ลบเครื่องหมาย Markdown (ตัวหนา/เอียง/หัวข้อ/หัวข้อย่อย) เหลือข้อความล้วนสำหรับ PDF"""
    text = _MD_BOLD.sub(lambda m: m.group(1) or m.group(2), text)
    text = _MD_ITALIC.sub(lambda m: m.group(1) or m.group(2), text)
    text = _MD_HEADER.sub("", text)
    text = _MD_BULLET.sub(r"\1• ", text)
    return text


# ---------------------------------------------------------
# ถามแบบแยกผู้ใช้
# ---------------------------------------------------------
# ผู้ใช้ทุกคนใช้สมุดบันทึกเดียวกัน และ NotebookLM ต่อทุกคำถามเข้ากับ "บทสนทนาล่าสุด" ร่วมกัน
# เพื่อไม่ให้คำถามของคนหนึ่งไปปนกับอีกคน: (1) ถามทีละคำถาม (ล็อก) (2) ลบบทสนทนาทันทีหลังได้คำตอบ
# (3) บริบทต่อเนื่องของแต่ละคนแนบไปกับคำถามจากฝั่งแอปแทน
_ASK_LOCK = threading.Lock()
_fresh = False   # True = รู้ว่าสมุดบันทึกไม่มีบทสนทนาค้าง


def history_pairs(messages: list[dict]) -> list[tuple[str, str]]:
    """คู่ (คำถาม, คำตอบล้วน) ของผู้ใช้คนนี้จากประวัติหน้าจอ"""
    out, q = [], None
    for m in messages:
        if m.get("role") == "user":
            q = m.get("content", "")
        elif m.get("role") == "assistant" and q is not None and m.get("answer_plain"):
            out.append((q, m["answer_plain"]))
            q = None
    return out


def build_prompt(question: str, history: list[tuple[str, str]] | None,
                 max_turns: int = 3, max_chars: int = 500) -> str:
    """แนบบริบทบทสนทนาก่อนหน้าของผู้ใช้คนเดียวกัน (ไม่มีประวัติ = ส่งคำถามเดิม)"""
    turns = (history or [])[-max_turns:]
    if not turns:
        return question
    lines = ["บริบทบทสนทนาก่อนหน้าของผู้ใช้คนนี้ (ใช้เมื่อเกี่ยวข้องกับคำถามปัจจุบันเท่านั้น):"]
    for q, a in turns:
        a = _CITE_MARK.sub("", strip_html(a)).strip()
        lines.append(f"ถาม: {q.strip()}\nตอบ: {a[:max_chars]}")
    lines += ["", f"คำถามปัจจุบัน: {question.strip()}"]
    return "\n".join(lines)


async def _drop_current(client, notebook_id: str) -> None:
    cid = await client.chat.get_conversation_id(notebook_id)
    if cid:
        await client.chat.delete_conversation(notebook_id, cid)


async def ask_isolated(client, notebook_id: str, prompt: str):
    """ถามโดยไม่ต่อกับบทสนทนาของคนอื่น แล้วลบบทสนทนาทิ้ง คืนผลลัพธ์ของ chat.ask"""
    global _fresh
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _ASK_LOCK.acquire)
    try:
        if not _fresh:                       # ครั้งแรก/หลังลบพลาด: เคลียร์บทสนทนาเก่าที่ค้างก่อน
            try:
                await _drop_current(client, notebook_id)
                _fresh = True
            except Exception:
                pass                         # ลบไม่ได้ก็ยังตอบต่อ (ลองใหม่คำถามหน้า)
        try:
            result = await client.chat.ask(notebook_id, prompt)
        except Exception:
            _fresh = False
            raise
        try:
            cid = getattr(result, "conversation_id", None)
            if cid:
                await client.chat.delete_conversation(notebook_id, cid)
            else:
                await _drop_current(client, notebook_id)
            _fresh = True
        except Exception:
            _fresh = False
        return result
    finally:
        _ASK_LOCK.release()


async def clear_history(notebook_id: str) -> bool:
    """ล้างประวัติแชตของสมุดบันทึกทันที (ผู้ดูแล) คืน True ถ้ามีบทสนทนาให้ล้าง"""
    async with NotebookLMClient.from_storage() as client:
        cid = await client.chat.get_conversation_id(notebook_id)
        if not cid:
            return False
        await client.chat.delete_conversation(notebook_id, cid)
        return True


FONT_DIR = Path(__file__).parent / "assets" / "fonts"
_CELL_END = {"new_x": "LMARGIN", "new_y": "NEXT", "align": "L"}


def chat_to_pdf_bytes(messages: list[dict], title: str = "บทสนทนา ผู้ช่วยงานพัสดุ ทอ.") -> bytes:
    """สร้างไฟล์ PDF ของบทสนทนา (ฟอนต์ Noto Sans Thai, OFL) ทำในเครื่องทั้งหมด ไม่ส่งข้อมูลไปที่ไหน"""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.add_font("Thai", "", str(FONT_DIR / "NotoSansThai-Regular.ttf"))
    pdf.add_font("Thai", "B", str(FONT_DIR / "NotoSansThai-Bold.ttf"))

    pdf.set_font("Thai", "B", 16)
    pdf.multi_cell(0, 10, title, **_CELL_END)
    pdf.set_font("Thai", "", 10)
    pdf.set_text_color(110, 110, 110)
    pdf.multi_cell(0, 6, f"ส่งออกเมื่อ {datetime.now(_TH_TZ):%d/%m/%Y %H:%M}", **_CELL_END)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    for m in messages:
        pdf.set_font("Thai", "B", 12)
        if m["role"] == "user":
            pdf.set_text_color(20, 60, 140)
            pdf.multi_cell(0, 8, "คำถาม", **_CELL_END)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Thai", "", 12)
            pdf.multi_cell(0, 7, strip_markdown(m["content"]), **_CELL_END)
            pdf.ln(3)
            continue

        pdf.set_text_color(20, 120, 60)
        pdf.multi_cell(0, 8, "คำตอบ", **_CELL_END)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Thai", "", 12)
        pdf.multi_cell(0, 7, strip_markdown(strip_html(m["content"])), **_CELL_END)
        # รายการแหล่งอ้างอิงแบบยาว (ชื่อไฟล์ + ข้อความที่อ้างอิง) ไม่ใส่ใน PDF เพราะทำให้ยาวเกินไป
        # เลข [n] ในเนื้อคำตอบยังอยู่ และดูรายละเอียดแหล่งอ้างอิงได้ในหน้าเว็บ
        pdf.ln(3)

    return bytes(pdf.output())


# =========================================================
# SOURCES
# =========================================================
@dataclass
class SourceInfo:
    id: str
    title: str
    kind: str
    ready: bool
    words: int | None
    updated: Any = None


async def list_sources(notebook_id: str) -> list[SourceInfo]:
    async with NotebookLMClient.from_storage() as client:
        sources = await client.sources.list(notebook_id)
    out = []
    for s in sources:
        kind = getattr(s, "kind", None)
        out.append(SourceInfo(
            id=s.id,
            title=getattr(s, "title", None) or s.id,
            kind=getattr(kind, "name", str(kind or "")),
            ready=bool(getattr(s, "is_ready", True)),
            words=getattr(s, "word_count", None),
            updated=getattr(s, "last_modified_at", None) or getattr(s, "created_at", None),
        ))
    return out


def thai_date(value: Any) -> str | None:
    """วันที่แบบ พ.ศ. (วว/ดด/ปปปป) จาก datetime หรือ timestamp วินาที/มิลลิวินาที; ไม่รู้ค่า -> None"""
    if value is None or value == "":
        return None
    try:
        if isinstance(value, datetime):
            d = value
        else:
            n = float(value)
            d = datetime.fromtimestamp(n / 1000 if n > 1e11 else n)
    except (TypeError, ValueError, OverflowError, OSError):
        return None
    return f"{d.day:02d}/{d.month:02d}/{d.year + 543}"


def latest_update(sources: list[SourceInfo]) -> str | None:
    """วันที่อัปเดตล่าสุดของเอกสารทั้งหมด (พ.ศ.)"""
    best = None
    for s in sources:
        v = s.updated
        try:
            key = v.timestamp() if isinstance(v, datetime) else float(v)
        except (TypeError, ValueError, AttributeError):
            continue
        if best is None or key > best[0]:
            best = (key, v)
    return thai_date(best[1]) if best else None


def format_feedback(question: str, answer: str, rating: str, comment: str = "") -> tuple[str, str]:
    """(หัวข้อ, เนื้อหา) ของโน้ตข้อสังเกตจากผู้ใช้"""
    mark = "👎 ไม่ตรง/ไม่ช่วย" if rating == "down" else "👍 ตรง/ช่วยได้"
    title = f"ข้อสังเกต {mark} {datetime.now(_TH_TZ):%d/%m/%Y %H:%M}"
    body = f"คำถาม: {question.strip()}\n\nคำตอบของระบบ:\n{strip_html(answer).strip()}"
    if comment.strip():
        body += f"\n\nความเห็นผู้ใช้: {comment.strip()}"
    return title, body


async def save_feedback_note(notebook_id: str, question: str, answer: str, rating: str,
                             comment: str = "") -> str:
    """เก็บคะแนน/ข้อสังเกตเป็น note ใน notebook (ผู้ดูแลเปิดดูใน NotebookLM ได้ ไม่หายเมื่อรีบูตแอป)"""
    title, body = format_feedback(question, answer, rating, comment)
    async with NotebookLMClient.from_storage() as client:
        note = await client.notes.create(notebook_id, title, body)
    return note.id


GUIDE_PROMPT = (
    "สรุปสาระสำคัญของเอกสารนี้ไม่เกิน 6 บรรทัด แล้วตามด้วยคำสำคัญ 8-10 คำ "
    "ตอบด้วยภาษาเดียวกับที่ใช้เขียนเอกสารต้นฉบับเสมอ (ห้ามแปลเป็นภาษาอื่น) "
    "ใช้หัวข้อ ## สรุป และ ## คำสำคัญ เท่านั้น ไม่ต้องมีคำนำหรือคำลงท้าย"
)
_CITE_MARK = re.compile(r"\s*\[\d+(?:\s*[,\-–]\s*\d+)*\]")


async def source_guide(notebook_id: str, source_id: str) -> dict:
    """สรุป + คำสำคัญของไฟล์ ในภาษาเดียวกับเอกสาร

    get_guide() ของ NotebookLM ตอบตามภาษาของบัญชี (อังกฤษ) จึงถามผ่านแชทโดยจำกัดเฉพาะไฟล์นี้
    (ไม่แตะค่าภาษาของบัญชี) ถ้าถามไม่สำเร็จจะย้อนไปใช้ get_guide() เดิม
    """
    async with NotebookLMClient.from_storage() as client:
        try:
            res = await client.chat.ask(notebook_id, GUIDE_PROMPT, source_ids=[source_id])
            text = _CITE_MARK.sub("", getattr(res, "answer", "") or "").strip()
            if text:
                return {"summary": text, "keywords": []}
        except Exception:
            pass
        g = await client.sources.get_guide(notebook_id, source_id)
    return {"summary": getattr(g, "summary", "") or "", "keywords": list(getattr(g, "keywords", []) or [])}


async def source_fulltext(notebook_id: str, source_id: str, limit: int = 20000) -> str:
    async with NotebookLMClient.from_storage() as client:
        ft = await client.sources.get_fulltext(notebook_id, source_id)
    text = getattr(ft, "content", "") or ""
    return text if len(text) <= limit else text[:limit] + "\n\n… (ตัดข้อความ)"


async def add_url(notebook_id: str, url: str) -> str:
    async with NotebookLMClient.from_storage() as client:
        s = await client.sources.add_url(notebook_id, url, wait=True)
    return s.id


async def add_text(notebook_id: str, title: str, content: str) -> str:
    async with NotebookLMClient.from_storage() as client:
        s = await client.sources.add_text(notebook_id, title, content, wait=True)
    return s.id


async def add_file_bytes(notebook_id: str, filename: str, data: bytes) -> str:
    """อัปโหลดไฟล์จาก st.file_uploader (เขียนลงไฟล์ชั่วคราวก่อน)"""
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / _safe_filename(filename)
        path.write_bytes(data)
        async with NotebookLMClient.from_storage() as client:
            s = await client.sources.add_file(notebook_id, path, wait=True)
    return s.id


async def delete_source(notebook_id: str, source_id: str) -> None:
    async with NotebookLMClient.from_storage() as client:
        await client.sources.delete(notebook_id, source_id)


# =========================================================
# STUDIO: สร้าง / รายการ / ดาวน์โหลด
# =========================================================
@dataclass
class ArtifactInfo:
    id: str
    title: str
    kind: str          # ชื่อ enum เช่น AUDIO
    completed: bool
    failed: bool

    @property
    def label(self) -> str:
        return KIND_LABEL.get(self.kind, self.kind)


async def list_artifacts(notebook_id: str) -> list[ArtifactInfo]:
    async with NotebookLMClient.from_storage() as client:
        arts = await client.artifacts.list(notebook_id)
    out = []
    for a in arts:
        kind = getattr(a, "kind", None)
        out.append(ArtifactInfo(
            id=a.id,
            title=getattr(a, "title", None) or a.id,
            kind=getattr(kind, "name", str(kind or "")),
            completed=bool(getattr(a, "is_completed", False)),
            failed=bool(getattr(a, "is_failed", False)),
        ))
    return [a for a in out if a.kind in _FILE_INFO]


async def generate(notebook_id: str, studio_type: str, opts: dict[str, Any],
                   timeout: float = 900.0) -> dict:
    """สร้างสื่อแล้วรอจนเสร็จ — opts คือค่าจากฟอร์ม (ดู STUDIO_TYPES)
    คืน {"ok": bool, "error": str|None}"""
    lang = opts.get("language", "th")
    instr = (opts.get("instructions") or "").strip() or None

    async with NotebookLMClient.from_storage() as client:
        art = client.artifacts

        if studio_type == "mindmap":
            await client.mind_maps.generate(
                notebook_id, kind=MindMapKind.INTERACTIVE, language=lang, instructions=instr)
            return {"ok": True, "error": None}

        if studio_type == "audio":
            status = await art.generate_audio(
                notebook_id, language=lang, instructions=instr,
                audio_format=opts.get("audio_format"), audio_length=opts.get("audio_length"))
        elif studio_type == "report":
            status = await art.generate_report(
                notebook_id, report_format=opts.get("report_format", ReportFormat.BRIEFING_DOC),
                language=lang, extra_instructions=instr)
        elif studio_type == "slides":
            status = await art.generate_slide_deck(
                notebook_id, language=lang, instructions=instr,
                slide_format=opts.get("slide_format"), slide_length=opts.get("slide_length"))
        elif studio_type == "quiz":
            status = await art.generate_quiz(
                notebook_id, instructions=instr,
                quantity=opts.get("quantity"), difficulty=opts.get("difficulty"))
        elif studio_type == "flashcards":
            status = await art.generate_flashcards(
                notebook_id, instructions=instr,
                quantity=opts.get("quantity"), difficulty=opts.get("difficulty"))
        elif studio_type == "datatable":
            status = await art.generate_data_table(notebook_id, language=lang, instructions=instr)
        elif studio_type == "infographic":
            status = await art.generate_infographic(
                notebook_id, language=lang, instructions=instr,
                orientation=opts.get("orientation"), detail_level=opts.get("detail"))
        else:
            raise ValueError(f"ไม่รู้จักชนิดสื่อ: {studio_type}")

        final = await art.wait_for_completion(notebook_id, status.task_id, timeout=timeout)
        if getattr(final, "is_complete", False):
            return {"ok": True, "error": None}
        return {"ok": False, "error": str(getattr(final, "error", None) or "สร้างไม่สำเร็จ")}


def download_options(kind: str) -> list[str]:
    """รูปแบบไฟล์ที่เลือกได้ตอนดาวน์โหลด (ตัวแรกคือค่าเริ่มต้น)"""
    return {
        "QUIZ": ["json", "markdown", "html"],
        "FLASHCARDS": ["json", "markdown", "html"],
        "SLIDE_DECK": ["pdf", "pptx"],
    }.get(kind, [_FILE_INFO[kind][0]])


_EXT = {"markdown": "md"}
_MIME = {"json": "application/json", "markdown": "text/markdown", "md": "text/markdown",
         "html": "text/html", "pdf": "application/pdf",
         "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}


async def download_artifact(notebook_id: str, art: ArtifactInfo, fmt: str | None = None):
    """คืน (bytes, ชื่อไฟล์, mime)"""
    kind = art.kind
    default_ext, default_mime = _FILE_INFO[kind]
    fmt = fmt or default_ext
    ext = _EXT.get(fmt, fmt)
    mime = _MIME.get(fmt, default_mime)

    with tempfile.TemporaryDirectory() as td:
        out = str(Path(td) / f"out.{ext}")
        async with NotebookLMClient.from_storage() as client:
            a = client.artifacts
            if kind == "AUDIO":
                await a.download_audio(notebook_id, out, art.id)
            elif kind == "VIDEO":
                await a.download_video(notebook_id, out, art.id)
            elif kind == "REPORT":
                await a.download_report(notebook_id, out, art.id)
            elif kind == "QUIZ":
                await a.download_quiz(notebook_id, out, art.id, output_format=fmt)
            elif kind == "FLASHCARDS":
                await a.download_flashcards(notebook_id, out, art.id, output_format=fmt)
            elif kind == "SLIDE_DECK":
                await a.download_slide_deck(notebook_id, out, art.id, output_format=fmt)
            elif kind == "INFOGRAPHIC":
                await a.download_infographic(notebook_id, out, art.id)
            elif kind == "DATA_TABLE":
                await a.download_data_table(notebook_id, out, art.id)
            elif kind == "MIND_MAP":
                await a.download_mind_map(notebook_id, out, art.id)
            else:
                raise ValueError(f"ดาวน์โหลดชนิด {kind} ไม่ได้")
        data = Path(out).read_bytes()
    return data, f"{_safe_filename(art.title, 'artifact')}.{ext}", mime


def mind_map_tree(data: bytes) -> dict | None:
    """อ่าน JSON ของ mind map ที่ดาวน์โหลดมา (คืน None ถ้าอ่านไม่ได้)"""
    try:
        return json.loads(data.decode("utf-8"))
    except Exception:
        return None


def tree_to_markdown(node: dict, depth: int = 0) -> str:
    """แปลงต้นไม้ mind map เป็นรายการซ้อนชั้น (ใช้แสดงผลใน st.markdown)"""
    name = str(node.get("name") or node.get("title") or node.get("label") or "").strip()
    lines = [f"{'  ' * depth}- {name}"] if name else []
    for child in node.get("children") or node.get("nodes") or []:
        if isinstance(child, dict):
            lines.append(tree_to_markdown(child, depth + (1 if name else 0)))
    return "\n".join(l for l in lines if l)


# =========================================================
# โควตา
# =========================================================
_TH_MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
_TH_TZ = timezone(timedelta(hours=7))
WINDOW_TITLES = {
    "FIVE_HOUR": "ปริมาณการใช้ AI ปัจจุบัน",
    "WEEKLY": "ขีดจำกัดรายสัปดาห์",
}
ACTION_NAMES = {
    "AUDIO_OVERVIEW": "ภาพรวมแบบเสียง", "VIDEO_OVERVIEW": "ภาพรวมแบบวิดีโอ", "BREAKDOWNS_VIDEO": "วิดีโออธิบาย",
    "SHORTS_VIDEO": "วิดีโอสั้น", "INFOGRAPHIC": "อินโฟกราฟิก", "SLIDES": "ชุดสไลด์", "REPORTS": "รายงาน",
    "TABLES": "ตารางข้อมูล", "FLASHCARDS": "แฟลชการ์ด", "QUIZ": "แบบทดสอบ", "MINDMAP": "แผนผังความคิด",
    "DEEP_RESEARCH": "ค้นคว้าเชิงลึก", "FAST_RESEARCH": "ค้นคว้าอย่างรวดเร็ว", "QNA": "ถาม–ตอบ",
}


def _th_local(dt: datetime) -> datetime:
    return dt.astimezone(_TH_TZ) if dt.tzinfo else dt.replace(tzinfo=_TH_TZ)


def format_reset(resets_at: Any, now: datetime | None = None) -> str | None:
    """ข้อความเวลารีเซ็ตแบบเดียวกับหน้า NotebookLM (เวลาไทย)
    วันเดียวกัน -> "รีเซ็ตเวลา 12:28"; วันอื่น -> "รีเซ็ตในวันที่ 6 พ.ย. เวลา 10:28" พร้อมเวลาที่เหลือ"""
    if not isinstance(resets_at, datetime):
        return None
    r = _th_local(resets_at)
    n = _th_local(now) if now else datetime.now(_TH_TZ)
    text = (f"รีเซ็ตเวลา {r:%H:%M}" if r.date() == n.date()
            else f"รีเซ็ตในวันที่ {r.day} {_TH_MONTHS[r.month - 1]} เวลา {r:%H:%M}")
    left = int((r - n).total_seconds() // 60)
    if left > 0:
        d, rest = divmod(left, 1440)
        h, m = divmod(rest, 60)
        parts = (f"{d} วัน " if d else "") + (f"{h} ชม. " if h else "") + (f"{m} นาที" if not d else "")
        text += f" (อีก {parts.strip()})"
    return text


def describe_window(w: dict, now: datetime | None = None) -> dict:
    """จัดข้อมูลช่วงโควตาให้พร้อมแสดง: title, used (0-100), remaining, reset"""
    used = w.get("used")
    used = 0.0 if used is None else float(used)
    rem = w.get("remaining")
    rem = max(0.0, 100.0 - used) if rem is None else float(rem)
    return {
        "title": WINDOW_TITLES.get(w.get("kind", ""), w.get("kind", "") or "โควตา"),
        "used": min(max(used, 0.0), 100.0),
        "remaining": min(max(rem, 0.0), 100.0),
        "reset": format_reset(w.get("resets_at"), now),
    }


async def get_usage() -> dict | None:
    """โควตาการใช้งานของบัญชี (None ถ้าบัญชีไม่เปิดตัวนับ/ดึงไม่ได้)"""
    try:
        async with NotebookLMClient.from_storage() as client:
            u = await client.settings.get_usage()
    except Exception:
        return None
    status = getattr(getattr(u, "status", None), "name", "")
    if status == "DISABLED":
        return None
    windows = []
    for w in getattr(u, "windows", []) or []:
        windows.append({
            "kind": getattr(getattr(w, "kind", None), "name", str(getattr(w, "kind", ""))),
            "used": getattr(w, "used_percent", None),
            "remaining": getattr(w, "remaining_percent", None),
            "resets_at": getattr(w, "resets_at", None),
        })
    blocked = []
    for a in getattr(u, "actions", []) or []:
        if getattr(a, "has_sufficient_quota", True) is False:
            name = getattr(getattr(a, "kind", None), "name", "")
            blocked.append(ACTION_NAMES.get(name, name))
    return {"windows": windows, "blocked": blocked, "fetched_at": datetime.now(_TH_TZ)}

