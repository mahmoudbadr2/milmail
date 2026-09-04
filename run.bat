@echo off
chcp 65001 > nul
set PYTHONUTF8=1
title MinMail Platform Server
echo.
echo ========================================================
echo        MinMail.pro - Privacy Email Alias Platform
echo ========================================================
echo.
echo  [+] جاري تشغيل خادم المنصة على: http://127.0.0.1:8000
echo  [+] للوصول للموقع افتح المتصفح على: http://localhost:8000
echo.
echo  [i] اضغط Ctrl + C لايقاف الخادم في اي وقت.
echo ========================================================
echo.
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause
