"""
auth_setup.py — ตั้งค่า master-token auth ของ notebooklm-py (ไม่พึ่ง streamlit)

หลักการ (ตามเอกสาร notebooklm-py):
  • วาง `master_token.json` ไว้คู่กับ `storage_state.json` ใน profile เดียวกัน
  • เมื่อ cookie ของ Google หมดอายุ ไลบรารีจะ "mint" cookie ใหม่จาก master token เอง
    ไม่ต้องเปิด browser / ไม่ต้องรัน refresh_session.bat / ไม่ต้องพึ่ง GitHub Actions keep-alive
  • ห้ามตั้ง NOTEBOOKLM_AUTH_JSON พร้อมกัน — โหมด inline นั้นปิดการ re-mint

master token ไม่หมดอายุเอง และเป็น credential ของทั้งบัญชี → ใช้บัญชี Google เฉพาะกิจเท่านั้น
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

REQUIRED_KEYS = ("version", "email", "android_id", "master_token")


class MasterTokenSetupError(Exception):
    """ตั้งค่า master token ไม่สำเร็จ (ข้อความไม่มีค่าลับ)"""


def parse_master_token_json(text: str) -> dict:
    """ตรวจรูปแบบของเนื้อหา master_token.json แล้วคืน dict (ไม่ใส่ค่าลับในข้อความ error)"""
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        raise MasterTokenSetupError("NOTEBOOKLM_MASTER_TOKEN_JSON ไม่ใช่ JSON ที่ถูกต้อง") from None
    if not isinstance(data, dict):
        raise MasterTokenSetupError("NOTEBOOKLM_MASTER_TOKEN_JSON ต้องเป็น JSON object")
    missing = [k for k in REQUIRED_KEYS if not data.get(k)]
    if missing:
        raise MasterTokenSetupError(f"master token ขาดฟิลด์: {', '.join(missing)}")
    if data["version"] != 1:
        raise MasterTokenSetupError("master token เป็นเวอร์ชันที่ไม่รองรับ")
    return data


def install_master_token(master_json: str, seed_storage_json: str | None = None) -> str:
    """เตรียม profile ให้ใช้ master-token auth แล้วคืนข้อความสถานะ

    1. เขียน master_token.json (สิทธิ์ 0600) ถ้ายังไม่มี/เนื้อหาต่างไป
    2. ถ้ายังไม่มี storage_state.json:
         - มี seed_storage_json (เช่นจาก Gist เดิม) → ใช้เป็นค่าเริ่มต้น
         - ไม่มี → mint session ใหม่จาก master token ทันที
       ถ้ามีอยู่แล้ว (cookie ที่หมุนเวียนระหว่างทำงาน) จะไม่เขียนทับ
    3. ลบ NOTEBOOKLM_AUTH_JSON ออกจาก environment เพื่อไม่ให้ปิดการ re-mint
    """
    from notebooklm.auth import (
        MasterTokenError,
        bootstrap_missing_storage_from_master_token,
        read_master_token,
        write_master_token,
    )
    from notebooklm.paths import get_master_token_path, get_storage_path

    data = parse_master_token_json(master_json)
    token_path: Path = get_master_token_path()
    storage_path: Path = get_storage_path()
    token_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        current = read_master_token(token_path)
    except MasterTokenError:
        current = None
    same = bool(current) and all(current.get(k) == data[k] for k in ("email", "android_id", "master_token"))
    if not same:
        write_master_token(token_path, email=data["email"],
                           master_token=data["master_token"], android_id=data["android_id"])
        action = "เขียน master_token.json"
    else:
        action = "ใช้ master_token.json เดิม"

    os.environ.pop("NOTEBOOKLM_AUTH_JSON", None)

    if storage_path.exists():
        return f"{action}; ใช้ session เดิมในเครื่อง"

    if seed_storage_json:
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        storage_path.write_text(seed_storage_json, encoding="utf-8")
        try:
            os.chmod(storage_path, 0o600)
        except OSError:
            pass
        return f"{action}; ตั้ง session เริ่มต้นจากข้อมูลสำรอง (จะ mint ใหม่เองเมื่อหมดอายุ)"

    try:
        ok = asyncio.run(bootstrap_missing_storage_from_master_token(storage_path))
    except MasterTokenError as exc:
        raise MasterTokenSetupError(f"mint session จาก master token ไม่สำเร็จ: {exc}") from None
    if not ok:
        raise MasterTokenSetupError("mint session จาก master token ไม่สำเร็จ (ไม่พบ token)")
    return f"{action}; mint session ใหม่จาก master token แล้ว"
