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
from dataclasses import dataclass
from datetime import datetime
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


def chat_to_markdown(messages: list[dict], title: str = "บทสนทนา ผู้ช่วยงานพัสดุ ทอ.") -> str:
    """แปลงประวัติแชทเป็น Markdown พร้อมรายการแหล่งอ้างอิงท้ายแต่ละคำตอบ"""
    lines = [f"# {title}", f"_ส่งออกเมื่อ {datetime.now():%d/%m/%Y %H:%M}_", ""]
    for m in messages:
        if m["role"] == "user":
            lines += [f"## 🙋 คำถาม", m["content"], ""]
            continue
        lines += ["## 🤖 คำตอบ", strip_html(m["content"]), ""]
        refs = m.get("references") or []
        if refs:
            lines.append("**แหล่งอ้างอิง**")
            seen = set()
            for r in sorted(refs, key=lambda x: int(x.get("number") or 0)):
                key = (r.get("number"), r.get("source_id"), r.get("cited_text"))
                if key in seen:
                    continue
                seen.add(key)
                cited = (r.get("cited_text") or "").strip().replace("\n", " ")
                lines.append(f"- [{r.get('number')}] {r.get('title') or 'แหล่งข้อมูล'}: “{cited[:300]}”")
            lines.append("")
    return "\n".join(lines)


async def save_chat_as_note(notebook_id: str, messages: list[dict], title: str | None = None) -> str:
    """บันทึกทั้งบทสนทนาเป็น note ใน notebook (ผู้ดูแลเท่านั้น) คืน note id"""
    title = title or f"บทสนทนา {datetime.now():%d/%m/%Y %H:%M}"
    async with NotebookLMClient.from_storage() as client:
        note = await client.notes.create(notebook_id, title, chat_to_markdown(messages, title))
    return note.id


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


def resolve_scope(sources: list[SourceInfo], groups: dict[str, list[str]] | None = None,
                  group: str | None = None, titles: list[str] | None = None) -> list[str] | None:
    """คืนรายการ source id ที่จะให้ค้น; None = ค้นทุกเอกสาร

    group  = ชื่อหมวดใน groups (หมวด -> คำที่ต้องมีในชื่อไฟล์ อย่างน้อยหนึ่งคำ)
    titles = เลือกเป็นรายไฟล์ (ชื่อไฟล์ตรงตัว) ถ้าเลือกทั้งสองแบบจะใช้ไฟล์ที่เข้าทั้งคู่
    """
    ids = {s.id for s in sources}
    if group and groups and group in groups:
        words = [w.lower() for w in groups[group] if w]
        ids &= {s.id for s in sources if any(w in s.title.lower() for w in words)}
    if titles:
        ids &= {s.id for s in sources if s.title in set(titles)}
    if len(ids) == len(sources):
        return None
    return [s.id for s in sources if s.id in ids]


def format_feedback(question: str, answer: str, rating: str, comment: str = "") -> tuple[str, str]:
    """(หัวข้อ, เนื้อหา) ของโน้ตข้อสังเกตจากผู้ใช้"""
    mark = "👎 ไม่ตรง/ไม่ช่วย" if rating == "down" else "👍 ตรง/ช่วยได้"
    title = f"ข้อสังเกต {mark} {datetime.now():%d/%m/%Y %H:%M}"
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
    return {"windows": windows}
