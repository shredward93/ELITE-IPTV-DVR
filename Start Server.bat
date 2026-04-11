@echo off
title ELITE IPTV DVR — PC Server
cd /d "%~dp0"
echo Starting ELITE IPTV DVR server...
echo.
echo From the Android TV emulator, connect to:
echo   http://10.0.2.2:8080
echo.
echo From a real Android TV on your LAN, connect to:
echo   http://192.168.2.81:8080
echo.
"C:\Users\eddyd\AppData\Local\Programs\Python\Python310\python.exe" main.py
pause
