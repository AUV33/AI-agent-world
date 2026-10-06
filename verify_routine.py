import enhanced_agent_factory as f
f.load_enhanced_agents('data/AuvAgents.json')
from enhanced_engine import agents, envs

print("=== routine 加载 + 随模拟时间变化 ===")
for name in ['AUV', '3A', 'sagi', '蜂兵老师', 'AUV小姨', '躺啊堂']:
    a = agents[name]
    print(f"\n[{name}] routine段数={len(a.life_state.routine)}  初始场景={a.envName}")
    for t in ['2026-09-29 09:00', '2026-09-29 13:00', '2026-09-29 19:00', '2026-09-29 23:00']:
        st = a.life_state.get_current_state(t)
        print(f"   {t} -> {st['activity'][:24]:24} | {st['location']}")

print("\n=== 场景注册检查（routine 引入的新场景应已注册）===")
for s in ['上海-3A家', '泾县-蜂兵家', '上海-签证官住处']:
    print(f"   {s}: {'已注册' if s in envs.get_all_envNameList() else '缺失!!'}")
