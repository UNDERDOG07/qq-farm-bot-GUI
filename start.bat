@echo off
chcp 65001 >nul
echo.
echo 正在启动 qq-farm-bot-GUI ... 后台挂机这个控制台页面不要关闭，浏览器可以随时访问 http://127.0.0.1:8080/ 查看进度
echo.

python start.py

if %errorlevel% neq 0 (
    echo.
    echo 启动失败！可能原因：
    echo 1. 请确保已在当前目录运行 install.bat
    echo 2. Python 或 nicegui 未正确安装
    echo 3. start.py 文件有问题
    echo.
    pause
) else (
    echo.
    echo 程序已退出，按任意键关闭窗口...
    pause
)