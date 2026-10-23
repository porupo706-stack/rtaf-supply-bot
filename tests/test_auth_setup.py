import json, os, stat, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

home = tempfile.mkdtemp()
os.environ["NOTEBOOKLM_HOME"] = home
os.environ["NOTEBOOKLM_AUTH_JSON"] = "{}"   # ต้องถูกลบเมื่อใช้โหมด master token
os.environ.pop("NOTEBOOKLM_PROFILE", None)

import auth_setup as a

good = json.dumps({"version": 1, "email": "bot@example.com", "android_id": "abc123", "master_token": "aas_et/SECRET"})

# --- ตรวจรูปแบบ
for bad in ["", "not json", "[]", json.dumps({"version": 1, "email": "x"}),
            json.dumps({"version": 2, "email": "x", "android_id": "y", "master_token": "z"})]:
    try:
        a.parse_master_token_json(bad); raise SystemExit(f"ควรปฏิเสธ: {bad!r}")
    except a.MasterTokenSetupError as e:
        assert "SECRET" not in str(e)

# --- ติดตั้งพร้อม session เริ่มต้น
msg = a.install_master_token(good, '{"cookies": []}')
mt = Path(home) / "profiles" / "default" / "master_token.json"
ss = Path(home) / "profiles" / "default" / "storage_state.json"
assert mt.exists() and ss.exists(), list(Path(home).rglob("*"))
assert "NOTEBOOKLM_AUTH_JSON" not in os.environ
if os.name == "posix":
    assert stat.S_IMODE(mt.stat().st_mode) == 0o600, oct(mt.stat().st_mode)
assert json.loads(mt.read_text())["master_token"] == "aas_et/SECRET"
assert "SECRET" not in msg

# --- เรียกซ้ำ: ไม่เขียนทับ session ที่หมุนเวียนแล้ว
ss.write_text('{"cookies": ["rotated"]}')
msg2 = a.install_master_token(good, '{"cookies": ["stale-from-gist"]}')
assert "rotated" in ss.read_text() and "เดิม" in msg2, msg2

# --- เปลี่ยน token ใหม่ -> เขียนทับ master_token.json
new = json.dumps({"version": 1, "email": "bot@example.com", "android_id": "abc123", "master_token": "aas_et/NEW"})
a.install_master_token(new)
assert json.loads(mt.read_text())["master_token"] == "aas_et/NEW"
print("auth_setup OK")
