@echo off
title HEXOR AI OS
cd /d "%~dp0"

:main_loop
cls
echo ============================================================
echo HEXOR // JARVIS AUTONOMOUS AGENT SYSTEM
echo Launching Core...
echo ============================================================
python run_hexor.py

set EXIT_CODE=%ERRORLEVEL%
if %EXIT_CODE% equ 0 (
    echo.
    echo [Hexor] Core shut down cleanly.
    timeout /t 1 >nul
    exit /b 0
)

echo.
echo ============================================================
echo [SUPERVISOR] Hexor Core stopped (exit code: %EXIT_CODE%).
echo [SUPERVISOR] Auto-recovering in 3 seconds... (Press Ctrl+C to cancel)
echo ============================================================
timeout /t 3
goto main_loop
