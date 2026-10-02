# -*- coding: utf-8 -*-
"""端到端对照：psychology_enabled 关 vs 开，同一负性消息下 agent 的对外输出差异。

验证：
  ① 开关关 ⇒ agent.psych is None（逐字回退旧行为，零心理引擎开销）
  ② 开关开 ⇒ 收到负性消息后 self.psych.S>0、vent_pressure 上升
  ③ 出站纪律生效（输出不含【】方括号标注、不泄露"我读到了/我在想"）
使用 caller.py 默认的 hy3 KEY（腾讯 LKEAP）。
"""
import io
import os
import sys
import contextlib

PROJ = os.path.dirname(os.path.abspath(__file__)) + "/.."
sys.path.insert(0, PROJ)

import enhanced_engine
import enhanced_agent_factory
from enhanced_engine import agents, envs, msgCenter

AGENTS_FILE = os.path.join(PROJ, "data", "demo_agents.json")
INJECT_FROM = "测试伙伴"
INJECT_MSG = "你又忘了说好的事，我特别失望"


def reset_and_load(enable):
    enhanced_engine.PSYCHOLOGY_ENABLED = enable
    agents.clear()
    envs.env.clear()
    msgCenter.paddingMsgList.clear()
    enhanced_agent_factory.load_enhanced_agents(AGENTS_FILE)
    return list(agents.keys())[0]


def run_once(enable):
    name = reset_and_load(enable)
    a = agents[name]
    msgCenter.send_message_by_msg(INJECT_FROM, name, INJECT_MSG)
    env_info = envs.get_env(a.envName) or "这里没有人"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out = a.get_action(env_info, "第1轮 第1天 09:00", world=None)
    return name, a, out


def _check_outbound(text):
    """出站纪律粗检：不含【】方括号标注、不含内部过程泄露。"""
    has_bracket = "【" in (text or "") and "】" in (text or "")
    leak = ("我读到了" in (text or "")) or ("我在想" in (text or ""))
    return (not has_bracket), (not leak)


if __name__ == "__main__":
    try:
        n1, a1, o1 = run_once(False)
        ok_b, ok_l = _check_outbound(o1)
        print("===== 开关关 =====")
        print("target:", n1, "| psych is None:", a1.psych is None)
        print("出站纪律(无方括号/无泄露):", ok_b, ok_l)
        print("OUT:", (o1 or "")[:600])
    except Exception as e:
        print("关 失败:", repr(e))

    try:
        n2, a2, o2 = run_once(True)
        ok_b, ok_l = _check_outbound(o2)
        print("\n===== 开关开 =====")
        print("target:", n2, "| psych is not None:", a2.psych is not None)
        if a2.psych:
            print("收到负性消息后 S=%.2f vent=%.3f" % (a2.psych.S, a2.psych.vent_pressure()))
        print("出站纪律(无方括号/无泄露):", ok_b, ok_l)
        print("OUT:", (o2 or "")[:600])
    except Exception as e:
        print("开 失败:", repr(e))

    print("\n[提示] 两侧 OUT 应不同：开侧应体现被积压/更直接，且都不泄露内部材料。")
