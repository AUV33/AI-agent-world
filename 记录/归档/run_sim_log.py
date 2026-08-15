# -*- coding: utf-8 -*-
"""
run_sim_log.py —— 运行致敬传奇AI模拟，并自动保存"原始记录"日志
=====================================================================
用法：
    python run_sim_log.py [轮数] [日志文件路径] [--quiet]
        - 不传轮数：无限运行，按 Ctrl+C 停止
        - 传轮数：跑满 N 轮后自动停止
        - --quiet：后台模式，只写日志文件（不写控制台）
        - 日志默认保存到 记录\原始日志\致敬传奇AI_原始记录_时间戳.txt

跑完后，再用 story_converter.py 把这份原始记录生成成故事：
    python story_converter.py --light-novel <刚才的日志> <故事输出.txt>
=====================================================================
"""
import sys
import os
import time
import datetime

PROJ = r"D:\致敬传奇AI项目"
DEFAULT_OUT_DIR = r"D:\致敬传奇AI项目\记录\原始日志"


def main():
    args = sys.argv[1:]
    quiet = "--quiet" in args
    args = [a for a in args if a != "--quiet"]
    rounds = None
    if args and args[0].isdigit():
        rounds = int(args[0])
        args = args[1:]
    log_path = args[0] if args else os.path.join(
        DEFAULT_OUT_DIR,
        "致敬传奇AI_原始记录_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt")

    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    # 先打开日志文件；quiet 模式下直接作为 stdout（行缓冲，实时落盘）
    logf = open(log_path, "w", encoding="utf-8", buffering=1)
    if quiet:
        sys.stdout = logf
        sys.stderr = logf

    sys.path.insert(0, PROJ)
    os.chdir(PROJ)

    import caller as caller_mod
    _orig = caller_mod.call_model

    def call_with_retry(*args, **kwargs):
        last = None
        for i in range(4):
            try:
                r = _orig(*args, **kwargs)
                if isinstance(r, dict) and "choices" in r:
                    return r
                last = r
                print(f"[重试 {i+1}/4] API 未返回正常结果，稍后重试", flush=True)
            except Exception as e:
                last = e
                print(f"[重试 {i+1}/4] 异常：{e}", flush=True)
            time.sleep(2)
        if isinstance(last, Exception):
            raise last
        return last

    caller_mod.call_model = call_with_retry

    import agent_factory
    agent_factory.load_AuvAgents_from_json("japanAgents.json")
    agent_factory.update_envs_with_agents_info()
    print(f"== 已加载 {len(agent_factory.agents)} 个角色 ==", flush=True)
    print(f"== 原始记录将保存到：{log_path} ==", flush=True)

    try:
        step = 0
        while True:
            step += 1
            print(f"\n========== 第 {step} 轮 ==========", flush=True)
            agent_factory.run_step()
            print(f"========== 第 {step} 轮结束 ==========", flush=True)
            if rounds and step >= rounds:
                break
    except KeyboardInterrupt:
        print("\n== 已手动停止 ==", flush=True)
    finally:
        logf.write(f"== 原始记录已保存：{log_path} ==\n")
        logf.flush()
        logf.close()
        if quiet:
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__


if __name__ == "__main__":
    main()
