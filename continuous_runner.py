# -*- coding: utf-8 -*-
"""continuous_runner.py - 连续时间多 Agent 运行时（方案 C）

与回合制(run_step)的本质区别：
- 没有"全局一轮"的概念；模拟时间连续推进，每个角色拥有【独立时钟】。
- 调度器每次只唤醒"最早该行动"的角色并派发；时间顺序天然交错，
  不再是"你动一下我动一下"的固定轮次与固定顺序。
- 消息异步投递：A 给 B 发消息后，消息进入 B 的收件箱；B 在自己回合感知到并自主决定
  回复，只动自己的钟（与"自我发现"对称、有上界），不强制打断/拉钟。
- 速度可配：SPEED = 每模拟分钟对应的真实秒数（默认让世界走得不快不慢）。

共享状态(envs / msgCenter / bonds / memory.db)在单线程调度下无竞态；
若日后要"真正并行思考"，可在外层套 asyncio 把 process_agent_turn 并发化
（方案 B），本文件已把每角色逻辑收敛到 process_agent_turn，便于并发复用。

记录（见 event_log.py）：每次行动都会写入结构化事件，并生成两种视图文件——
- record_by_scene.md ：📍 某一场景内，每个人都干了什么
- record_by_person.md：👤 某个人，在所有场景都干了什么
- events.jsonl      ：原始事件流，便于后续任意聚合
"""
import os, sys, time, random, json, argparse
from datetime import datetime, timedelta

PROJ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJ)

from enhanced_agent_factory import (
    load_enhanced_agents, load_enhanced_agents_from_data, update_envs_with_agents_info,
)
from enhanced_engine import (
    process_agent_turn,
    CONFIG, REFLECTION_ENABLED, REFLECTION_INTERVAL, run_global_reflection,
)
from environment import World
from time_engine import TimeEngine
from event_bus import EventBus
from event_log import EventLog
from run_monitor import RunMonitor

# ---------------- 可调参数 ----------------
DEFAULT_BASE = "2026-09-29 12:00"   # 模拟起始时刻
DEFAULT_SPEED = 0.05                # 每模拟分钟 = 0.05 真实秒 → 1 模拟小时≈3 秒
SLEEP_INTERVAL_MIN = (90, 180)      # 睡觉时两次行动间隔
AWAKE_INTERVAL_MIN = (15, 45)       # 清醒时两次行动间隔
MAX_SLEEP_REAL = 2.0                # 单次真实等待上限（秒），便于及时响应停止信号
FLUSH_EVERY = 10                    # 每多少轮落盘一次事件记录


def _interval_for(agent, sim_now):
    """根据作息决定该角色下一次行动的间隔（模拟分钟）。"""
    try:
        st = agent.life_state.get_current_state()
        activity = st.get("activity", "")
    except Exception:
        activity = ""
    if "睡觉" in activity:
        return random.uniform(*SLEEP_INTERVAL_MIN)
    return random.uniform(*AWAKE_INTERVAL_MIN)


def _fmt(sim_dt):
    return sim_dt.strftime("%Y-%m-%d %H:%M")


def reset_world_state():
    """清空全局世界状态，保证每次连续运行从干净环境开始（角色/场景/未读消息）。"""
    World().reset()


def run(agents_file, base_time=DEFAULT_BASE, speed=DEFAULT_SPEED,
        max_turns=None, max_hours=None, dry_run=False, stop_event=None,
        out_dir=None, subset=None, common_scene=None, reset_state=True):
    """连续时间多 Agent 运行时。

    新增参数：
    - max_hours     : 按模拟小时数停止（与 max_turns 二选一/并存）
    - out_dir       : 事件记录输出目录（独立结果用，默认 PROJ）
    - subset        : 只加载这些名字的角色（随机抽取的关联人物）
    - common_scene  : 把所有子集角色塞进同一场景（覆盖各自初始位置）
    - reset_state   : 运行前是否清空全局世界状态（多次运行间隔离）
    """
    elog = None
    world = World()
    bus = EventBus()
    monitor = RunMonitor()
    bus.subscribe(lambda e: e.get('kind') in ('im', 'f2f', 'move'), monitor.record_event)
    turns = 0
    try:
        if reset_state:
            reset_world_state()

        # 只加载指定子集（随机抽取的关联人物）；否则全量加载
        if subset:
            with open(agents_file, 'r', encoding='utf-8') as f:
                all_data = json.load(f)
            sel = [d for d in all_data if d['name'] in set(subset)]
            load_enhanced_agents_from_data(sel)
        else:
            load_enhanced_agents(agents_file)
        update_envs_with_agents_info()

        # 全角色名（社区名单），供闲聊/八卦提及"不在本场"的人
        try:
            with open(agents_file, 'r', encoding='utf-8') as _f:
                _all = json.load(_f)
            community_names = [d['name'] for d in _all]
        except Exception:
            community_names = list(world.agents.keys())

        # 把所有子集角色放进同一场景
        if common_scene:
            for ag in world.agents.values():
                ag.envName = common_scene
            if common_scene not in world.get_all_envNameList():
                world.add_env(common_scene, '')
            update_envs_with_agents_info()

        # 结构化事件记录：按场景 / 按人物 两种视图（独立输出目录）
        elog = EventLog(base_dir=out_dir or PROJ)
        import enhanced_engine as _ee
        _ee.EVENT_LOG = elog

        base_dt = datetime.strptime(base_time, "%Y-%m-%d %H:%M")
        # 独立调度器：只管时钟推进与派发下一个该动的角色（不含业务）
        engine_t = TimeEngine(list(world.agents.keys()), base_dt, speed)

        # dry_run：用桩替换 LLM，仅验证调度/加急/时间推进逻辑，不烧 API
        if dry_run:
            for ag in world.agents.values():
                ag.get_action = lambda envInfo, time_label="", joinable_context="", world=None, _a=ag: (
                    f"接下来一小时的动作：\n{_a.name}在{_a.envName}做日常。\n"
                    f"向【测试好友】发送【（dry-run）在呢】", _a.envName, _a.envName)
            # 场景改写与全局反思也会调 LLM，干跑时一并桩掉
            world.envs.update_envInfo_by_AI = lambda *a, **k: None

        last_reflect_hour = None
        scene_tag = f"，场景【{common_scene}】" if common_scene else ""
        print(f"连续运行时启动：基准 {base_time}，速度 {speed}s/模拟分钟，角色 {len(world.agents)} 个{scene_tag}")
        while True:
            if stop_event is not None and stop_event.is_set():
                break
            if max_turns is not None and turns >= max_turns:
                break
            if max_hours is not None and engine_t.elapsed_hours() >= max_hours:
                break

            # 派发最早该行动的角色（独立时钟 + 时间顺序交错）
            name, due = engine_t.next()
            engine_t.advance_to(due)   # 按速度真实等待并推进 sim_now

            agent = world.agents[name]
            sim_now = engine_t.sim_now
            dt = _interval_for(agent, sim_now)
            time_label = _fmt(sim_now)
            # 单角色一轮（内层→外层→落库→消息→关系→场景）
            # 注意：IM 仅为纯投递，不再强制拉接收方时钟——
            # 接收方在自己回合自主决定回复，只动自己的钟（与"自我发现"对称、有上界）
            # 单角色一轮：包裹计时与异常捕获——单轮失败不中断整体运行，但记入监控
            t0 = time.time()
            ok_turn = True
            err_turn = None
            chitchat_targets = []
            try:
                action_text, chitchat_targets = process_agent_turn(
                    agent, time_label, dt_minutes=dt, community_names=community_names,
                    dry_run=dry_run, world=world)
            except Exception as e:
                ok_turn = False
                err_turn = e
                action_text = ""
                print(f"[ERROR] 角色 {name} 行动失败：{type(e).__name__}: {e}")
            dt_real = time.time() - t0
            monitor.record_turn(name, time_label, agent.envName, action_text,
                                chitchat_targets, dt_real, dt, ok=ok_turn, error=err_turn)
            if ok_turn:
                # 事件驱动：本轮行动 / IM 发布到总线（同场景观察者经 World.perceive 看到）
                bus.publish({'kind': 'action', 'agent': name, 'scene': agent.envName,
                             'time': time_label, 'text': action_text})
                for _t in chitchat_targets:
                    bus.publish({'kind': 'im', 'frm': name, 'to': _t, 'time': time_label})

            # 排定该角色下一次行动（间隔随作息变化）
            engine_t.reschedule(name, _interval_for(agent, sim_now))

            # 周期性全局反思（按模拟小时累计；干跑时不调 LLM）
            if (not dry_run) and REFLECTION_ENABLED and REFLECTION_INTERVAL:
                elapsed_h = int((sim_now - base_dt).total_seconds() // 3600)
                if last_reflect_hour is None or elapsed_h - last_reflect_hour >= REFLECTION_INTERVAL:
                    last_reflect_hour = elapsed_h
                    try:
                        run_global_reflection(time_label)
                        monitor.record_reflection(ok=True)
                    except Exception as e:
                        monitor.record_reflection(ok=False, error=e)
                        print("[WARN] 全局反思失败：", e)

            turns += 1
            if turns % FLUSH_EVERY == 0:
                elog.flush()
    except KeyboardInterrupt:
        print("\n[停止] 连续运行时被中断（当前轮次已执行完毕）")
    finally:
        if elog is not None:
            try:
                elog.flush()
            except Exception:
                pass
        try:
            monitor.flush()
            monitor.close()
            monitor.print_summary()
        except Exception:
            pass
    print(f"连续运行时结束：共派发 {turns} 次角色行动")


def main():
    ap = argparse.ArgumentParser(description="连续时间多 Agent 运行时（方案 C）")
    ap.add_argument("--agents", default=os.path.join(PROJ, "data", "AuvAgents.json"))
    ap.add_argument("--base", default=DEFAULT_BASE, help="模拟起始时刻 YYYY-MM-DD HH:MM")
    ap.add_argument("--speed", type=float, default=DEFAULT_SPEED,
                   help="每模拟分钟对应的真实秒数（越小世界走得越快）")
    ap.add_argument("--max-turns", type=int, default=None, help="最多派发多少次角色行动（调试用）")
    ap.add_argument("--max-hours", type=float, default=None, help="按模拟小时数停止（如 1 表示跑满 1 小时）")
    ap.add_argument("--out-dir", default=None, help="事件记录输出目录（独立结果用）")
    ap.add_argument("--subset", default=None, help="只加载这些角色，逗号分隔（随机抽取的关联人物）")
    ap.add_argument("--common-scene", default=None, help="把所有子集角色塞进同一场景")
    ap.add_argument("--no-reset", action="store_true", help="运行前不重置全局世界状态")
    ap.add_argument("--dry-run", action="store_true",
                   help="用桩替换 LLM，仅验证调度逻辑，不消耗 API")
    args = ap.parse_args()
    subset = [s.strip() for s in args.subset.split(",")] if args.subset else None
    run(args.agents, base_time=args.base, speed=args.speed,
        max_turns=args.max_turns, max_hours=args.max_hours, dry_run=args.dry_run,
        out_dir=args.out_dir, subset=subset, common_scene=args.common_scene,
        reset_state=not args.no_reset)


if __name__ == "__main__":
    main()
