# -*- coding: utf-8 -*-
"""
demo_monitor.py —— 演示实时监控功能
==================================================
运行这个脚本来快速体验实时监控效果
==================================================
"""
import os
import sys
import time

PROJ = r"D:\致敬传奇AI项目"
PYTHON = r"C:\Users\萌\Documents\Codex\2026-08-15\bang\work\venv\Scripts\python.exe"

def print_banner():
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║           🎭 致敬传奇AI - 实时互动监控演示 🎭                ║
║                                                              ║
║    观看明远中学 302 寝室的同学们实时互动！                    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")

def print_menu():
    print("""
请选择演示模式：
┌─────────────────────────────────────────────────────────────┐
│  1. 📺 终端实时监控（彩色输出，推荐）                        │
│  2. 🌐 网页实时监控（浏览器查看）                            │
│  3. 🚀 快速体验（运行1轮看看效果）                          │
│  4. 📖 查看使用说明                                         │
│  0. 退出                                                     │
└─────────────────────────────────────────────────────────────┘
""")

def run_terminal_demo(rounds=1):
    """运行终端演示"""
    print(f"\n🎬 启动终端实时监控（{rounds}轮）...\n")
    cmd = f'"{PYTHON}" "{os.path.join(PROJ, "realtime_monitor.py")}" {rounds}'
    os.system(cmd)

def run_html_demo():
    """运行网页演示"""
    print("\n🌐 启动网页实时监控...\n")
    cmd = f'"{PYTHON}" "{os.path.join(PROJ, "realtime_monitor.py")}" --html'
    print("正在生成监控页面...")
    os.system(cmd)
    print("\n✅ monitor.html 已生成！")
    print(f"📁 文件位置：{os.path.join(PROJ, 'monitor.html')}")
    print("\n请在浏览器中打开此文件查看实时监控")

def show_readme():
    """显示使用说明"""
    readme_path = os.path.join(PROJ, "MONITOR_README.md")
    if os.path.exists(readme_path):
        with open(readme_path, "r", encoding="utf-8") as f:
            print(f.read())
    else:
        print("说明文件不存在")

def main():
    print_banner()
    
    while True:
        print_menu()
        choice = input("请输入选项 (0-4): ").strip()
        
        if choice == "1":
            rounds = input("运行几轮？（直接回车=无限）: ").strip()
            rounds = int(rounds) if rounds.isdigit() else None
            run_terminal_demo(rounds)
        
        elif choice == "2":
            run_html_demo()
        
        elif choice == "3":
            print("\n🎬 快速体验模式：运行1轮看看效果\n")
            run_terminal_demo(1)
            print("\n✅ 演示完成！")
            print("💡 提示：运行 python realtime_monitor.py 可以无限运行")
        
        elif choice == "4":
            show_readme()
        
        elif choice == "0":
            print("\n👋 再见！")
            break
        
        else:
            print("\n❌ 无效选项，请重新输入")
        
        input("\n按回车键继续...")


if __name__ == "__main__":
    main()
