@echo off
title ELITE IPTV DVR — Build and Install
echo Building APK...
echo.

powershell -NoProfile -Command "^
    $env:JAVA_HOME = 'C:\Program Files\Android\Android Studio\jbr'; ^
    $env:PATH = $env:JAVA_HOME + '\bin;' + $env:PATH; ^
    Set-Location 'C:\Users\eddyd\Documents\VS Code\ELITE IPTV DVR\android'; ^
    & .\gradlew.bat assembleDebug; ^
    if ($LASTEXITCODE -eq 0) { ^
        Write-Host 'Build OK. Installing to emulator...'; ^
        $adb = $env:LOCALAPPDATA + '\Android\Sdk\platform-tools\adb.exe'; ^
        & $adb install -r 'app\build\outputs\apk\debug\app-debug.apk'; ^
        Write-Host 'Done.'; ^
    } else { ^
        Write-Host 'BUILD FAILED.' -ForegroundColor Red; ^
    } ^
"
pause
