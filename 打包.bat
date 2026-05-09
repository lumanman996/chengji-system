@echo off
chcp 65001 >nul
echo ========================================
echo   成绩核算系统 - 打包工具
echo ========================================
echo.

REM 检查 PyInstaller
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [!] PyInstaller 未安装，正在安装...
    pip install pyinstaller
)

echo [1/3] 清理旧构建...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

echo [2/3] 开始打包...
pyinstaller chengji.spec --noconfirm

echo [3/3] 复制配置目录...
if not exist "dist\成绩核算系统\config" mkdir "dist\成绩核算系统\config"
if not exist "dist\成绩核算系统\uploads" mkdir "dist\成绩核算系统\uploads"

REM 复制已有配置
if exist "config\teachers.json" copy "config\teachers.json" "dist\成绩核算系统\config\" >nul
if exist "config\class_counts.json" copy "config\class_counts.json" "dist\成绩核算系统\config\" >nul
if exist "config\algorithm.json" copy "config\algorithm.json" "dist\成绩核算系统\config\" >nul

echo.
echo ========================================
echo   打包完成！
echo   输出目录: dist\成绩核算系统\
echo   运行: dist\成绩核算系统\成绩核算系统.exe
echo ========================================
pause
