"""
citations.py — แปลงเลขอ้างอิง [1], [1, 2], [1-3] ในคำตอบของ NotebookLM
ให้เป็นชิปที่ชี้/กดแล้วเห็นชื่อไฟล์ต้นฉบับ + ข้อความที่ถูกอ้างอิง (เหมือน NotebookLM)

ไม่พึ่ง streamlit จึงทดสอบแยกได้
"""
import html
import re

# [1]  [1, 2]  [1-3]  [1, 3-5]
CITE_RE = re.compile(r"\[(\d+(?:\s*[,\-–]\s*\d+)*)\]")

MAX_PASSAGE_CHARS = 700
MAX_CONTEXT_CHARS = 1200


# ---------------------------------------------------------
# CSS (ฉีดครั้งเดียวด้วย st.markdown(CITATION_CSS, unsafe_allow_html=True))
# ---------------------------------------------------------
CITATION_CSS = """
<style>
.cite{position:relative;display:inline-block;margin:0 1px;}
.cite-n{display:inline-block;min-width:1.4em;padding:0 .35em;border-radius:1em;
  background:#e8f0fe;color:#1a56c4;font-size:.78em;font-weight:600;font-style:normal;
  text-align:center;cursor:pointer;line-height:1.5;border:1px solid #c6d8fb;}
.cite-n:hover{background:#d2e3fc;}
.cite-tip{display:none;position:absolute;z-index:99999;left:0;top:100%;
  width:min(440px,82vw);max-height:340px;overflow-y:auto;padding:.8rem .95rem;
  background:#fff;color:#222;border:1px solid #d0d7de;border-radius:.7rem;
  box-shadow:0 8px 28px rgba(0,0,0,.20);font-size:.86rem;line-height:1.6;
  font-style:normal;font-weight:400;text-align:left;white-space:normal;}
.cite:hover .cite-tip,.cite:focus-within .cite-tip,.cite:focus .cite-tip{display:block;}
.cite-title{display:block;font-weight:700;color:#1a3d7c;margin:0 0 .25rem 0;}
.cite-text{display:block;margin:0 0 .6rem 0;}
.cite-text:last-child{margin-bottom:0;}
.cite-text mark{background:#fff3b0;padding:0 .1em;border-radius:.15em;}
.src-card{border-left:4px solid #4CAF50;background:rgba(76,175,80,.07);
  padding:.55rem .8rem;margin:.4rem 0;border-radius:0 .4rem .4rem 0;font-size:.9rem;line-height:1.6;}
.src-card .src-title{font-weight:700;}
.src-card mark{background:#fff3b0;color:#222;padding:0 .1em;border-radius:.15em;}
</style>
"""


_SPECIAL = {"*": "&#42;", "_": "&#95;", "`": "&#96;", "[": "&#91;", "]": "&#93;",
            "$": "&#36;", "~": "&#126;", "|": "&#124;", "#": "&#35;", "\\": "&#92;"}


def esc(text: str) -> str:
    """escape HTML และอักขระที่ markdown/LaTeX ของ Streamlit จะตีความผิด (แปลงทีละตัว ไม่ escape ซ้ำ)"""
    t = "".join(_SPECIAL.get(ch) or html.escape(ch, quote=True)
                for ch in str(text or "").strip())
    # ห้ามมีบรรทัดว่าง ไม่งั้น markdown จะตัดบล็อก HTML
    return re.sub(r"\s*\n\s*", "<br>", t)


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + " …"


def expand_numbers(spec: str) -> list[int]:
    """'1, 3-5' -> [1, 3, 4, 5]"""
    nums: list[int] = []
    for part in spec.split(","):
        found = [int(x) for x in re.findall(r"\d+", part)]
        if len(found) == 2 and re.search(r"[\-–]", part):
            a, b = found
            if a <= b and b - a < 50:
                nums.extend(range(a, b + 1))
                continue
        nums.extend(found)
    return nums


def group_references(refs: list[dict]) -> dict[int, list[dict]]:
    """จัดกลุ่ม references ตาม citation_number (เลขเดียวอาจมีหลายท่อน)"""
    grouped: dict[int, list[dict]] = {}
    for r in refs:
        grouped.setdefault(int(r["number"]), []).append(r)
    return grouped


def _passage_html(r: dict, tip: bool) -> str:
    """ข้อความต้นฉบับ: ใช้บริบทรอบข้อความถ้ามี และไฮไลต์ส่วนที่ถูกอ้างอิง"""
    cited = (r.get("cited_text") or "").strip()
    ctx = (r.get("context") or "").strip()
    if ctx:
        body = esc(_truncate(ctx, MAX_CONTEXT_CHARS))
        if cited:
            c_esc = esc(cited)
            if c_esc in body:
                body = body.replace(c_esc, f"<mark>{c_esc}</mark>", 1)
    else:
        body = esc(_truncate(cited, MAX_PASSAGE_CHARS))
    return body


def _chip(number: int, passages: list[dict]) -> str:
    inner = []
    last_title = None
    for r in passages:
        title = r.get("title") or "แหล่งข้อมูล"
        if title != last_title:
            inner.append(f'<span class="cite-title">{esc(title)}</span>')
            last_title = title
        inner.append(f'<span class="cite-text">{_passage_html(r, True)}</span>')
    # tabindex ทำให้แตะบนมือถือแล้วค้างได้
    return (f'<span class="cite" tabindex="0">'
            f'<span class="cite-n">{number}</span>'
            f'<span class="cite-tip">{"".join(inner)}</span></span>')


def render_answer(answer: str, refs: list[dict]) -> str:
    """แทนที่ [n] ในคำตอบด้วยชิปที่เปิดดูแหล่งข้อมูลได้"""
    grouped = group_references(refs)

    def repl(m: re.Match) -> str:
        nums = expand_numbers(m.group(1))
        chips = []
        for n in nums:
            if n in grouped:
                chips.append(_chip(n, grouped[n]))
            else:
                chips.append(f'<span class="cite-n">{n}</span>')
        return "".join(chips)

    return CITE_RE.sub(repl, answer)


def render_sources_html(refs: list[dict]) -> str:
    """รายการแหล่งข้อมูลทั้งหมด (ใส่ใน expander ใต้คำตอบ) — ใช้ได้บนมือถือด้วย"""
    out = []
    for n, passages in sorted(group_references(refs).items()):
        for r in passages:
            title = r.get("title") or "แหล่งข้อมูล"
            out.append(
                f'<div class="src-card"><span class="src-title">[{n}] {esc(title)}</span>'
                f'<br>{_passage_html(r, False)}</div>'
            )
    return "".join(out)
