@echo off
echo ==========================================
echo   CHECK IF REBUILD IS NEEDED
echo ==========================================
echo.
echo This will check your recent changes and tell you
whether you need to restart or rebuild the container on your NAS.
echo.

cd /d "C:\Users\eddyd\Documents\VS Code\ELITE IPTV DVR"

REM Check uncommitted changes
setlocal enabledelayedexpansion
set REQ_CHANGED=0
set DOCK_CHANGED=0
set COMPOSE_CHANGED=0

echo Checking modified files...
echo.

for /f "tokens=*" %%a in ('git diff --name-only') do (
    if "%%a"=="requirements.txt" set REQ_CHANGED=1
    if "%%a"=="Dockerfile" set DOCK_CHANGED=1
    if "%%a"=="docker-compose.yml" set COMPOSE_CHANGED=1
    echo   [MODIFIED] %%a
)

for /f "tokens=*" %%a in ('git diff --cached --name-only') do (
    if "%%a"=="requirements.txt" set REQ_CHANGED=1
    if "%%a"=="Dockerfile" set DOCK_CHANGED=1
    if "%%a"=="docker-compose.yml" set COMPOSE_CHANGED=1
    echo   [STAGED] %%a
)

echo.
echo ==========================================
echo   RESULT
echo ==========================================
echo.

if %REQ_CHANGED%==1 (
    echo [!!!] REBUILD REQUIRED
    echo.
    echo requirements.txt was modified.
    echo This means new Python packages need installation.
    echo.
    echo ACTION: In Container Manager, rebuild the container (2-5 minutes)
) else if %DOCK_CHANGED%==1 (
    echo [!!!] REBUILD REQUIRED
    echo.
    echo Dockerfile was modified.
    echo Container configuration has changed.
    echo.
    echo ACTION: In Container Manager, rebuild the container (2-5 minutes)
) else if %COMPOSE_CHANGED%==1 (
    echo [!] docker-compose.yml changed
    echo.
    echo This MAY require a rebuild depending on what changed:
    echo   - New volume mounts: Just restart
    echo   - Build context changes: Full rebuild
    echo.
    echo Try restarting the container first in Container Manager.
    echo If that doesn't work, rebuild the container.
) else (
    echo [OK] No rebuild needed!
    echo.
    echo Your changes are to code files (.py) only.
    echo The fast restart will pick them up instantly.
    echo.
    echo ACTION: Restart the container in Container Manager (10 seconds)
)

echo.
pause
