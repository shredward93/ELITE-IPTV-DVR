@echo off
setlocal
title ELITE IPTV DVR — Emulator Launcher

set ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe
set EMULATOR=%LOCALAPPDATA%\Android\Sdk\emulator\emulator.exe
set AVD=Television_1080p
set APK=%~dp0android\app\build\outputs\apk\debug\app-debug.apk

echo Starting Android TV emulator: %AVD%
start "" "%EMULATOR%" -avd %AVD% -gpu host -no-boot-anim

echo Waiting for emulator to boot (this takes ~60 seconds)...
:wait_boot
timeout /t 5 /nobreak >nul
"%ADB%" shell getprop sys.boot_completed 2>nul | findstr "1" >nul
if errorlevel 1 goto wait_boot

echo Emulator ready. Installing APK...
if exist "%APK%" (
    "%ADB%" install -r "%APK%"
    echo Launching app...
    "%ADB%" shell am start -n com.elite.iptv.dvr/.MainActivity
) else (
    echo No APK found. Run "Build and Install.bat" first.
)

echo.
echo From emulator: http://10.0.2.2:8080
echo.
echo Debug logcat:
echo   Run "Debug Logcat.bat"
echo.
pause
