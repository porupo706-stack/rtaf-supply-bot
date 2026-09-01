@echo off
title RTAF Supply Bot - Session Refresher
cd /d "%~dp0"

echo.
echo กำลังตรวจสอบ dependencies...
pip install cryptography requests -q

echo.
python refresh_session.py

echo.
if %errorlevel% neq 0 (
    echo ❌ เกิดข้อผิดพลาด error code: %errorlevel%
)
pause
