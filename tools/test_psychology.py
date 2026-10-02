# -*- coding: utf-8 -*-
"""core/psychology 的对照测试（不调 LLM，纯本地）。

验证：
  ① 事件解释层不把示好判成责备（mizuse 的学费实例）
  ② 心理引擎可复现（同样的输入序列 ⇒ 同样的状态，无随机源）
  ③ 连续负性会累积抑制池 S、外化压力上升
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.psychology import Appraisal, parse_event


def test_event_parse():
    # ① 示好不应被判成责备
    r = parse_event("我有点想你了")
    assert r["event"] == "示好", r
    assert r["desirability"] > 0, r
    # 否定护栏：我不想你了 不应判示好
    r2 = parse_event("我不想你了")
    assert r2["event"] is None or r2["desirability"] <= 0, r2
    # 承诺未兑现
    r3 = parse_event("你又忘了说好的事")
    assert r3["event"] == "承诺未兑现", r3
    print("[OK] event_parse: 示好 / 否定护栏 / 承诺未兑现 正确")


def test_reproducible():
    # ② 同样输入序列 ⇒ 同样状态（无随机源）
    seq = ["你又忘了说好的事", "我特别累", "你总是这样", "算了"]
    def run():
        a = Appraisal(persona_params={})
        for s in seq:
            a.on_message(s)
        return a.snapshot()
    s1, s2 = run(), run()
    assert s1 == s2, (s1, s2)
    print("[OK] appraisal 可复现:", s1)


def test_negative_accumulates():
    # ③ 连续负性 ⇒ 抑制池 S 上升、vent_pressure 上升
    a = Appraisal(persona_params={})
    for s in ["你又忘了", "你总是这样", "我特别累", "你根本不在乎"]:
        a.on_message(s)
    snap = a.snapshot()
    assert snap["S"] > 0, snap
    assert a.vent_pressure() > 0, snap
    line = a.render()
    print("[OK] 负性累积 S=%.2f vent=%.3f render=%r" % (snap["S"], a.vent_pressure(), line))


if __name__ == "__main__":
    test_event_parse()
    test_reproducible()
    test_negative_accumulates()
    print("ALL PASS")
