@echo off
title ELITE IPTV DVR — PC Server
cd /d "%~dp0"
echo Starting ELITE IPTV DVR server...
echo.
echo From the same machine, connect to:
echo   http://127.0.0.1:8080
echo.
echo From another device on your LAN, connect to the PC's local IP on port 8080.
echo.
"C:\Users\eddyd\AppData\Local\Programs\Python\Python310\python.exe" main.py
pause
