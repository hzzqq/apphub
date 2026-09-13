@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [App Hub] 启动中（零编译桌面壳层）...
python launch.py
if errorlevel 1 (
  echo.
  echo [App Hub] 启动失败：请确认已安装 Python，并已安装后端依赖
  echo           pip install flask
)
echo.
pause
