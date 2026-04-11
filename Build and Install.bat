@echo off
setlocal EnableExtensions
title ELITE IPTV DVR — Build and Install

set "ROOT=%~dp0"
set "ANDROID_DIR=%ROOT%android"
set "ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr"
set "PATH=%JAVA_HOME%\bin;%PATH%"

echo Building APK...
echo.

pushd "%ANDROID_DIR%"
call gradlew.bat assembleDebug
if errorlevel 1 (
    echo.
    echo BUILD FAILED.
    popd
    pause
    exit /b 1
)

echo.
echo Build OK. Installing to emulator...

if not exist "%ADB%" (
    echo ADB not found at "%ADB%"
    popd
    pause
    exit /b 1
)

set "TARGET_DEVICE="
for /f "skip=1 tokens=1,2" %%A in ('"%ADB%" devices') do (
    if /I "%%B"=="device" (
        echo %%A | findstr /B /I "emulator-" >nul
        if not errorlevel 1 if not defined TARGET_DEVICE set "TARGET_DEVICE=%%A"
    )
)

if not defined TARGET_DEVICE (
    echo No online emulator device found.
    popd
    pause
    exit /b 1
)

echo Using device %TARGET_DEVICE%
"%ADB%" -s %TARGET_DEVICE% install -r "app\build\outputs\apk\debug\app-debug.apk"
if errorlevel 1 (
    echo.
    echo INSTALL FAILED.
    popd
    pause
    exit /b 1
)

echo.
echo Done.
popd
pause
