@echo off
echo ==========================================
echo   ELITE IPTV DVR - Push to GitHub
echo ==========================================
echo.
echo This will push your local changes to GitHub.
echo.
cd /d "C:\Users\eddyd\Documents\VS Code\ELITE IPTV DVR"

git status
echo.
set /p confirm="Push these changes? (y/n): "
if /I "%confirm%"=="y" (
    git push
    echo.
    echo ==========================================
    echo   PUSHED! Now run "2 - Update NAS.bat"
    echo ==========================================
) else (
    echo Cancelled.
)
pause
