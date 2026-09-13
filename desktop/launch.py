#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""App Hub 零编译桌面启动器

不需要 Rust / Node / 任何打包工具，装上 Python + Flask 就能用：
  1. 后端没起来就后台拉起 `python backend/app.py`
  2. 等待 127.0.0.1:8787 就绪
  3. 用 Edge/Chrome 的 --app 模式打开（无地址栏、无标签页，观感接近原生窗口）
     找不到 Chromium 内核浏览器时，退化为系统默认浏览器

用法：
    python desktop/launch.py
    或双击 launcher.bat（Windows）/ 执行 bash launcher.sh（mac、Linux）

环境变量：
    APPHUB_PORT   后端端口（默认 8787）
    APPHUB_PYTHON 运行后端的解释器（默认与当前解释器相同）
"""

import os
import socket
import subprocess
import sys
import time
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))

PORT = int(os.environ.get("APPHUB_PORT", "8787"))
URL = "http://127.0.0.1:%d" % PORT
PY = os.environ.get("APPHUB_PYTHON") or sys.executable or "python"
LOG = os.path.join(HERE, ".backend.log")


def port_open(port, host="127.0.0.1", timeout=0.6):
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True
    except Exception:
        return False


def start_backend():
    """后台拉起 Flask 后端；日志写入 desktop/.backend.log 便于排障。"""
    if not os.path.isfile(os.path.join(ROOT, "backend", "app.py")):
        print("[App Hub] 未找到 backend/app.py（ROOT=%s）" % ROOT)
        return False
    print("[App Hub] 启动后端：%s backend/app.py" % PY)
    logf = open(LOG, "wb")
    kwargs = {"cwd": ROOT, "stdout": logf, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True
    try:
        subprocess.Popen([PY, "backend/app.py"], **kwargs)
    except Exception as e:
        print("[App Hub] 后端启动失败：%s" % e)
        return False
    return True


def find_chromium():
    """找一个 Chromium 内核浏览器，用 --app 模式得到无地址栏的『原生窗口』观感。"""
    cands = []
    if sys.platform.startswith("win"):
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        local = os.environ.get("LOCALAPPDATA", "")
        cands = [
            os.path.join(pf86, "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(pf, "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(pf, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(pf86, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(local, "Google", "Chrome", "Application", "chrome.exe"),
        ]
    elif sys.platform == "darwin":
        cands = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    else:
        for name in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge"):
            p = _which(name)
            if p:
                cands.append(p)
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


def _which(name):
    for d in (os.environ.get("PATH") or "").split(os.pathsep):
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return p
    return None


def open_window():
    browser = find_chromium()
    if browser:
        print("[App Hub] 以应用窗口模式打开：%s" % browser)
        try:
            subprocess.Popen([browser, "--app=" + URL, "--window-size=1280,860"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            print("[App Hub] 打开失败（%s），退化为默认浏览器" % e)
    print("[App Hub] 用默认浏览器打开：%s" % URL)
    try:
        webbrowser.open(URL)
        return True
    except Exception as e:
        print("[App Hub] 打开浏览器失败：%s" % e)
        return False


def main():
    print("=" * 60)
    print("App Hub · 零编译桌面启动器")
    print("=" * 60)

    if port_open(PORT):
        print("[App Hub] 后端已在 %s 运行" % URL)
    else:
        if not start_backend():
            return 1
        print("[App Hub] 等待后端就绪", end="", flush=True)
        for _ in range(60):
            if port_open(PORT):
                print(" 就绪")
                break
            print(".", end="", flush=True)
            time.sleep(0.5)
        else:
            print("\n[App Hub] 后端 30s 未就绪，请看日志：%s" % LOG)
            return 1

    ok = open_window()
    print("[App Hub] 地址：%s" % URL)
    print("[App Hub] 提示：关闭窗口不会停后端；要停止请结束 python backend/app.py 进程")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
