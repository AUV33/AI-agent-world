# -*- coding: utf-8 -*-
"""enhanced_runner.py - 增强版模拟运行器（持续运行）"""
import os, sys, time, signal, argparse
from datetime import datetime

PROJ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJ)

from enhanced_engine import EnhancedAgent, envs, agents, msgCenter, run_step, run_global_reflection, REFLECTION_ENABLED, REFLECTION_INTERVAL
from enhanced_agent_factory import load_enhanced_agents, update_envs_with_agents_info

running = True


def signal_handler(sig, frame):
    global running
    print("\n\n正在优雅停止... 等待当前轮次完成...")
    running = False


signal.signal(signal.SIGINT, signal_handler)


class Tee:
    """同时输出到控制台和文件"""
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)

    def flush(self):
        for s in self.streams:
            s.flush()


def get_time_label(round_num):
    """根据轮次生成时间标签（模拟一天中的时间推进）"""
    base_hour = 8
    hour = base_hour + round_num
    day = hour // 24 + 1
    hour = hour % 24
    return f"第{round_num+1}轮 第{day}天 {hour:02d}:00"


def run_simulation(agents_file=None, log_dir=None, interval=5):
    """持续运行模拟，Ctrl+C 停止"""
    global running

    if agents_file is None:
        agents_file = os.path.join(PROJ, 'data', 'AuvAgents.json')
    if log_dir is None:
        log_dir = os.path.join(PROJ, '记录', '原始日志')
    os.makedirs(log_dir, exist_ok=True)

    load_enhanced_agents(agents_file)
    update_envs_with_agents_info()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"模拟记录_{timestamp}.txt")

    print("=" * 50)
    print("  AI Agent World 模拟运行器")
    print("=" * 50)
    print(f"角色：{', '.join(agents.keys())}")
    print(f"日志：{log_file}")
    print(f"间隔：{interval}秒/轮")
    print("按 Ctrl+C 停止")
    print("=" * 50)

    round_num = 0

    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(f"模拟开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"角色：{', '.join(agents.keys())}\n")
        f.write("=" * 50 + "\n\n")

        while running:
            time_label = get_time_label(round_num)
            print(f"\n{'='*50}")
            print(f"  {time_label}")
            print(f"{'='*50}\n")
            f.write(f"\n{'='*50}\n  {time_label}\n{'='*50}\n\n")

            old_stdout = sys.stdout
            sys.stdout = Tee(sys.stdout, f)
            try:
                run_step(time_label)
            finally:
                sys.stdout = old_stdout

            if REFLECTION_ENABLED and round_num > 0 and round_num % REFLECTION_INTERVAL == 0:
                run_global_reflection(time_label)

            f.write("\n")
            f.flush()

            round_num += 1

            if running:
                print(f"\n[等待 {interval} 秒后开始下一轮...]")
                for _ in range(interval):
                    if not running:
                        break
                    time.sleep(1)

    print(f"\n{'='*50}")
    print(f"  模拟结束！共运行 {round_num} 轮")
    print(f"  日志保存在：{log_file}")
    print(f"{'='*50}")
    return log_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="增强版模拟运行器（持续运行）")
    parser.add_argument("--agents", type=str, help="角色设定文件路径")
    parser.add_argument("--log-dir", type=str, help="日志目录")
    parser.add_argument("--interval", type=int, default=5, help="每轮间隔秒数（默认5）")
    args = parser.parse_args()
    run_simulation(args.agents, args.log_dir, args.interval)