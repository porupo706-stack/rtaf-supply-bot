@echo off
title RTAF Supply Bot - Session Refresher
echo.
echo กำลังตรวจสอบ dependencies...
pip install cryptography requests -q
echo.
python refresh_session.py
