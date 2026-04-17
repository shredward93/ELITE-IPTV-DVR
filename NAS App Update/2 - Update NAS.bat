@echo off
echo ==========================================
echo   ELITE IPTV DVR - Update NAS via SSH
echo ==========================================
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

echo NAS Host: %NAS_HOST%
echo Path: %NAS_PATH%

if "%QC_ID%"=="yourqcid" (
    echo.
    echo [WARNING] QuickConnect ID not configured!
    echo Edit this file and set QC_ID to your QuickConnect ID.
    echo Find it in DSM -^> Control Panel -^> QuickConnect
    pause
    exit /b
)
echo.
echo This will SSH into your NAS, pull latest code,
echo and restart the Docker container.
echo.
set /p confirm="Proceed? (y/n): "
if /I not "%confirm%"=="y" (
    echo Cancelled.
    pause
    exit /b
)

echo.
echo Connecting to NAS and updating...
echo.

ssh -p %SSH_PORT% %NAS_USER%@%NAS_HOST% "cd %NAS_PATH% && git pull && docker-compose restart"

if %ERRORLEVEL% neq 0 (
    echo.
    echo ==========================================
    echo   ERROR: Update failed!
    echo ==========================================
    echo.
    echo Troubleshooting:
    echo  - Check NAS_IP, NAS_USER, and NAS_PATH in this file
    echo  - Ensure SSH is enabled on your Synology NAS
    echo  - Run this command once to save the host key:
    echo    ssh %NAS_USER%@%NAS_IP%
) else (
    echo.
    echo ==========================================
    echo   NAS UPDATED SUCCESSFULLY!
    echo ==========================================
)

pause
