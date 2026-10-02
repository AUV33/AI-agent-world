# -*- coding: utf-8 -*-
"""run_remaining.py - 依次跑剩余 4 个世界（Japan/Jec/Malaya/demo），各 3 轮，支持断点续跑。"""
import os, sys, subprocess, time
from datetime import datetime

PROJ = os.path.dirname(os.path.abspath(__file__))
N = 2
WORLDS = [
    ('Japan',  'japanAgents.json',  'run_japan.txt'),
    ('Jec',    'JecAgents.json',    'run_jec.txt'),
    ('Malaya', 'malayaAgents.json', 'run_malaya.txt'),
    ('demo',   'demo_agents.json',  'run_demo.txt'),
]
STATUS = os.path.join(PROJ, 'run_remaining_status.txt')


def log(msg):
    with open(STATUS, 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.now():%H:%M:%S}] {msg}\n")
        f.flush()


def rounds_done(lf):
    p = os.path.join(PROJ, lf)
    if not os.path.exists(p):
        return 0
    try:
        s = open(p, encoding='utf-8', errors='ignore').read()
    except Exception:
        return 0
    # demo_run 每轮写一个 "第X轮 第Y天 HH:00" 标题
    return s.count('轮 第')  # 粗略：每个轮次标题含 "轮 第"


if __name__ == '__main__':
    log(f"START ALL worlds={[w[0] for w in WORLDS]} rounds={N}")
    for name, af, lf in WORLDS:
        done = rounds_done(lf)
        if done >= N:
            log(f"SKIP {name} (already {done} rounds)")
            continue
        log(f"START {name} (prev rounds={done})")
        t0 = time.time()
        try:
            rc = subprocess.run(
                [sys.executable, 'run_one.py', str(N), af, lf],
                cwd=PROJ,
            ).returncode
        except Exception as e:
            rc = -1
            log(f"EXC {name} {e}")
        log(f"END {name} rc={rc} elapsed={time.time()-t0:.0f}s")
    log("ALL DONE")
