# -*- coding: utf-8 -*-
"""脱离式启动聚焦生成：5 个关联角色 × 5 轮。"""
import subprocess, sys, os

PROJ = os.path.dirname(os.path.abspath(__file__))
DETACH = getattr(subprocess, "DETACHED_PROCESS", 0) | subprocess.CREATE_NEW_PROCESS_GROUP

subprocess.Popen(
    [sys.executable, "run_one.py", "5", "focus_agents.json", "focus_output.txt"],
    cwd=PROJ,
    stdout=open(os.path.join(PROJ, "focus_out.txt"), "w", encoding="utf-8"),
    stderr=open(os.path.join(PROJ, "focus_err.txt"), "w", encoding="utf-8"),
    creationflags=DETACH,
)
print("launched focus generation (detached)")
