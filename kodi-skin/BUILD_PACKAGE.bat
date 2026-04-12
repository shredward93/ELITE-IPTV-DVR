@echo off
REM Build ELITE IPTV DVR Kodi Skin Package
echo Building skin package...

cd /d "%~dp0"

if exist "skin.elite.dvr.zip" del "skin.elite.dvr.zip"

powershell -Command "Compress-Archive -Path 'skin.elite.dvr' -DestinationPath 'skin.elite.dvr.zip' -Force"

if %errorlevel% neq 0 (
    echo ERROR: Failed to create zip file!
    echo Trying alternative method...
    
    REM Fallback to tar if available (Windows 10+)
    tar -acf "skin.elite.dvr.zip" "skin.elite.dvr"
    
    if %errorlevel% neq 0 (
        echo ERROR: Could not create zip package!
        pause
        exit /b 1
    )
)

echo.
echo ==========================================
echo Package created: skin.elite.dvr.zip
echo ==========================================
echo.
echo To install in Kodi:
echo 1. Copy skin.elite.dvr.zip to your device
echo 2. Kodi: Settings ^> Add-ons ^> Install from zip file
echo 3. Select the zip file
echo 4. Activate: Settings ^> Interface ^> Skin
echo.
pause
