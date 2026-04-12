@echo off
REM ELITE IPTV DVR Kodi Skin Installer
REM This script installs the skin to your Kodi addons folder

echo ==========================================
echo ELITE IPTV DVR Kodi Skin Installer
echo ==========================================
echo.

set KODI_ADDONS=%APPDATA%\Kodi\addons
set SKIN_NAME=skin.elite.dvr
set SOURCE_DIR=%~dp0%SKIN_NAME%

if not exist "%KODI_ADDONS%" (
    echo ERROR: Kodi addons folder not found at:
    echo %KODI_ADDONS%
    echo.
    echo Make sure Kodi is installed.
    pause
    exit /b 1
)

if not exist "%SOURCE_DIR%" (
    echo ERROR: Skin folder not found: %SKIN_NAME%
    echo Make sure you're running this from the kodi-skin folder.
    pause
    exit /b 1
)

echo Installing skin to: %KODI_ADDONS%\%SKIN_NAME%

if exist "%KODI_ADDONS%\%SKIN_NAME%" (
    echo Removing existing installation...
    rmdir /s /q "%KODI_ADDONS%\%SKIN_NAME%"
)

echo Copying files...
xcopy /e /i /y "%SOURCE_DIR%" "%KODI_ADDONS%\%SKIN_NAME%"

if %errorlevel% neq 0 (
    echo ERROR: Failed to copy files!
    pause
    exit /b 1
)

echo.
echo ==========================================
echo Installation Complete!
echo ==========================================
echo.
echo Next steps:
echo 1. Open Kodi
echo 2. Go to Settings ^> Interface ^> Skin
echo 3. Select "ELITE IPTV DVR"
echo 4. Enjoy your branded Kodi experience!
echo.
pause
