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

# กัน HTML Injection: คำตอบ AI ไม่ควรมีแท็ก HTML ดิบหลุดออกมาได้ (หน้าเว็บเรนเดอร์ด้วย unsafe_allow_html=True)
xss = render_answer('แจ้งเตือน <script>alert(1)</script> ตามข้อ [1] & ข้อ 2', refs)
assert "<script>" not in xss and "&lt;script&gt;alert(1)&lt;/script&gt;" in xss, xss
assert "ข้อ 2" in xss and "&amp;" in xss      # ตัวอักษรธรรมดา/& ยังอยู่ครบ ไม่หาย
assert 'class="cite-n"' in xss                # เลขอ้างอิง [1] ยังถูกแทนที่เป็นชิปได้ปกติ

assert ft.strip_markdown("**บทที่ ๒** คือเรื่อง _การจำแนก_") == "บทที่ ๒ คือเรื่อง การจำแนก"
assert ft.strip_markdown("## หัวข้อ\n- ข้อหนึ่ง\n* ข้อสอง") == "หัวข้อ\n• ข้อหนึ่ง\n• ข้อสอง"
assert ft.strip_markdown("ตัวแปร snake_case ไม่ใช่ตัวเอียง") == "ตัวแปร snake_case ไม่ใช่ตัวเอียง"

tree = {"name": "พัสดุ", "children": [{"name": "จัดซื้อ", "children": [{"name": "เฉพาะเจาะจง"}]}, {"name": "คลัง"}]}
assert ft.tree_to_markdown(tree) == "- พัสดุ\n  - จัดซื้อ\n    - เฉพาะเจาะจง\n  - คลัง", repr(ft.tree_to_markdown(tree))
assert ft.mind_map_tree(b'{"a":1}') == {"a": 1} and ft.mind_map_tree(b"xx") is None
assert ft.download_options("SLIDE_DECK") == ["pdf", "pptx"] and ft.download_options("AUDIO") == ["m4a"]
assert ft._safe_filename("../a/b:c.pdf") == "a_b_c.pdf" or "/" not in ft._safe_filename("../a/b:c.pdf")
print("unit OK")
