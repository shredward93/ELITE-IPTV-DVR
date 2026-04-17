@echo off
echo ==========================================
echo   ELITE IPTV DVR - FULL REBUILD (Slow)
echo ==========================================
echo.
echo WARNING: This rebuilds the Docker image.
echo Only needed when:
echo   - requirements.txt changed (new Python packages)
echo   - Dockerfile changed
echo   - Base image updates (security patches)
echo.
echo For code changes to .py files, use "2 - Update NAS.bat" instead!
echo.

REM ======= NAS CONFIGURATION =======
set NAS_USER=kurtdoerfel
set NAS_PATH=/volume1/docker/eliteiptvdvr
REM
REM For QuickConnect: Replace YOURQCID with your actual QuickConnect ID
set QC_ID=kurtdoerfel
set NAS_HOST=%QC_ID%.direct.quickconnect.to
set SSH_PORT=2222
REM ==================================

set /p confirm="Are you sure you want to rebuild? (y/n): "
if /I not "%confirm%"=="y" (
    echo Cancelled.
    pause
    exit /b
)

echo.
echo Rebuilding on NAS...
echo This may take 2-5 minutes...
echo.

if "%QC_ID%"=="yourqcid" (
    echo [WARNING] QuickConnect ID not configured!
    echo Edit this file and set QC_ID to your QuickConnect ID.
    pause
    exit /b
)

ssh -p %SSH_PORT% %NAS_USER%@%NAS_HOST% "cd %NAS_PATH% && git pull && docker-compose down && docker-compose up -d --build"

if %ERRORLEVEL% neq 0 (
    echo.
    echo ==========================================
    echo   ERROR: Rebuild failed!
    echo ==========================================
) else (
    echo.
    echo ==========================================
    echo   REBUILD COMPLETE!
    echo ==========================================
)

pause
