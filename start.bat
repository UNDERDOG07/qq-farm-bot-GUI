@echo off
chcp 65001 >nul
echo.
echo ================================================
echo   QQ农场经典挂机启动器（自农场专用版）
echo ================================================
echo.
echo 步骤说明
echo 1. 即将自动打开浏览器到扫码登录页面
echo 2. 用手机 QQ 扫码授权登录（2分钟内完成）
echo 3. 登录成功后，页面右侧日志会显示 "Authorization Code: xxxxxxxx"（一串长字符串）
echo 4. 复制这个 code，粘贴到即将弹出的 GUI 界面中的“登录Code”输入框
echo 5. 在 GUI 设置自家间隔（建议 30-60 秒），点击“开始挂机”
echo.
echo 后台挂机启动后，这个控制台不要关闭！
echo 可随时浏览器访问 http://127.0.0.1:8080/ 查看进度
echo.
pause

:: 自动打开浏览器访问扫码页面（Windows 默认浏览器）
start "" "https://qrcode.atlcservals.com/"

echo.
echo 浏览器已打开，请完成扫码登录并复制 code...
echo 完成后回到这个窗口，按任意键继续启动 GUI...
pause

python start.py

if %errorlevel% neq 0 (
    echo.
    echo 启动失败！可能原因：
    echo 1. 未运行 install.bat（缺少依赖）
    echo 2. Python 或 nicegui 未安装
    echo 3. start.py 文件损坏
    echo.
    pause
) else (
    echo.
    echo 程序已退出，按任意键关闭窗口...
    pause
)
