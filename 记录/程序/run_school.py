# -*- coding: utf-8 -*-
"""
run_school.py —— 运行"明远中学 302 寝室"场景（单步记录模式）
=====================================================================
用法：
    python run_school.py [轮数] [--quiet]
        - 不传轮数：无限运行，按 Ctrl+C 停止
        - 传轮数：跑满 N 轮后自动停止
        - --quiet：后台模式，只写日志文件
        - 日志默认保存到 记录\原始日志\明远中学_原始记录_时间戳.txt
设定文件：D:\\致敬传奇AI项目\\schoolAgents.json
每轮 = 所有角色依次单独行动（思考/记忆/动作/场景状态），
原始记录只记录每个角色自己的行动，不做群体叙事。
每轮结束后自动检测"剧情中出现的新角色"（消息收件人/好友请求对象），
实时生成详细人设并加入模拟，后续轮次该角色会按人设正常行动。
=====================================================================
"""
import sys
import os
import time
import datetime
import re

PROJ = r"D:\致敬传奇AI项目"
HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(PROJ, "schoolAgents.json")
DEFAULT_OUT_DIR = os.path.join(PROJ, "记录", "原始日志")


def make_time_label(step, start="14:00", hours_per_round=1):
    """模拟时钟：第 step 轮的模拟时间标签（从 start 开始，每轮推进 hours_per_round 小时）。"""
    h0, m0 = map(int, start.split(":"))
    total_min = h0 * 60 + m0 + (step - 1) * hours_per_round * 60
    day = total_min // (24 * 60) + 1
    rem = total_min % (24 * 60)
    return f"第{day}天 {rem // 60:02d}:{rem % 60:02d}"



def evolve_all(agents, agents_path, cg):
    """评估全员近期经历是否导致人设演变，更新并持久化人设。"""
    import json as _json
    changed = []
    for name, ag in agents.items():
        try:
            result = cg.evolve_persona(name, ag.persona, ag.memory)
        except Exception as e:
            print(f"[演变] {name} 评估失败: {e}", flush=True)
            continue
        result = (result or "").strip()
        if "无明显变化" in result or len(result) < 10:
            continue
        if "【近况与变化】" in ag.persona:
            ag.persona = re.sub(r"\n\n【近况与变化】[^\n]*?(?=\n\n【|\Z)", "", ag.persona, flags=re.S)
        ag.persona = ag.persona.rstrip() + "\n\n" + result
        changed.append(name)
    if changed:
        try:
            data = _json.load(open(agents_path, encoding="utf-8"))
            for d in data:
                if d.get("name") in agents and d["name"] in changed:
                    d["persona"] = agents[d["name"]].persona
            _json.dump(data, open(agents_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[演变] 持久化失败: {e}", flush=True)
        print(f"== 人设演变：{'、'.join(changed)} ==", flush=True)
    return changed

def main():
    args = sys.argv[1:]
    quiet = "--quiet" in args
    args = [a for a in args if a != "--quiet"]
    evolve = 3  # 每 N 轮评估一次人设演变（0 关闭）
    if "--evolve" in args:
        j = args.index("--evolve")
        try:
            evolve = int(args[j + 1]) if j + 1 < len(args) else 3
        except ValueError:
            evolve = 3
        args = args[:j] + args[j + 2:]
    start_time = "14:00"
    if "--start" in args:
        j = args.index("--start")
        start_time = args[j + 1] if j + 1 < len(args) else "14:00"
        args = args[:j] + args[j + 2:]
    rounds = None
    if args and args[0].isdigit():
        rounds = int(args[0])
        args = args[1:]
    log_path = args[0] if args else os.path.join(
        DEFAULT_OUT_DIR,
        "明远中学_原始记录_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt")

    # 进程锁：防止环境派生的影子进程与主进程竞争写同一日志（后到者自动退出）
    import msvcrt
    LOCK_PATH = os.path.join(HERE, ".run_school.lock")
    try:
        _lockf = open(LOCK_PATH, "a+", encoding="utf-8")
        msvcrt.locking(_lockf.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        print("== 已有另一个 run_school 实例在运行，本实例退出 ==", flush=True)
        sys.exit(0)

    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    logf = open(log_path, "w", encoding="utf-8", buffering=1)

    class _Tee:
        """同时写多个输出（控制台 + 日志文件），保证前台运行也落盘。"""
        def __init__(self, *files):
            self.files = files
        def write(self, s):
            for f in self.files:
                try:
                    f.write(s)
                except Exception:
                    pass
        def flush(self):
            for f in self.files:
                try:
                    f.flush()
                except Exception:
                    pass

    if quiet:
        sys.stdout = logf
        sys.stderr = logf
    else:
        sys.stdout = _Tee(sys.__stdout__, logf)
        sys.stderr = _Tee(sys.__stderr__, logf)

    sys.path.insert(0, PROJ)
    os.chdir(PROJ)

    import caller as caller_mod
    _orig = caller_mod.call_model

    def call_with_retry(*a, **kw):
        last = None
        for i in range(6):
            try:
                r = _orig(*a, **kw)
                content = ""
                try:
                    content = r["choices"][0]["message"]["content"] or ""
                except Exception:
                    pass
                if isinstance(r, dict) and "choices" in r and content.strip():
                    return r
                last = r
                print(f"[重试 {i+1}/4] API 返回为空内容，稍后重试", flush=True)
            except Exception as e:
                last = e
                print(f"[重试 {i+1}/4] 异常：{e}", flush=True)
            time.sleep(3)
        if isinstance(last, Exception):
            raise last
        return last

    caller_mod.call_model = call_with_retry

    import agent_factory
    agent_factory.load_AuvAgents_from_json(CONFIG)
    agent_factory.update_envs_with_agents_info()
    print(f"== 已加载 {len(agent_factory.agents)} 个角色（明远中学）· 单步记录模式 ==", flush=True)
    print(f"== 原始记录将保存到：{log_path} ==", flush=True)

    import character_generator as cg
    try:
        step = 0
        last_pos = 0
        while True:
            step += 1
            print(f"\n========== 第 {step} 轮 | {make_time_label(step, start_time)} ==========", flush=True)
            agent_factory.run_step(make_time_label(step, start_time))
            print(f"========== 第 {step} 轮结束 ==========", flush=True)
            logf.flush()
            with open(log_path, encoding="utf-8") as _f:
                _f.seek(last_pos)
                _new = _f.read()
                last_pos = _f.tell()
            new_names = cg.sync_new_chars(_new, agent_factory.agents, CONFIG)
            if evolve > 0 and step % evolve == 0:
                evolve_all(agent_factory.agents, CONFIG, cg)
            if new_names:
                print(f"== 剧情新角色已生成并加入模拟：{'、'.join(new_names)} ==", flush=True)
            if rounds and step >= rounds:
                break
    except KeyboardInterrupt:
        print("\n== 已手动停止 ==", flush=True)
    finally:
        logf.write(f"== 原始记录已保存：{log_path} ==\n")
        logf.flush()
        logf.close()
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__


if __name__ == "__main__":
    main()
