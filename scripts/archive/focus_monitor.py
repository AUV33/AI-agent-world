# -*- coding: utf-8 -*-
"""监控聚焦生成：5 个关联角色 × 5 轮，跑完写 focus_done.txt 并退出。
判定只依赖日志轮次标题数（>= 角色数 × 轮数），并加卡死超时保护。"""
import os, re, time

PROJ = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(PROJ, "focus_output.txt")
DONE = os.path.join(PROJ, "focus_done.txt")
N_AGENTS = 5
N_ROUNDS = 5
TARGET = N_AGENTS * N_ROUNDS  # 25 个轮次标题
STUCK_LIMIT = 12 * 60  # 12 分钟无增长视为卡死


def progress():
    if not os.path.exists(LOG):
        return 0, 0, 0
    s = open(LOG, encoding="utf-8", errors="ignore").read()
    r = sum(len(re.findall(rf"\[第{i}轮", s)) for i in range(1, N_ROUNDS + 1))
    err = len(re.findall(r"\[ERROR\]", s))
    return r, err, os.path.getsize(LOG)


last_size = -1
last_grow = time.time()
while True:
    r, err, size = progress()
    now = time.time()
    if size != last_size:
        last_size = size
        last_grow = now
    if r >= TARGET:
        with open(DONE, "w", encoding="utf-8") as f:
            f.write(f"DONE rounds_done~={r} errors={err}\n")
        print("focus generation finished")
        break
    if now - last_grow > STUCK_LIMIT:
        with open(DONE, "w", encoding="utf-8") as f:
            f.write(f"STUCK rounds_done~={r} errors={err} size={size}\n")
        print("focus generation STUCK/stopped")
        break
    time.sleep(30)
