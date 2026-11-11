import os
import socket
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import setup_token as st

# ---- หา Chrome
win_env = {"ProgramFiles": r"C:\PF", "ProgramFiles(x86)": r"C:\PF86", "LOCALAPPDATA": r"C:\L"}
c = st.chrome_candidates(win_env, "win32")
assert len(c) == 3 and c[0].endswith("chrome.exe") and "PF" in c[0], c
assert st.chrome_candidates({}, "win32") == []
assert "Google Chrome" in st.chrome_candidates({}, "darwin")[0]
assert st.find_chrome(None, win_env, "win32", exists=lambda p: p == c[1]) == c[1]
assert st.find_chrome("/x/chrome", {}, "linux", exists=lambda p: True) == "/x/chrome"
assert st.find_chrome("/x/chrome", {}, "linux", exists=lambda p: False) is None
assert st.find_chrome(None, {}, "linux", exists=lambda p: False,
                      which=lambda n: "/usr/bin/chromium" if n == "chromium" else None) == "/usr/bin/chromium"
assert st.find_chrome(None, {}, "linux", exists=lambda p: False, which=lambda n: None) is None

# ---- พอร์ต
with socket.socket() as s:
    s.bind(("127.0.0.1", 0)); s.listen(1)
    busy = s.getsockname()[1]
    p = st.find_free_port(busy)            # พอร์ตที่ต้องการไม่ว่าง -> ต้องได้พอร์ตอื่น
    assert p != busy and p > 0
    assert st.wait_for_port(busy, timeout=2) is True
assert st.wait_for_port(st.find_free_port(), timeout=0.6) is False

# ---- คำสั่งล็อกอิน
cmd = st.build_login_cmd("a@b.com", 9222, python="PY")
assert cmd[:4] == ["PY", "-m", "notebooklm", "login"] and "--master-token" in cmd
assert cmd[cmd.index("--account") + 1] == "a@b.com"
assert cmd[cmd.index("--cdp-url") + 1] == "http://localhost:9222" and "--force" not in cmd
assert "--force" in st.build_login_cmd("a@b.com", 1, force=True)

# ---- main ทั้งสายด้วยของจำลอง
class FakeProc:
    terminated = False
    def terminate(self): self.terminated = True
    def wait(self, timeout=None): return 0

def run_main(argv, *, login_code=0, wait_ok=True, chrome="/fake/chrome"):
    calls = {"launch": None, "cmd": None, "export": 0, "proc": FakeProc(), "profile": None}
    orig = st.find_chrome
    st.find_chrome = lambda explicit=None, *a, **k: chrome
    try:
        def launch(ch, port, profile):
            calls["launch"] = (ch, port); calls["profile"] = profile
            assert os.path.isdir(profile)
            return calls["proc"]
        def run_cmd(cmd): calls["cmd"] = cmd; return login_code
        def export(): calls["export"] += 1; return 0
        rc = st.main(argv, launch=launch, run_cmd=run_cmd, export=export,
                     wait=lambda port: wait_ok, ask=lambda prompt: "ask@x.com")
    finally:
        st.find_chrome = orig
    return rc, calls

rc, k = run_main(["--account", "me@x.com"])
assert rc == 0 and k["export"] == 1 and k["cmd"][k["cmd"].index("--account") + 1] == "me@x.com"
assert k["proc"].terminated and not os.path.exists(k["profile"]), "ต้องปิด Chrome และลบโปรไฟล์ชั่วคราว"

rc, k = run_main([])                                   # ไม่ใส่อีเมล -> ถามตอนรัน
assert rc == 0 and k["cmd"][k["cmd"].index("--account") + 1] == "ask@x.com"

rc, k = run_main(["--account", "me@x.com"], login_code=1)   # ล็อกอินล้มเหลว -> ไม่พิมพ์ค่า แต่ยังล้างร่องรอย
assert rc == 1 and k["export"] == 0 and k["proc"].terminated and not os.path.exists(k["profile"])

rc, k = run_main(["--account", "me@x.com"], wait_ok=False)  # Chrome ไม่ตอบสนอง
assert rc == 1 and k["cmd"] is None and not os.path.exists(k["profile"])

rc, k = run_main(["--account", "bad"])                 # อีเมลผิด
assert rc == 2 and k["launch"] is None

rc, k = run_main(["--account", "me@x.com"], chrome=None)   # ไม่พบ Chrome
assert rc == 2 and k["launch"] is None

# ---- โปรไฟล์: ตั้งตัวแปรสภาพแวดล้อมให้ทั้งคำสั่งล็อกอินและตัวพิมพ์ค่า Secrets
assert st.valid_profile_name("systemB") and st.valid_profile_name("a-b_1")
for bad in ("", "a b", "../x", "x" * 41, "ก"):
    assert not st.valid_profile_name(bad), bad
os.environ.pop("NOTEBOOKLM_PROFILE", None)
seen = {}
def fake_run(cmd): seen["env"] = os.environ.get("NOTEBOOKLM_PROFILE"); return 0
rc, k = None, None
orig = st.find_chrome; st.find_chrome = lambda *a, **kw: "/fake/chrome"
try:
    rc = st.main(["--account", "b@x.com", "--profile", "systemB"],
                 launch=lambda c, p, d: FakeProc(), run_cmd=fake_run,
                 export=lambda: seen.setdefault("export_env", os.environ.get("NOTEBOOKLM_PROFILE")) and 0,
                 wait=lambda p: True)
    assert rc == 0 and seen["env"] == "systemB" and seen["export_env"] == "systemB", seen
    os.environ.pop("NOTEBOOKLM_PROFILE", None)
    rc = st.main(["--account", "b@x.com", "--profile", "../x"], launch=lambda c, p, d: FakeProc(),
                 run_cmd=fake_run, export=lambda: 0, wait=lambda p: True)
    assert rc == 2 and "NOTEBOOKLM_PROFILE" not in os.environ
finally:
    st.find_chrome = orig
    os.environ.pop("NOTEBOOKLM_PROFILE", None)
print("setup_token OK")
