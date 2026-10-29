import sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import features as ft
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
import run_eval as ev

# ---- วันที่ พ.ศ.
assert ft.thai_date(datetime(2026, 10, 29)) == "29/10/2569"
assert ft.thai_date(1798502400) == ft.thai_date(1798502400 * 1000)   # วินาที = มิลลิวินาที
assert ft.thai_date(None) is None and ft.thai_date("x") is None
S = ft.SourceInfo
src = [S("1", "ระเบียบพัสดุ 2560.pdf", "PDF", True, 10, datetime(2026, 1, 5)),
       S("2", "คู่มือเบิกจ่าย.pdf", "PDF", True, 10, datetime(2026, 9, 1)),
       S("3", "แบบฟอร์ม.docx", "DOC", True, 10, None)]
assert ft.latest_update(src) == "01/09/2569"
assert ft.latest_update([S("x", "t", "k", True, 1, None)]) is None

# ---- ขอบเขตการค้นหา
groups = {"เบิกจ่าย": ["เบิกจ่าย", "แบบฟอร์ม"], "ระเบียบ": ["ระเบียบ"]}
assert ft.resolve_scope(src) is None
assert ft.resolve_scope(src, groups, "ระเบียบ") == ["1"]
assert ft.resolve_scope(src, groups, "เบิกจ่าย") == ["2", "3"]
assert ft.resolve_scope(src, groups, None, ["แบบฟอร์ม.docx"]) == ["3"]
assert ft.resolve_scope(src, groups, "ระเบียบ", ["แบบฟอร์ม.docx"]) == []
assert ft.resolve_scope(src, groups, "ไม่มีหมวดนี้") is None      # หมวดไม่รู้จัก = ไม่กรอง

# ---- ข้อสังเกต
title, body = ft.format_feedback("ถามอะไร", '<b>ตอบ</b> <span class="cite"><span class="cite-n">1</span></span>', "down", " ไม่ตรง ")
assert "👎" in title and "ถามอะไร" in body and "<" not in body and "ความเห็นผู้ใช้: ไม่ตรง" in body
assert "👍" in ft.format_feedback("q", "a", "up")[0]

# ---- ตัวตรวจคำตอบ
assert ev.score_case({"q": "x"}, "อะไรก็ได้", 0)[0] == "MANUAL"
assert ev.score_case({"q": "x", "expect_any": ["100,000"]}, "วงเงิน 100,000 บาท [1]", 1)[0] == "PASS"
st, why = ev.score_case({"q": "x", "expect_any": ["500,000"], "min_citations": 1}, "วงเงิน 100,000", 0)
assert st == "FAIL" and len(why) == 2
assert ev.score_case({"q": "x", "expect_all": ["ก", "ข"]}, "ก เท่านั้น", 3)[0] == "FAIL"
assert ev.normalize("ข้อ [1, 2] ตก  ลง [3-4]") == "ข้อ ตก ลง"
res = [{"q": "a", "answer": "x", "citations": 1, "status": "PASS", "why": []},
       {"q": "b", "answer": "y", "citations": 0, "status": "FAIL", "why": ["เหตุ"]},
       {"q": "c", "answer": "z", "citations": 0, "status": "MANUAL", "why": []}]
assert ev.summarize(res)["accuracy"] == 0.5 and "ความแม่น 50%" in ev.render_report(res)
print("extras OK")
