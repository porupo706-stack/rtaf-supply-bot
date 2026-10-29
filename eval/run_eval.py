"""
eval/run_eval.py — ชุดคำถามทดสอบความแม่นของระบบ (รันบนเครื่องผู้ดูแล)

    python eval/run_eval.py --questions eval/questions.json --notebook รหัสสมุดบันทึก
    (ใช้โปรไฟล์กุญแจเดียวกับที่ออกด้วย setup_token.py; ระบุได้ด้วย --profile ชื่อ)

ไฟล์คำถาม (JSON รายการ):
  {"q": "คำถาม",
   "expect_any": ["คำ/ตัวเลขที่ต้องมีอย่างน้อย 1 คำ"],
   "expect_all": ["คำที่ต้องมีครบทุกคำ"],
   "min_citations": 1}
ข้อที่ไม่ใส่ expect_* จะแสดงคำตอบให้ตรวจด้วยมือ

ใส่คำตอบที่ถูกต้องจากระเบียบจริงเองเท่านั้น (ตัวอย่างในไฟล์ .example เป็นเพียงรูปแบบ)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

_CITE = re.compile(r"\[\d+(?:\s*[,\-–]\s*\d+)*\]")


def normalize(text: str) -> str:
    """ตัดเลขอ้างอิง [1] และช่องว่างซ้ำ ลดตัวพิมพ์ เพื่อเทียบคำ"""
    return re.sub(r"\s+", " ", _CITE.sub("", text or "")).strip().lower()


def score_case(case: dict, answer: str, n_citations: int) -> tuple[str, list[str]]:
    """คืน (สถานะ, เหตุผล) สถานะ = PASS | FAIL | MANUAL"""
    any_w = [w for w in case.get("expect_any", []) if w]
    all_w = [w for w in case.get("expect_all", []) if w]
    min_c = int(case.get("min_citations", 0) or 0)
    if not (any_w or all_w or min_c):
        return "MANUAL", ["ไม่ได้กำหนดเกณฑ์ ต้องตรวจด้วยมือ"]
    text, why = normalize(answer), []
    if any_w and not any(normalize(w) in text for w in any_w):
        why.append(f"ไม่พบคำใดเลยใน {any_w}")
    missing = [w for w in all_w if normalize(w) not in text]
    if missing:
        why.append(f"ขาดคำ {missing}")
    if n_citations < min_c:
        why.append(f"อ้างอิง {n_citations} จุด น้อยกว่าที่กำหนด {min_c}")
    return ("FAIL" if why else "PASS"), why


def summarize(results: list[dict]) -> dict:
    out = {"PASS": 0, "FAIL": 0, "MANUAL": 0}
    for r in results:
        out[r["status"]] += 1
    graded = out["PASS"] + out["FAIL"]
    out["accuracy"] = (out["PASS"] / graded) if graded else None
    return out


def render_report(results: list[dict]) -> str:
    s = summarize(results)
    acc = f"{s['accuracy']:.0%}" if s["accuracy"] is not None else "-"
    lines = [f"# ผลทดสอบ {datetime.now():%d/%m/%Y %H:%M}", "",
             f"ผ่าน {s['PASS']} · ไม่ผ่าน {s['FAIL']} · ตรวจมือ {s['MANUAL']} · ความแม่น {acc}", ""]
    for i, r in enumerate(results, 1):
        icon = {"PASS": "✅", "FAIL": "❌", "MANUAL": "🔍"}[r["status"]]
        lines += [f"## {i}. {icon} {r['q']}"]
        lines += [f"- {w}" for w in r["why"]]
        lines += [f"- อ้างอิง {r['citations']} จุด", "", "```", normalize(r["answer"])[:1200], "```", ""]
    return "\n".join(lines)


async def ask_all(notebook_id: str, cases: list[dict], delay: float) -> list[dict]:
    from notebooklm import NotebookLMClient
    results = []
    async with NotebookLMClient.from_storage() as client:
        for case in cases:
            try:
                r = await client.chat.ask(notebook_id, case["q"])
                answer, n = r.answer, len({getattr(x, "citation_number", 0) for x in (r.references or [])})
            except Exception as e:  # noqa: BLE001
                answer, n = f"(ผิดพลาด: {type(e).__name__}: {e})", 0
            status, why = score_case(case, answer, n)
            if answer.startswith("(ผิดพลาด"):
                status, why = "FAIL", ["ถามไม่สำเร็จ"]
            results.append({"q": case["q"], "answer": answer, "citations": n, "status": status, "why": why})
            print(f"{status:6} {case['q'][:70]}", flush=True)
            await asyncio.sleep(delay)
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="รันชุดคำถามทดสอบ")
    ap.add_argument("--questions", required=True)
    ap.add_argument("--notebook", default=os.environ.get("NOTEBOOK_ID", ""))
    ap.add_argument("--profile")
    ap.add_argument("--out", default="eval-report.md")
    ap.add_argument("--delay", type=float, default=3.0, help="หน่วงระหว่างข้อ (วินาที) กันถูกจำกัดอัตรา")
    args = ap.parse_args(argv)
    if not args.notebook:
        print("❌ ต้องระบุ --notebook หรือตั้งตัวแปร NOTEBOOK_ID")
        return 2
    if args.profile:
        os.environ["NOTEBOOKLM_PROFILE"] = args.profile
    cases = json.loads(Path(args.questions).read_text(encoding="utf-8"))
    results = asyncio.run(ask_all(args.notebook, cases, args.delay))
    Path(args.out).write_text(render_report(results), encoding="utf-8")
    s = summarize(results)
    print(f"\nผ่าน {s['PASS']} · ไม่ผ่าน {s['FAIL']} · ตรวจมือ {s['MANUAL']} → {args.out}")
    return 1 if s["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
