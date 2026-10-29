"""
scripts/wake_app.py — เปิดหน้าเว็บด้วยเบราว์เซอร์จริง และกดปุ่มปลุกถ้าแอปหลับ

Streamlit ฟรีจะหลับเมื่อไม่มีคนเข้านาน การเรียก HTTP เฉยๆ ไม่ปลุกแอป ต้องเปิดผ่านเบราว์เซอร์
ใช้โดย .github/workflows/wake.yml  (ตัวแปร APP_URL)
"""
import os
import sys

from playwright.sync_api import sync_playwright

APP_URL = os.environ.get("APP_URL", "https://rtaf-supply.streamlit.app")
WAKE_TEXTS = ("get this app back up", "wake", "ปลุก")
READY_SELECTOR = '[data-testid="stChatInput"], [data-testid="stSidebar"], [data-testid="stApp"]'


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(APP_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
        for btn in page.get_by_role("button").all():
            label = (btn.inner_text() or "").lower()
            if any(t in label for t in WAKE_TEXTS):
                print("แอปหลับอยู่ กดปุ่มปลุก")
                btn.click()
                page.wait_for_timeout(45000)
                break
        try:
            page.wait_for_selector('[data-testid="stApp"]', timeout=60000)
            page.wait_for_selector('[data-testid="stSidebar"], [data-testid="stChatInput"], [data-testid="stMain"]',
                                   timeout=60000)
            print("แอปพร้อมใช้งาน")
            code = 0
        except Exception as e:  # noqa: BLE001
            print(f"แอปยังไม่พร้อม: {type(e).__name__}")
            code = 1
        browser.close()
        return code


if __name__ == "__main__":
    sys.exit(main())
