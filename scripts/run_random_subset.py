# -*- coding: utf-8 -*-
"""随机抽 k 个角色，连续跑 h 模拟小时（continuous_runner 的便捷入口）。

用法：
  # 先 dry-run 验证调度（桩掉 LLM，不烧 API、不需要 key）
  python scripts/run_random_subset.py --k 4 --hours 4 --dry-run

  # 真实跑（需先设置环境变量 LLM_API_KEY / MIMO_API_KEY）
  python scripts/run_random_subset.py --k 4 --hours 4
  python scripts/run_random_subset.py --k 4 --hours 4 --common-scene 咖啡馆   # 子集同场互动
"""
import os, sys, json, random, argparse

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)

import enhanced_engine
from continuous_runner import run, DEFAULT_BASE, DEFAULT_SPEED


def cleanup_test_processes(my_pid):
    """测试结束后，自动关掉所有由本脚本 / continuous_runner 启动的 python 进程
    （排除自身）。避免后台多次运行遗留进程；不会误杀其他 python（如 http.server）。"""
    if os.name != "nt":
        return
    import subprocess, json
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=30)
        data = out.stdout.strip()
        if not data:
            return
        try:
            procs = json.loads(data)
            if isinstance(procs, dict):
                procs = [procs]
        except Exception:
            return
        for p in procs:
            pid = p.get("ProcessId")
            cmd = (p.get("CommandLine") or "")
            if pid and int(pid) != my_pid and \
               ("continuous_runner" in cmd or "run_random_subset" in cmd):
                try:
                    subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                                   capture_output=True, timeout=10)
                except Exception:
                    pass
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser(description="随机抽 k 人连续跑 h 模拟小时")
    ap.add_argument("--agents", default=os.path.join(PROJ, "data", "AuvAgents.json"))
    ap.add_argument("--k", type=int, default=4, help="随机选几个人")
    ap.add_argument("--hours", type=float, default=4, help="模拟小时数")
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--speed", type=float, default=DEFAULT_SPEED)
    ap.add_argument("--common-scene", default=None, help="把子集塞进同一场景（增强互动）")
    ap.add_argument("--seed", type=int, default=None, help="随机种子（可复现）")
    ap.add_argument("--out-dir", default=None, help="事件记录输出目录")
    ap.add_argument("--max-turns", type=int, default=None, help="最多派发多少次角色行动（调试用）")
    ap.add_argument("--interval", type=float, default=None,
                    help="固定每个角色行动间隔（模拟分钟），如 60 表示每轮一小时推进")
    ap.add_argument("--dry-run", action="store_true",
                    help="桩掉 LLM，仅验证调度逻辑，不烧 API")
    ap.add_argument("--psychology", action="store_true",
                    help="开启心理引擎（OCC）：S/vent 将写入 events（覆盖 world_config.json 的 psychology_enabled）")
    ap.add_argument("--run-dir", default=None,
                    help="★ 实验隔离目录：记忆/羁绊/心理状态/事件全放这里（对照实验必用）")
    ap.add_argument("--resume", action="store_true", help="run-dir 已存在时接着跑")
    args = ap.parse_args()

    with open(args.agents, "r", encoding="utf-8") as f:
        all_data = json.load(f)
    names = [d["name"] for d in all_data]
    if args.seed is not None:
        random.seed(args.seed)
    k = min(args.k, len(names))
    subset = random.sample(names, k)
    print(f"[随机子集] 从 {len(names)} 人中抽取 {k} 人：{subset}")

    my_pid = os.getpid()
    if args.psychology:
        enhanced_engine.PSYCHOLOGY_ENABLED = True
        print("[psychology] 已开启心理引擎（OCC），S/vent 将写入 events")
    try:
        run(args.agents, base_time=args.base, speed=args.speed,
            max_hours=args.hours, max_turns=args.max_turns, dry_run=args.dry_run,
            out_dir=args.out_dir, subset=subset, common_scene=args.common_scene,
            interval_min=args.interval, run_dir=args.run_dir, resume=args.resume,
            seed=args.seed)
    finally:
        cleanup_test_processes(my_pid)


if __name__ == "__main__":
    main()
