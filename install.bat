@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo.
echo =============================================
echo   qq-farm-bot-GUI  一键安装依赖 (Windows)
echo =============================================
echo.

echo [1/4] 检查 Node.js 是否已安装...
node -v >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Node.js 未找到！
    echo     请访问 https://nodejs.org 下载并安装 LTS 版本（建议 18.x 或 20.x）
    echo     安装完成后重新运行此脚本。
    echo.
    pause
    exit /b 1
)
echo [OK] Node.js 已安装：!node -v!

echo.
echo [2/4] 安装 Node.js 项目依赖...
call npm install --production
if %errorlevel% neq 0 (
    echo [X] npm install 失败！请检查网络或 package.json 是否正常。
    echo     也可以尝试删除 node_modules 文件夹后重试。
    pause
    exit /b 1
)
echo [OK] Node.js 依赖安装完成

echo.
echo [3/4] 检查 Python 是否已安装...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Python 未找到！
    echo     请访问 https://www.python.org/downloads/ 下载 Python 3.10 或更高版本
    echo     安装时请勾选「Add Python to PATH」
    echo     安装完成后重新运行此脚本。
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do set PYVER=%%i
echo [OK] Python 已安装：!PYVER!

echo.
echo [4/4] 安装 nicegui...
pip install nicegui --upgrade
if %errorlevel% neq 0 (
    echo [X] pip install nicegui 失败！请检查 pip 是否可用。
    echo     可以尝试：python -m pip install --upgrade pip
    pause
    exit /b 1
)
echo [OK] nicegui 安装完成

echo.
echo =============================================
echo         所有依赖安装完毕！
echo   接下来双击 start.bat 即可打开图形界面
echo =============================================
echo.
pause