@echo off
title Closing Hexor AI OS...
echo ===================================================
echo Terminating Hexor AI OS, Core Services and Terminal...
echo ===================================================

:: 1. Attempt graceful notification to API if online
curl -s -m 1 -X POST http://127.0.0.1:8000/api/system/shutdown >nul 2>&1

:: 2. Close dedicated terminal window by window title
taskkill /F /FI "WINDOWTITLE eq HEXOR AI OS*" >nul 2>&1

:: 3. Terminate any Python process running run_hexor.py
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*run_hexor.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1

:: 4. Terminate any residual process listening on port 8000
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo Hexor has been completely stopped and all ports released.
timeout /t 1 /nobreak >nul
exit
