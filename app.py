import os
import asyncio
import time
import streamlit as st
import requests as req
from notebooklm import NotebookLMClient
from cryptography.fernet import Fernet, InvalidToken

from citations import CITATION_CSS, render_answer, render_sources_html
from theme import HERO_HTML, LOGO_PATH, THEME_CSS
import features as ft
from auth_setup import MasterTokenSetupError, install_master_token

# =========================================================
# CONFIG — ดึงจาก Secrets ทั้งหมด (ไม่มีข้อมูลสำคัญใน code)
# =========================================================
NOTEBOOK_ID = st.secrets.get("NOTEBOOK_ID", "")

# รหัสผ่านผู้ดูแล — ปลดล็อกการแก้ไขแหล่งข้อมูล / สร้างสื่อ / บันทึกโน้ต
# (ถ้าไม่ตั้งใน Secrets: ผู้ใช้ทั่วไปใช้ได้เฉพาะถาม–ตอบและดาวน์โหลด)
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "")
MAX_LOGIN_ATTEMPTS = 5

# True = ดึงเนื้อหาเต็มของไฟล์มาหาบริบทรอบข้อความที่อ้างอิง (เหมือน NotebookLM แสดงย่อหน้า)
#        ช้าลงเล็กน้อย แต่ได้ข้อความละเอียดกว่า
# False = แสดงเฉพาะข้อความที่ NotebookLM ส่งมาให้ (เร็วกว่า)
SHOW_CONTEXT = True

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="ผู้ช่วยงานพัสดุ ของกองทัพอากาศ (ทอ.)",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "✈️",
    layout="centered",
)

# CSS ของเลขอ้างอิง / การ์ดแหล่งข้อมูล
st.markdown(CITATION_CSS, unsafe_allow_html=True)
st.markdown(THEME_CSS, unsafe_allow_html=True)

# =========================================================
# HEADER
# =========================================================
st.markdown(HERO_HTML, unsafe_allow_html=True)

# =========================================================
# ดึง session จาก GitHub Gist (cache 1 ชั่วโมง)
# =========================================================
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_from_gist() -> str | None:
    gist_id  = st.secrets.get("GIST_ID", "")
    gh_token = st.secrets.get("GITHUB_TOKEN", "")
    enc_key  = st.secrets.get("SESSION_ENC_KEY", "")

    if not all([gist_id, gh_token, enc_key]):
        return None

    try:
        resp = req.get(
            f"https://api.github.com/gists/{gist_id}",
            headers={"Authorization": f"token {gh_token}"},
            timeout=10,
        )
        if resp.status_code != 200:
            return None

        encrypted = resp.json()["files"]["session.enc"]["content"]
        return Fernet(enc_key.encode()).decrypt(encrypted.encode()).decode()

    except (InvalidToken, KeyError, Exception):
        return None


# =========================================================
# ตั้งค่า Auth
# =========================================================
@st.cache_resource(show_spinner=False)
def ensure_master_token(master_json: str, seed_storage_json: str | None) -> str:
    """เตรียม profile แบบ master-token ครั้งเดียวต่อ process (ล้มเหลวจะไม่ถูก cache)"""
    return install_master_token(master_json, seed_storage_json)


def setup_auth() -> bool:
    """ลำดับความสำคัญ: master token (mint cookie เอง) > Gist เดิม > NOTEBOOKLM_AUTH_JSON

    โหมด master token ห้ามมี NOTEBOOKLM_AUTH_JSON ค้างใน environment
    เพราะโหมด inline ปิดการ re-mint ของไลบรารี
    """
    master_json = st.secrets.get("NOTEBOOKLM_MASTER_TOKEN_JSON", "")
    if master_json:
        try:
            ensure_master_token(master_json, fetch_from_gist())
            os.environ.pop("NOTEBOOKLM_AUTH_JSON", None)
            st.session_state["auth_mode"] = "master-token"
            return True
        except MasterTokenSetupError as e:
            st.warning(f"⚠️ ตั้งค่า master token ไม่สำเร็จ — ใช้ session สำรองแทน ({e})")
        except Exception as e:
            st.warning(f"⚠️ master token ใช้ไม่ได้ — ใช้ session สำรองแทน ({type(e).__name__})")

    st.session_state["auth_mode"] = "session"
    auth_json = fetch_from_gist()

    if not auth_json:
        try:
            auth_json = st.secrets["NOTEBOOKLM_AUTH_JSON"]
        except Exception:
            pass

    if not auth_json:
        return False

    os.environ["NOTEBOOKLM_AUTH_JSON"] = auth_json
    return True


def is_auth_error(e: Exception) -> bool:
    keywords = ["auth", "login", "credential", "unauthorized",
                "403", "session", "google", "oauth", "token", "invalid"]
    return any(kw in str(e).lower() for kw in keywords)


def clear_gist_cache():
    fetch_from_gist.clear()


def _hide_vendor_name(text: str) -> str:
    """ซ่อนชื่อผู้ให้บริการเบื้องหลัง ไม่ให้หลุดไปโผล่ในข้อความที่ผู้ใช้เห็น"""
    for vendor in ("NotebookLM", "notebooklm"):
        text = text.replace(vendor, "ระบบฐานความรู้")
    return text


def handle_error(e: Exception, where: str = "ระบบฐานความรู้"):
    """session หมดอายุ -> หน้าแก้ไข / ข้อผิดพลาดอื่น -> แสดงข้อความ"""
    if is_auth_error(e):
        clear_gist_cache()
        st.session_state["auth_expired"] = True
        st.rerun()
    st.error(f"❌ เกิดข้อผิดพลาดในการเชื่อมต่อ{where}")
    st.caption(f"รายละเอียด: {_hide_vendor_name(str(e))}")


# =========================================================
# ตรวจ NOTEBOOK_ID
# =========================================================
if not NOTEBOOK_ID:
    st.error("⚠️ ไม่พบ NOTEBOOK_ID ใน Streamlit Secrets")
    st.info("กรุณาเพิ่ม NOTEBOOK_ID = '...' ใน App settings → Secrets")
    st.stop()

# =========================================================
# NOTEBOOKLM
# =========================================================
async def get_answer(prompt: str, history: list[tuple[str, str]] | None = None,
                     titles: dict[str, str] | None = None) -> dict:
    """คืน {"answer", "next_steps", "references": [ {number, source_id, title, cited_text, context} ]}

    ถามแบบแยกผู้ใช้ (ดู features.ask_isolated): บริบทต่อเนื่องมาจาก history ของผู้ใช้คนนี้เท่านั้น
    titles: ชื่อไฟล์แต่ละแหล่งข้อมูล (จาก cached_sources ที่เรียกไว้ก่อนแล้ว กันดึงรายชื่อซ้ำทุกคำถาม)
    """
    titles = titles or {}
    async with NotebookLMClient.from_storage() as client:
        result = await ft.ask_isolated(client, NOTEBOOK_ID, ft.build_prompt(prompt, history))
        raw_refs = list(getattr(result, "references", None) or [])

        # ดึงเนื้อหาเต็มของแต่ละไฟล์ที่ถูกอ้างอิงพร้อมกัน (แทนการรอทีละไฟล์) เพื่อหาย่อหน้ารอบข้อความอ้างอิง
        fulltexts: dict = {}
        if SHOW_CONTEXT:
            sids = {getattr(r, "source_id", "") or "" for r in raw_refs if getattr(r, "cited_text", "")}
            sids.discard("")
            if sids:
                async def fetch(sid: str):
                    try:
                        return sid, await client.sources.get_fulltext(NOTEBOOK_ID, sid)
                    except Exception:
                        return sid, None
                for sid, full in await asyncio.gather(*(fetch(s) for s in sids)):
                    fulltexts[sid] = full

        refs: list[dict] = []
        for r in raw_refs:
            sid = getattr(r, "source_id", "") or ""
            cited = getattr(r, "cited_text", "") or ""
            context = ""
            full = fulltexts.get(sid)
            if full is not None and cited:
                try:
                    matches = full.find_citation_context(cited)
                    if matches:
                        context = matches[0][0]
                except Exception:
                    pass

            refs.append({
                "number": getattr(r, "citation_number", None) or 0,
                "source_id": sid,
                "title": titles.get(sid, ""),
                "cited_text": cited,
                "context": context,
            })

        next_steps = [getattr(n, "question", "") for n in (getattr(result, "next_steps", None) or [])]

        return {
            "answer": result.answer,
            "next_steps": [q for q in next_steps if q][:3],
            "references": refs,
        }


# =========================================================
# แสดงข้อความแชท (ใช้ทั้งตอนตอบใหม่และตอนแสดงประวัติ)
# =========================================================
@st.cache_data(ttl=600, show_spinner=False)
def _cached_sources_raw(notebook_id: str) -> list[dict]:
    """ดึงรายชื่อเอกสารจริง (cache 10 นาที) เก็บเป็น dict ธรรมดา ไม่ใช่ dataclass
    เพราะ st.cache_data ใช้ pickle เก็บผลลัพธ์ ถ้าแอป hot-reload โค้ดกลางอากาศ
    (เช่นหลัง push ใหม่) คลาส dataclass เดิมกับคลาสหลัง reload จะถือเป็นคนละคลาส
    ทำให้ pickle ล้มเหลวและหน้าเว็บพังทั้งหน้า เก็บเป็น dict จึงไม่มีปัญหานี้"""
    try:
        return [s.__dict__ for s in ft.run(ft.list_sources(notebook_id))]
    except Exception:
        return []


def cached_sources(notebook_id: str) -> list:
    """รายชื่อเอกสารแบบ SourceInfo (ใช้กับตัวเลือกขอบเขตและวันที่อัปเดต); ดึงไม่ได้ = รายการว่าง"""
    return [ft.SourceInfo(**d) for d in _cached_sources_raw(notebook_id)]


DISCLAIMER = "ข้อมูลจากเอกสารที่อัปโหลดไว้ในระบบ โปรดตรวจสอบกับระเบียบฉบับจริงก่อนดำเนินการ"


@st.cache_data(show_spinner=False, max_entries=20)
def _cached_chat_pdf(messages: list) -> bytes | None:
    """สร้าง PDF จากบทสนทนา (cache ตามเนื้อหาบทสนทนา) กันไม่ให้ต้องสร้าง PDF ใหม่
    ทุกครั้งที่หน้าเว็บ rerun (เช่น ถามคำถามใหม่ กดถูกใจ/ไม่ถูกใจ) ทั้งที่บทสนทนาไม่ได้เปลี่ยน"""
    try:
        return ft.chat_to_pdf_bytes(messages)
    except Exception:
        return None


def render_message(message: dict):
    st.markdown(message["content"], unsafe_allow_html=True)
    if message.get("role") == "assistant":
        updated = ft.latest_update(cached_sources(NOTEBOOK_ID)) if NOTEBOOK_ID else None
        st.caption(f"⚠️ {DISCLAIMER}" + (f" · เอกสารอัปเดตล่าสุด {updated}" if updated else ""))
    refs = message.get("references") or []
    if refs:
        with st.expander(f"📚 แหล่งข้อมูลอ้างอิง ({len({r['number'] for r in refs})})"):
            st.markdown(render_sources_html(refs), unsafe_allow_html=True)


# =========================================================
# หน้า "Session หมดอายุ"
# =========================================================
if st.session_state.get("auth_expired", False):
    st.error("🔐 Session Google หมดอายุแล้ว")
    if st.secrets.get("NOTEBOOKLM_MASTER_TOKEN_JSON", ""):
        st.markdown("""
ระบบตั้งค่า **master token** ไว้แล้ว และ mint session ใหม่เองได้ตามปกติ
หากเห็นหน้านี้ แปลว่า master token ถูกเพิกถอน/ใช้ไม่ได้ (เช่น ถูกลบอุปกรณ์ใน Google Account)

**วิธีแก้:**

1. บนคอมพิวเตอร์ รัน `notebooklm login --master-token --account อีเมล`
2. รัน `python export_master_token.py` แล้วคัดลอกผลลัพธ์
3. วางทับ `NOTEBOOKLM_MASTER_TOKEN_JSON` ใน App settings → Secrets
4. กด **Reboot app** แล้วกด "รีเฟรช" ด้านล่าง
""")
    else:
        st.markdown("""
**วิธีแก้ (ทำแค่นี้เดียว):**

1. บนคอมพิวเตอร์ รัน `python setup_token.py`
2. ล็อกอิน Google ในหน้าต่าง Chrome ที่เปิดขึ้นมา แล้วกด I agree
3. วางบรรทัดที่ได้ใน App settings → Secrets แล้ว Reboot app
4. กดปุ่ม **"รีเฟรช"** ด้านล่าง

💡 รายละเอียดดูในคู่มือ README
""")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 รีเฟรช", type="primary", use_container_width=True):
            clear_gist_cache()
            ensure_master_token.clear()
            st.session_state["auth_expired"] = False
            st.rerun()
    with col2:
        if st.button("🗑️ ล้าง cache แล้วลองใหม่", use_container_width=True):
            clear_gist_cache()
            ensure_master_token.clear()
            st.session_state["auth_expired"] = False
            st.rerun()
    st.stop()


# =========================================================
# ตรวจ auth
# =========================================================
if not setup_auth():
    st.error("⚠️ ยังไม่ได้ตั้งค่าการยืนยันตัวตนของระบบฐานความรู้")
    st.info("กรุณาตั้งค่า NOTEBOOKLM_MASTER_TOKEN_JSON (แนะนำ) หรือ GIST_ID + GITHUB_TOKEN + SESSION_ENC_KEY ใน Secrets")
    if st.button("🔄 ลองใหม่", use_container_width=True):
        clear_gist_cache()
        st.rerun()
    st.stop()


# =========================================================
# SIDEBAR: เมนู + ผู้ดูแลระบบ + โควตา
# =========================================================
st.session_state.setdefault("is_admin", False)
st.session_state.setdefault("login_attempts", 0)

PAGES = ["💬 ถาม–ตอบ", "📚 แหล่งข้อมูล"]
page = st.sidebar.radio("เมนู", PAGES, label_visibility="collapsed")

with st.sidebar:
    st.divider()
    if st.session_state["is_admin"]:
        st.success("🔓 โหมดผู้ดูแลระบบ")
        if st.button("ออกจากโหมดผู้ดูแล", use_container_width=True):
            st.session_state["is_admin"] = False
            st.rerun()
        with st.expander("🔑 สถานะระบบ"):
            mode = st.session_state.get("auth_mode")
            st.caption("กุญแจเข้าระบบ: " + ("master token ✅ (ต่ออายุเอง)" if mode == "master-token"
                                            else "session สำรอง ⚠️ (อาจหมดอายุ)"))
            if st.button("🧹 ล้างประวัติแชตในตอนนี้", use_container_width=True):
                try:
                    done = ft.run(ft.clear_history(NOTEBOOK_ID))
                    st.success("ล้างประวัติแล้ว" if done else "ยังไม่มีประวัติให้ล้าง")
                except Exception as e:
                    st.error(f"ล้างไม่สำเร็จ: {type(e).__name__}")
            if st.button("ทดสอบการเชื่อมต่อ", use_container_width=True):
                t0 = time.monotonic()
                try:
                    n = len(ft.run(ft.list_sources(NOTEBOOK_ID)))
                    st.success(f"เชื่อมต่อได้ ({n} เอกสาร, {time.monotonic() - t0:.1f} วินาที)")
                except Exception as e:
                    st.error(f"เชื่อมต่อไม่ได้: {type(e).__name__}")
        with st.expander("📊 โควตาการใช้งาน"):
            if st.button("🔄 ตรวจโควตา", use_container_width=True):
                try:
                    st.session_state["usage"] = ft.run(ft.get_usage()) or {"windows": []}
                except Exception:
                    st.session_state["usage"] = {"windows": []}
            usage = st.session_state.get("usage")
            if usage is None:
                st.caption("กด “ตรวจโควตา” เพื่อดูปริมาณการใช้งานล่าสุด")
            elif not usage["windows"]:
                st.caption("บัญชีนี้ไม่เปิดตัวนับโควตา หรือดึงข้อมูลไม่ได้")
            else:
                for w in usage["windows"]:
                    d = ft.describe_window(w)
                    st.markdown(f"**{d['title']}** — ใช้งาน **{d['used']:.0f}%** (เหลือ {d['remaining']:.0f}%)")
                    st.progress(int(d["used"]))
                    if d["reset"]:
                        st.caption(d["reset"])
                    if d["used"] >= 90:
                        st.warning("ใกล้หมดโควตา คำถาม/การสร้างสื่ออาจถูกจำกัด")
                if usage.get("fetched_at"):
                    st.caption(f"ข้อมูล ณ {usage['fetched_at']:%H:%M} น.")
    else:
        with st.expander("🔐 ผู้ดูแลระบบ"):
            if not ADMIN_PASSWORD:
                st.caption("ยังไม่ได้ตั้ง ADMIN_PASSWORD ใน Secrets")
            elif st.session_state["login_attempts"] >= MAX_LOGIN_ATTEMPTS:
                st.error("ใส่รหัสผิดเกินกำหนด — โหลดหน้าใหม่เพื่อลองอีกครั้ง")
            else:
                pw = st.text_input("รหัสผ่าน", type="password", key="admin_pw")
                if st.button("เข้าสู่ระบบ", use_container_width=True):
                    if ft.check_admin_password(pw, ADMIN_PASSWORD):
                        st.session_state["is_admin"] = True
                        st.session_state["login_attempts"] = 0
                        st.rerun()
                    st.session_state["login_attempts"] += 1
                    st.error("รหัสผ่านไม่ถูกต้อง")

IS_ADMIN = st.session_state["is_admin"]


def admin_only_notice():
    st.info("🔐 ฟังก์ชันนี้สำหรับผู้ดูแลระบบ — เข้าสู่ระบบได้ที่แถบด้านข้าง")


# =========================================================
# หน้า 1: ถาม–ตอบ
# =========================================================
def feedback_buttons(idx: int):
    """👍/👎 ใต้คำตอบล่าสุด: 👎 เก็บเป็นโน้ตใน Notebook ให้ผู้ดูแลไปปรับเอกสาร"""
    msg = st.session_state.messages[idx]
    if msg.get("feedback"):
        st.caption("🙏 ขอบคุณสำหรับความเห็น")
        return
    c1, c2, _ = st.columns([1, 1, 4])
    rating = "up" if c1.button("👍", key=f"fb_up_{idx}", help="คำตอบตรง/ช่วยได้") else \
             "down" if c2.button("👎", key=f"fb_dn_{idx}", help="คำตอบไม่ตรง/ไม่ช่วย แจ้งผู้ดูแล") else None
    if not rating:
        return
    question = next((m["content"] for m in reversed(st.session_state.messages[:idx])
                     if m["role"] == "user"), "")
    msg["feedback"] = rating
    print(f"[feedback] {rating}: {question[:120]!r}", flush=True)   # ปรากฏใน Manage app → Logs
    if rating == "down":
        try:
            ft.run(ft.save_feedback_note(NOTEBOOK_ID, question, msg["content"], rating))
        except Exception:
            st.toast("บันทึกความเห็นไม่สำเร็จ แต่ระบบรับทราบแล้ว", icon="⚠️")
    st.rerun()


def page_chat():
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("pending_prompt", None)

    # ปุ่มจัดการบทสนทนา
    if st.session_state.messages:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🧹 เริ่มบทสนทนาใหม่", use_container_width=True):
                st.session_state.messages = []
                st.rerun()
        with c2:
            pdf_bytes = _cached_chat_pdf(st.session_state.messages)
            st.download_button(
                "📄 ดาวน์โหลด PDF",
                data=pdf_bytes or b"",
                file_name="rtaf-supply-chat.pdf",
                mime="application/pdf",
                disabled=pdf_bytes is None,
                use_container_width=True,
            )

    last_idx = len(st.session_state.messages) - 1
    for i, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            render_message(message)
            if message["role"] == "assistant" and i == last_idx:
                feedback_buttons(i)

    # หน้าแรกไม่มีคำถามแนะนำ (ให้พิมพ์ถามได้ทันที) — แสดงเฉพาะคำถามต่อเนื่องหลังมีคำตอบแล้ว
    suggestions: list[str] = []
    if st.session_state.messages:
        last = st.session_state.messages[-1]
        suggestions = last.get("next_steps") or []
        if suggestions:
            st.caption("💡 คำถามต่อเนื่อง")
    for i, q in enumerate(suggestions):
        if st.button(q, key=f"sugg_{len(st.session_state.messages)}_{i}", use_container_width=True):
            st.session_state.pending_prompt = q
            st.rerun()

    user_input = st.chat_input("พิมพ์คำถามเกี่ยวกับงานพัสดุ...")
    if st.session_state.pending_prompt:
        user_input = st.session_state.pending_prompt
        st.session_state.pending_prompt = None

    if not user_input:
        return

    history = ft.history_pairs(st.session_state.messages)   # ก่อนเพิ่มคำถามปัจจุบัน
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("🔎 กำลังค้นหาข้อมูลจากฐานความรู้..."):
            try:
                titles = {s.id: s.title for s in cached_sources(NOTEBOOK_ID)}
                data = asyncio.run(get_answer(user_input, history, titles))
                msg = {
                    "role": "assistant",
                    "content": render_answer(data["answer"], data["references"]),
                    "answer_plain": data["answer"],
                    "references": data["references"],
                    "next_steps": data["next_steps"],
                }
                render_message(msg)
                st.session_state.messages.append(msg)
            except Exception as e:
                handle_error(e)
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant":
        st.rerun()  # แสดงปุ่มคำถามต่อเนื่องของคำตอบล่าสุด


# =========================================================
# หน้า 2: แหล่งข้อมูล
# =========================================================
def page_sources():
    st.markdown("#### 📚 แหล่งข้อมูลในฐานความรู้")

    if st.button("🔄 โหลดรายการใหม่") or "sources" not in st.session_state:
        with st.spinner("กำลังโหลดรายการ..."):
            try:
                st.session_state["sources"] = ft.run(ft.list_sources(NOTEBOOK_ID))
            except Exception as e:
                handle_error(e)
                return

    sources = st.session_state.get("sources", [])
    st.caption(f"ทั้งหมด {len(sources)} รายการ")

    for s in sources:
        words = f" · {s.words:,} คำ" if s.words else ""
        status = "" if s.ready else " · ⏳ กำลังประมวลผล"
        with st.expander(f"{s.title}"):
            st.caption(f"ประเภท: {s.kind}{words}{status}")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("📝 สรุป + คำสำคัญ", key=f"g_{s.id}", use_container_width=True):
                    try:
                        cache = st.session_state.setdefault("guides", {})
                        if s.id not in cache:
                            with st.spinner("กำลังสรุป..."):
                                cache[s.id] = ft.run(ft.source_guide(NOTEBOOK_ID, s.id))
                        g = cache[s.id]
                        st.markdown(g["summary"] or "_ไม่มีสรุป_")
                        if g["keywords"]:
                            st.caption("คำสำคัญ: " + " · ".join(g["keywords"]))
                    except Exception as e:
                        handle_error(e)
            with c2:
                if st.button("📖 ดูเนื้อหาเต็ม", key=f"f_{s.id}", use_container_width=True):
                    try:
                        text = ft.run(ft.source_fulltext(NOTEBOOK_ID, s.id))
                        st.text_area("เนื้อหา", text, height=300, key=f"t_{s.id}")
                    except Exception as e:
                        handle_error(e)
            if IS_ADMIN:
                if st.button("🗑️ ลบแหล่งข้อมูลนี้", key=f"d_{s.id}"):
                    st.session_state[f"confirm_del_{s.id}"] = True
                if st.session_state.get(f"confirm_del_{s.id}"):
                    st.warning("ลบแล้วกู้คืนไม่ได้ — ยืนยัน?")
                    if st.button("ยืนยันลบ", key=f"dy_{s.id}", type="primary"):
                        try:
                            ft.run(ft.delete_source(NOTEBOOK_ID, s.id))
                            st.session_state.pop(f"confirm_del_{s.id}", None)
                            st.session_state.pop("sources", None)
                            st.rerun()
                        except Exception as e:
                            handle_error(e)

    st.divider()
    st.markdown("#### ➕ เพิ่มแหล่งข้อมูล")
    if not IS_ADMIN:
        admin_only_notice()
        return

    tab_file, tab_url, tab_text = st.tabs(["📄 ไฟล์", "🔗 ลิงก์ / YouTube", "✍️ วางข้อความ"])
    with tab_file:
        files = st.file_uploader(
            "PDF, Word, ข้อความ, Markdown, EPUB, เสียง, รูปภาพ",
            accept_multiple_files=True,
        )
        if files and st.button("อัปโหลด", type="primary", key="up_files"):
            for f in files:
                with st.spinner(f"กำลังอัปโหลด {f.name}..."):
                    try:
                        ft.run(ft.add_file_bytes(NOTEBOOK_ID, f.name, f.getvalue()))
                        st.success(f"เพิ่ม {f.name} แล้ว")
                    except Exception as e:
                        handle_error(e)
            st.session_state.pop("sources", None)
    with tab_url:
        url = st.text_input("URL หน้าเว็บหรือวิดีโอ YouTube")
        if url and st.button("เพิ่มลิงก์", type="primary", key="up_url"):
            with st.spinner("กำลังเพิ่ม..."):
                try:
                    ft.run(ft.add_url(NOTEBOOK_ID, url.strip()))
                    st.success("เพิ่มลิงก์แล้ว")
                    st.session_state.pop("sources", None)
                except Exception as e:
                    handle_error(e)
    with tab_text:
        title = st.text_input("ชื่อเอกสาร")
        body = st.text_area("เนื้อหา", height=200)
        if title and body and st.button("เพิ่มข้อความ", type="primary", key="up_text"):
            with st.spinner("กำลังเพิ่ม..."):
                try:
                    ft.run(ft.add_text(NOTEBOOK_ID, title.strip(), body))
                    st.success("เพิ่มข้อความแล้ว")
                    st.session_state.pop("sources", None)
                except Exception as e:
                    handle_error(e)


# =========================================================
# ROUTER
# =========================================================
if page == PAGES[0]:
    page_chat()
else:
    page_sources()
