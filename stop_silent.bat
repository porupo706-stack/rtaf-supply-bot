@echo off
echo กำลังหยุด Auto-refresh...
taskkill /f /im pythonw.exe >nul 2>&1
echo ✅ หยุดแล้ว
timeout /t 2 >nul
