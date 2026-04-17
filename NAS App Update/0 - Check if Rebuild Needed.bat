@echo off
echo ==========================================
echo   CHECK IF REBUILD IS NEEDED
echo ==========================================
echo.
echo This will check your recent changes and tell you
whether to use "Update NAS" (fast) or "Full Rebuild" (slow).
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
    echo USE: 3 - Full Rebuild NAS.bat (2-5 minutes)
) else if %DOCK_CHANGED%==1 (
    echo [!!!] REBUILD REQUIRED
    echo.
    echo Dockerfile was modified.
    echo Container configuration has changed.
    echo.
    echo USE: 3 - Full Rebuild NAS.bat (2-5 minutes)
) else if %COMPOSE_CHANGED%==1 (
    echo [!] docker-compose.yml changed
    echo.
    echo This MAY require a rebuild depending on what changed:
    echo   - New volume mounts: Just restart
    echo   - Build context changes: Full rebuild
    echo.
    echo Try "2 - Update NAS.bat" first.
    echo If it doesn't work, use "3 - Full Rebuild NAS.bat"
) else (
    echo [OK] No rebuild needed!
    echo.
    echo Your changes are to code files (.py) only.
    echo The fast restart will pick them up instantly.
    echo.
    echo USE: 2 - Update NAS.bat (10 seconds)
)

echo.
pause
