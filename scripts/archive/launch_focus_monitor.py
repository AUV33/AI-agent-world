# -*- coding: utf-8 -*-
"""脱离式启动聚焦监控。"""
import subprocess, sys, os

PROJ = os.path.dirname(os.path.abspath(__file__))
DETACH = getattr(subprocess, "DETACHED_PROCESS", 0) | subprocess.CREATE_NEW_PROCESS_GROUP

subprocess.Popen(
    [sys.executable, "focus_monitor.py"],
    cwd=PROJ,
    stdout=open(os.path.join(PROJ, "focus_monitor_out.txt"), "w", encoding="utf-8"),
    stderr=open(os.path.join(PROJ, "focus_monitor_err.txt"), "w", encoding="utf-8"),
    creationflags=DETACH,
)
print("launched focus monitor (detached)")
