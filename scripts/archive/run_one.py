# -*- coding: utf-8 -*-
"""run_one.py - 在独立进程里跑单个世界 N 轮（避免跨世界全局状态污染）"""
import sys, os
PROJ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJ)
import demo_run

n = int(sys.argv[1])
af = sys.argv[2]
lf = sys.argv[3]
demo_run.main(n_rounds=n,
              agents_file=os.path.join(PROJ, af),
              log_path=os.path.join(PROJ, lf))
