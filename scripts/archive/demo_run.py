# -*- coding: utf-8 -*-
"""demo_run.py - 固定轮数的演示脚本（跑完自动退出，便于产出文档）"""
import os, sys, time
from datetime import datetime

PROJ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJ)

from enhanced_engine import (envs, agents, run_step, run_global_reflection,
                             REFLECTION_ENABLED, REFLECTION_INTERVAL)
from enhanced_agent_factory import load_enhanced_agents, update_envs_with_agents_info


def get_time_label(round_num):
    base_hour = 8
    hour = base_hour + round_num
    day = hour // 24 + 1
    hour = hour % 24
    return f"第{round_num + 1}轮 第{day}天 {hour:02d}:00"


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)

    def flush(self):
        for s in self.streams:
            s.flush()


def main(n_rounds=4, agents_file=None, log_path=None):
    if agents_file is None:
        agents_file = os.path.join(PROJ, 'demo_agents.json')
    if log_path is None:
        log_path = os.path.join(PROJ, 'demo_output.txt')

    load_enhanced_agents(agents_file)
    update_envs_with_agents_info()

    with open(log_path, 'w', encoding='utf-8') as f:
        f.write(f"演示开始：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"角色：{', '.join(agents.keys())}\n")
        f.write("=" * 50 + "\n\n")
        for round_num in range(n_rounds):
            tl = get_time_label(round_num)
            f.write(f"\n{'=' * 50}\n  {tl}\n{'=' * 50}\n\n")
            sys.stdout = Tee(sys.stdout, f)
            try:
                run_step(tl)
                if REFLECTION_ENABLED and round_num > 0 and round_num % REFLECTION_INTERVAL == 0:
                    run_global_reflection(tl)
            finally:
                sys.stdout = sys.__stdout__
            f.write("\n")
            f.flush()
            time.sleep(0.5)
    print(f"演示完成，输出：{log_path}")


if __name__ == "__main__":
    main(n_rounds=4)
