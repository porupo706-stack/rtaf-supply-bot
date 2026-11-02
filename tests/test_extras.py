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

# ---- ถามแบบแยกผู้ใช้
import asyncio, threading, types
msgs = [{"role": "user", "content": "q1"}, {"role": "assistant", "content": "<b>html</b>", "answer_plain": "a1 [1]"},
        {"role": "user", "content": "q2"}, {"role": "assistant", "content": "x"}]      # ข้อสุดท้ายไม่มี answer_plain
assert ft.history_pairs(msgs) == [("q1", "a1 [1]")]
assert ft.build_prompt("คำถามใหม่", []) == "คำถามใหม่" and ft.build_prompt("คำถามใหม่", None) == "คำถามใหม่"
p = ft.build_prompt("ข้อใหม่", [("ก", "ตอบก [1, 2] " + "ย" * 900)] * 5)
assert p.count("ถาม: ก") == 3 and "[1, 2]" not in p and "ข้อใหม่" in p.rsplit("คำถามปัจจุบัน:", 1)[1]
assert "ย" * 501 not in p


class FakeServer:
    """จำลอง NotebookLM: ask ที่ไม่ระบุ conversation_id จะต่อท้ายบทสนทนาล่าสุดของสมุดบันทึกร่วมกัน"""
    def __init__(self, leftover=0):
        self.turns = [("เก่า", "เก่า")] * leftover
        self.cid = "old" if leftover else None
        self.n = 0; self.active = 0; self.max_active = 0; self.seen = []
        outer = self
        class Chat:
            async def get_conversation_id(self, nb): return outer.cid
            async def delete_conversation(self, nb, cid):
                assert cid == outer.cid; outer.cid, outer.turns = None, []
            async def ask(self, nb, q, **kw):
                assert "conversation_id" not in kw
                outer.active += 1; outer.max_active = max(outer.max_active, outer.active)
                outer.seen.append((q, len(outer.turns)))           # ก่อนถามมีประวัติของคนอื่นค้างกี่ข้อ
                await asyncio.sleep(0.02)
                if outer.cid is None:
                    outer.n += 1; outer.cid = f"c{outer.n}"
                outer.turns.append((q, "a")); outer.active -= 1
                return types.SimpleNamespace(answer="ตอบ " + q, conversation_id=outer.cid)
        self.chat = Chat()


ft._fresh = False
srv = FakeServer(leftover=7)                              # มีบทสนทนาเก่าค้างอยู่แล้ว
def worker(i):
    asyncio.run(ft.ask_isolated(srv, "nb", f"q{i}"))
ths = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
[t.start() for t in ths]; [t.join() for t in ths]
assert srv.max_active == 1, "ต้องถามทีละคำถาม"
assert [n for _, n in srv.seen] == [0] * 6, srv.seen      # ทุกคำถามเริ่มจากบทสนทนาว่าง (ไม่เห็นของคนอื่น/ของเก่า)
assert srv.cid is None and ft._fresh is True              # ลบทิ้งหลังตอบ

class FlakyDelete(FakeServer):
    def __init__(self):
        super().__init__(); real = self.chat.delete_conversation; self.fail = True
        async def bad(nb, cid):
            if self.fail: raise RuntimeError("net")
            await real(nb, cid)
        self.chat.delete_conversation = bad
ft._fresh = True
srv = FlakyDelete()
r = asyncio.run(ft.ask_isolated(srv, "nb", "x"))           # ลบพลาดก็ยังได้คำตอบ แต่ต้องรู้ว่าสกปรก
assert r.answer == "ตอบ x" and ft._fresh is False
srv.fail = False
asyncio.run(ft.ask_isolated(srv, "nb", "y"))               # คำถามถัดไปเคลียร์ของค้างก่อนถาม
assert srv.seen[-1] == ("y", 0) and srv.cid is None and ft._fresh is True

# ---- โควตา (แสดงแบบเดียวกับ NotebookLM)
from datetime import timezone, timedelta
th = timezone(timedelta(hours=7))
now = datetime(2026, 11, 2, 10, 40, tzinfo=th)
assert ft.format_reset(datetime(2026, 11, 2, 12, 28, tzinfo=th), now) == "รีเซ็ตเวลา 12:28 (อีก 1 ชม. 48 นาที)"
assert ft.format_reset(datetime(2026, 11, 6, 10, 28, tzinfo=th), now).startswith("รีเซ็ตในวันที่ 6 พ.ย. เวลา 10:28 (อีก 3 วัน")
assert ft.format_reset(datetime(2026, 11, 2, 5, 28, tzinfo=timezone.utc), now).startswith("รีเซ็ตเวลา 12:28")   # UTC -> เวลาไทย
assert ft.format_reset(None, now) is None and ft.format_reset("x", now) is None
d = ft.describe_window({"kind": "FIVE_HOUR", "used": 70.4, "remaining": None, "resets_at": None}, now)
assert d["title"] == "ปริมาณการใช้ AI ปัจจุบัน" and round(d["used"]) == 70 and round(d["remaining"]) == 30 and d["reset"] is None
assert ft.describe_window({"kind": "WEEKLY", "used": 16, "remaining": 84})["title"] == "ขีดจำกัดรายสัปดาห์"
assert ft.describe_window({"kind": "X", "used": 150})["used"] == 100.0 and ft.describe_window({"kind": "X"})["used"] == 0.0
print("extras OK")
