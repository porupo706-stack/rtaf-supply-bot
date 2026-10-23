import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import features as ft
from citations import render_answer

assert ft.check_admin_password("abc", "abc")
assert not ft.check_admin_password("abd", "abc")
assert not ft.check_admin_password("", "")          # ไม่ได้ตั้งรหัส = ปฏิเสธ
assert not ft.check_admin_password("x", "")

refs = [{"number": 1, "source_id": "s1", "title": "ระเบียบ.pdf", "cited_text": "ข้อ 5 วงเงิน", "context": ""}]
html = render_answer("วงเงินคือ 100,000 บาท [1]", refs)
plain = ft.strip_html(html)
assert "[1]" in plain and "<" not in plain and "ข้อ 5" not in plain, plain

md = ft.chat_to_markdown([
    {"role": "user", "content": "วงเงินเท่าไร"},
    {"role": "assistant", "content": html, "references": refs},
])
assert "ระเบียบ.pdf" in md and "ข้อ 5 วงเงิน" in md and "<span" not in md

tree = {"name": "พัสดุ", "children": [{"name": "จัดซื้อ", "children": [{"name": "เฉพาะเจาะจง"}]}, {"name": "คลัง"}]}
assert ft.tree_to_markdown(tree) == "- พัสดุ\n  - จัดซื้อ\n    - เฉพาะเจาะจง\n  - คลัง", repr(ft.tree_to_markdown(tree))
assert ft.mind_map_tree(b'{"a":1}') == {"a": 1} and ft.mind_map_tree(b"xx") is None
assert ft.download_options("SLIDE_DECK") == ["pdf", "pptx"] and ft.download_options("AUDIO") == ["m4a"]
assert ft._safe_filename("../a/b:c.pdf") == "a_b_c.pdf" or "/" not in ft._safe_filename("../a/b:c.pdf")
print("unit OK")
