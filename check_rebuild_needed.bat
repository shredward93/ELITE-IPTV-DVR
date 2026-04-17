@echo off
echo ==========================================
echo   REBUILD NEEDED CHECK
echo ==========================================
echo.

REM Get list of changed files staged or unstaged
for /f "tokens=*" %%a in ('git diff --name-only HEAD~1') do (
    if "%%a"=="requirements.txt" set REQ_CHANGED=1
    if "%%a"=="Dockerfile" set DOCK_CHANGED=1
    if "%%a"=="docker-compose.yml" set COMPOSE_CHANGED=1
)

for /f "tokens=*" %%a in ('git diff --cached --name-only') do (
    if "%%a"=="requirements.txt" set REQ_CHANGED=1
    if "%%a"=="Dockerfile" set DOCK_CHANGED=1
    if "%%a"=="docker-compose.yml" set COMPOSE_CHANGED=1
)

if defined REQ_CHANGED (
    echo [!!!] REBUILD REQUIRED: requirements.txt has changes
    echo       New Python dependencies detected.
    echo       Use: 3 - Full Rebuild NAS.bat
    echo.
)

if defined DOCK_CHANGED (
    echo [!!!] REBUILD REQUIRED: Dockerfile has changes
    echo       Container configuration changed.
    echo       Use: 3 - Full Rebuild NAS.bat
    echo.
)

if defined COMPOSE_CHANGED (
    echo [!] docker-compose.yml changed
    echo    This MAY need a rebuild depending on what changed.
    echo    If you added volume mounts: restart is enough.
    echo    If you changed the build context: rebuild needed.
    echo.
)

if not defined REQ_CHANGED if not defined DOCK_CHANGED (
    echo [OK] No rebuild needed - code changes only
    echo     Use: 2 - Update NAS.bat (fast restart)
    echo.
)

pause
