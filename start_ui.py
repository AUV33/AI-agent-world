# -*- coding: utf-8 -*-
"""
start_ui.py —— 启动UI界面
==================================================
用法：
    python start_ui.py
==================================================
"""
import os
import sys
import subprocess
import webbrowser
import time

PROJ = r"D:\致敬传奇AI项目"
PYTHON = r"C:\Users\萌\Documents\Codex\2026-08-15\bang\work\venv\Scripts\python.exe"

def main():
    print("=" * 50)
    print("致敬传奇AI - UI界面启动器")
    print("=" * 50)
    print()
    print("正在启动UI服务器...")
    
    # 启动服务器
    server_process = subprocess.Popen(
        [PYTHON, os.path.join(PROJ, "ui_server.py")],
        cwd=PROJ,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # 等待服务器启动
    time.sleep(2)
    
    # 打开浏览器
    url = "http://localhost:8080"
    print(f"服务器已启动: {url}")
    print("正在打开浏览器...")
    webbrowser.open(url)
    
    print()
    print("提示：")
    print("  - 浏览器已打开，可以开始使用")
    print("  - 按 Ctrl+C 停止服务器")
    print("  - 如果浏览器没有自动打开，请手动访问: http://localhost:8080")
    print()
    
    try:
        # 保持服务器运行
        server_process.wait()
    except KeyboardInterrupt:
        print("\n正在停止服务器...")
        server_process.terminate()
        print("服务器已停止")


if __name__ == "__main__":
    main()
