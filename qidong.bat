@echo off
title Pudater_gendan_bot by_Wangdage

echo ============================================
echo     Pudater_gendan_bot by_Wangdage
echo ============================================
echo.

:: Switch to current folder
cd /d %~dp0

:: Check Python
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed!
    pause
    exit /b
)

echo Starting  Pudater_gendan_bot by_Wangdage ...
echo.

:: Start waigua.py
python waigua.py

echo.
echo Worker exited. Press any key to close.
pause
