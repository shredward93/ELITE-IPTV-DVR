@echo off
:: Filtered logcat for ELITE IPTV DVR debugging
:: Shows: ExoPlayer, OkHttp, Retrofit errors, app crashes, and our custom tags

set ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe

echo === ELITE IPTV DVR — Debug Logcat ===
echo Filtering: ExoPlayer / OkHttp / DVR / AndroidRuntime errors
echo Press Ctrl+C to stop
echo.

"%ADB%" logcat -c
"%ADB%" logcat ExoPlayer:D OkHttp:D AndroidRuntime:E System.err:W *:S
