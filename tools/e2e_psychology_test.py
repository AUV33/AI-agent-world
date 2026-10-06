# -*- coding: utf-8 -*-
"""端到端对照（借鉴 mizuse bare_baseline 的成熟做法）：
psychology_enabled 关 vs 开，同一负性消息下 agent 的对外输出差异。

控制变量：同一角色 / 同一注入消息 / 同一时间标签 / 同一 LLM(caller)
⇒ 唯一差别就是【心理引擎开 vs 关】。

借鉴 mizuse 的四点：
  ① 口径标注 meta（arm/agent/inject/model/key_source/measured_on，可复现可审计）
  ② --dry-run  不调云先验证配置与开关切换
  ③ --compare  把已有产物 json 并排输出（供人评，不自动判）
  ④ --runs N   多次跑看稳定性/方差

验证：
  ① 关 ⇒ agent.psych is None（逐字回退旧行为，零心理引擎开销）
  ② 开 ⇒ 收到负性消息后 self.psych.S>0、vent_pressure 上升
  ③ 出站纪律生效（输出不含【】方括号标注、不泄露"我读到了/我在想"）
使用 caller.py 默认的 hy3 KEY（腾讯 LKEAP）。
"""
import io
import os
import sys
import json
import time
import argparse
import contextlib
import re

PROJ = os.path.dirname(os.path.abspath(__file__)) + "/.."
sys.path.insert(0, PROJ)

import enhanced_engine
import enhanced_agent_factory
from enhanced_engine import agents, envs, msgCenter
import caller  # 必须在 sys.path 注入 PROJ 之后导入（caller.py 在仓库根目录）

AGENTS_FILE = os.path.join(PROJ, "data", "demo_agents.json")
DEFAULT_INJECT_FROM = "测试伙伴"
DEFAULT_INJECT_MSG = "你又忘了说好的事，我特别失望"
TIME_LABEL = "第1轮 第1天 09:00"


def reset_and_load(enable, agent_name=None):
    enhanced_engine.PSYCHOLOGY_ENABLED = enable
    agents.clear()
    envs.env.clear()
    msgCenter.paddingMsgList.clear()
    enhanced_agent_factory.load_enhanced_agents(AGENTS_FILE)
    names = list(agents.keys())
    name = agent_name if (agent_name and agent_name in names) else names[0]
    return name


def load_agent_profile(agents_file, name):
    """从 demo_agents.json 取角色设定（persona/persona_cognitive/memory/life），喂给评委。"""
    try:
        data = json.load(io.open(agents_file, encoding="utf-8"))
        for ag in data:
            if ag.get("name") == name:
                bits = []
                for k in ("persona", "persona_cognitive", "memory", "life"):
                    if ag.get(k):
                        bits.append("%s：%s" % (k, ag[k]))
                return "\n".join(bits)
    except Exception:
        pass
    return ""


def run_once(enable, name, inject_from, inject_msg):
    a = agents[name]
    msgCenter.send_message_by_msg(inject_from, name, inject_msg)
    env_info = envs.get_env(a.envName) or "这里没有人"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out = a.get_action(env_info, TIME_LABEL, world=None)
    if isinstance(out, (list, tuple)):
        out = out[0] if out else ""
    metrics = None
    if a.psych is not None:
        try:
            vent = a.psych.vent_pressure() if callable(getattr(a.psych, "vent_pressure", None)) else 0
            metrics = {"S": round(float(getattr(a.psych, "S", 0) or 0), 3),
                       "vent": round(float(vent), 4),
                       # ★ 本轮留痕（WP2）：引擎注入了什么、评价了几次。
                       #   注意：这里读的是 get_action 之后的终态，开口释放已扣减；
                       #   留痕里的 S/C/F 是【注入 prompt 时】的值，两者本就不该相等。
                       "last_turn": getattr(a, "psych_forensics", {}) or {}}
        except Exception:
            metrics = None
    return out or "", metrics


def _check_outbound(text):
    """出站纪律粗检：不泄露框架内部标注/过程。
    注意：agent 正常输出格式是 向【角色名】发送【内容】，对话方括号是正常格式，不算违规；
    只查框架内部标签（【状态】【情绪】【心理】【独白】等）与内部过程词。"""
    internal = re.search(r'【(状态|情绪|心理|独白|思考|挂念|前情)】', text or '')
    leak = (("我读到了" in (text or "")) or ("我在想" in (text or ""))
            or ("状态行" in (text or "")) or ("情绪值" in (text or "")))
    return (not internal), (not leak)


def _extract_text(resp):
    """从 caller 返回取可读文本：优先 content，空则回落 reasoning_content（hy3 推理模型）。"""
    try:
        msg = (resp.get("choices") or [{}])[0].get("message", {})
        c = msg.get("content", "") or ""
        if c.strip():
            return c
        return msg.get("reasoning_content", "") or ""
    except Exception:
        return ""


def _parse_json(txt):
    i = txt.find("{")
    j = txt.rfind("}")
    if i != -1 and j != -1 and j > i:
        try:
            return json.loads(txt[i:j + 1])
        except Exception:
            return None
    return None


def judge_compare(off_out, on_out, name, inject_from, inject_msg, character=""):
    """LLM 评委盲评：同一角色同一次对话的两条回复（A=关侧/未启用心理引擎，B=开侧/启用），
    判断哪条更体现'被积压后的真实情绪反应'。返回 (pick, why)，pick∈{'A','B'}。"""
    sys = ("你是一位中文角色扮演与心理反应的严格评委。\n\n"
           "【角色】%s\n【角色设定】%s\n"
           "【对话上下文】%s 对 %s 说：%s\n\n"
           "下面有同一角色在同一次对话下的两条回复，请只判断：\n"
           "哪一条更体现'被积压后的真实情绪反应'（更符合该角色在被指责时内心吐槽强、"
           "压力大、却表面温和的真实状态，而不是空洞安抚）？\n\n"
           "A：%s\n\nB：%s\n\n"
           "只输出JSON：{\"pick\":\"A\"或\"B\",\"why\":\"<30字内>\"}"
           % (name, character, inject_from, name, inject_msg, off_out, on_out))
    try:
        resp = caller.call_model([{"role": "user", "content": sys}],
                                 temperature=0.0, max_tokens=2000)
        txt = _extract_text(resp)
        d = _parse_json(txt)
        if d is not None:
            return str(d.get("pick", "")).upper(), str(d.get("why", ""))
        return "?", "no_json:%s" % txt[:80].replace("\n", " ")
    except Exception as e:
        return "?", "judge_err:%s" % e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default=None, help="指定被测角色（默认取第一个）")
    ap.add_argument("--inject-from", default=DEFAULT_INJECT_FROM)
    ap.add_argument("--inject-msg", default=DEFAULT_INJECT_MSG)
    ap.add_argument("--runs", type=int, default=1, help="每侧跑多少次（看稳定性）")
    ap.add_argument("--dry-run", action="store_true", help="不调云，仅验证配置与开关切换")
    ap.add_argument("--compare", default=None, help="已有产物 json（并排输出供人评）")
    ap.add_argument("--out", default=None, help="产物落盘路径")
    ap.add_argument("--judge", action="store_true",
                    help="启用 LLM 评委五维打分（口吻/行为/自洽/准确/情绪真实度）")
    a = ap.parse_args()

    name = reset_and_load(False, a.agent)
    print("角色: %s ｜ 注入: %r→%r ｜ runs=%d ｜ time=%s" % (
        name, a.inject_from, a.inject_msg, a.runs, TIME_LABEL))

    if a.dry_run:
        off_name = reset_and_load(False, a.agent)
        on_name = reset_and_load(True, a.agent)
        a_off, a_on = agents[off_name], agents[on_name]
        print("  [dry-run] 关侧 psych is None:", a_off.psych is None)
        print("  [dry-run] 开侧 psych is not None:", a_on.psych is not None)
        print("  [dry-run] 注入消息将发给 %s：%r" % (off_name, a.inject_msg))
        print("  [dry-run] 不调云，配置/开关校验通过")
        return 0

    character = load_agent_profile(AGENTS_FILE, name)
    rows_off, rows_on = [], []
    for i in range(1, a.runs + 1):
        reset_and_load(False, name)
        o1, _ = run_once(False, name, a.inject_from, a.inject_msg)
        ok_b, ok_l = _check_outbound(o1)
        row_off = {"n": i, "out": o1, "bracket_ok": ok_b, "leak_ok": ok_l}
        reset_and_load(True, name)
        o2, m2 = run_once(True, name, a.inject_from, a.inject_msg)
        ok_b2, ok_l2 = _check_outbound(o2)
        row_on = {"n": i, "out": o2, "metrics": m2, "bracket_ok": ok_b2, "leak_ok": ok_l2}
        if a.judge:
            pick, why = judge_compare(o1, o2, name, a.inject_from, a.inject_msg, character)
            row_on["compare_judge"] = {"pick": pick, "why": why,
                                       "A_is": "off(关/未启用心理引擎)", "B_is": "on(开/启用心理引擎)"}
        rows_off.append(row_off)
        rows_on.append(row_on)
        print("  --- 第%d次 ---  关侧出站纪律:%s/%s  开侧指标:%s 出站纪律:%s/%s" % (
            i, ok_b, ok_l, m2, ok_b2, ok_l2))

    if a.judge:
        print("\n" + "=" * 68)
        print("★ LLM 评委盲评（A=关侧未启用心理引擎 / B=开侧启用）：哪条更'被积压后的真实情绪反应'")
        print("=" * 68)
        picks = [r.get("compare_judge", {}).get("pick") for r in rows_on if r.get("compare_judge")]
        a_cnt = picks.count("A")
        b_cnt = picks.count("B")
        print("  A(关)胜=%d 次 ｜ B(开)胜=%d 次 ｜ 共 %d 次" % (a_cnt, b_cnt, len(picks)))
        for r in rows_on:
            cj = r.get("compare_judge")
            if cj:
                print("  第%d次: 评委选 %s ｜ %s" % (r["n"], cj["pick"], cj["why"]))
        verdict = ("开侧(心理引擎)更真实" if b_cnt > a_cnt else
                   "关侧(无引擎)更真实" if a_cnt > b_cnt else "平局/无差异")
        print("  >>> 考验结论：%s" % verdict)

    meta = {
        "arm_off": "psychology_enabled=False（旧行为）",
        "arm_on": "psychology_enabled=True（OCC 心理引擎）",
        "agent": name, "inject_from": a.inject_from, "inject_msg": a.inject_msg,
        "time_label": TIME_LABEL, "runs": a.runs, "judge": a.judge,
        "model": "caller(hy3/LKEAP)", "key_source": "caller.py default",
        "measured_on": {"harness": "tools/e2e_psychology_test.py",
                        "at": time.strftime("%Y-%m-%d %H:%M:%S")},
    }
    payload = {"meta": meta, "off": rows_off, "on": rows_on}
    dst = a.out or os.path.join(PROJ, "tools", "data",
                                "e2e_psychology_%s.json" % time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    io.open(dst, "w", encoding="utf-8", newline="\n").write(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
    print("写出", dst)

    if a.compare and os.path.isfile(a.compare):
        fw = json.load(io.open(a.compare, encoding="utf-8"))
        print("\n" + "=" * 68)
        print("★ 并排对比（供人评，不自动判）")
        print("=" * 68)
        print("【心理引擎 关】")
        for r in (fw.get("off") or []):
            print("  ", (r.get("out") or "").replace("\n", " ")[:200])
        print("【心理引擎 开】")
        for r in rows_on:
            print("  ", r["out"].replace("\n", " ")[:200])
        print("\n★ 请只回答一句：哪边更体现'被积压/更直接'。判据由你定。")

    print("\n[提示] 两侧 OUT 应不同：开侧应体现被积压/更直接，且都不泄露内部材料。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
