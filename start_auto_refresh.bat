@echo off
title RTAF Auto Session Sync
cd /d "%~dp0"
pip install cryptography requests -q
echo.
echo กำลังเริ่ม Auto-refresh ทุก 3 นาที...
echo ปิดหน้าต่างนี้เพื่อหยุด
echo.
python auto_refresh.py
pause
