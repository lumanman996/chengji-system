@echo off
chcp 65001 >nul
echo 正在启动成绩核算系统...
echo.
cd /d "%~dp0"
python app.py
pause
