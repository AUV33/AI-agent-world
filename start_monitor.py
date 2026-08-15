# -*- coding: utf-8 -*-
"""
start_monitor.py —— 快速启动实时监控
==================================================
用法：
    python start_monitor.py          # 终端实时监控
    python start_monitor.py --html   # 同时启动网页监控
    python start_monitor.py 5        # 运行5轮后停止
==================================================
"""
import sys
import os
import subprocess

PROJ = r"D:\致敬传奇AI项目"
PYTHON = r"C:\Users\萌\Documents\Codex\2026-08-15\bang\work\venv\Scripts\python.exe"

def main():
    args = sys.argv[1:]
    
    print("=" * 50)
    print("🎭 致敬传奇AI - 实时互动监控")
    print("=" * 50)
    print()
    print("选择监控模式：")
    print("  1. 终端实时监控（彩色输出）")
    print("  2. 网页实时监控（浏览器查看）")
    print("  3. 两者同时启动")
    print()
    
    if "--html" in args or "-h" in args:
        mode = "2"
    elif "--both" in args or "-b" in args:
        mode = "3"
    else:
        mode = input("请选择 (1/2/3，默认1): ").strip() or "1"
    
    # 构建命令
    cmd = [PYTHON, os.path.join(PROJ, "realtime_monitor.py")]
    
    # 添加轮数参数
    for arg in args:
        if arg.isdigit():
            cmd.append(arg)
    
    # 添加HTML参数
    if mode in ["2", "3"]:
        cmd.append("--html")
    
    print()
    print("启动中...")
    print()
    
    # 运行
    try:
        subprocess.run(cmd, cwd=PROJ)
    except KeyboardInterrupt:
        print("\n监控已停止")


if __name__ == "__main__":
    main()
