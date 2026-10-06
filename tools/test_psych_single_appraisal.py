# -*- coding: utf-8 -*-
"""心理引擎「一条消息只评价一次」回归守卫（纯本地、零 API、不碰生产数据）。

守的是什么
  get_action 每收到 1 条 IM 消息，只能调用 on_message 一次。
  历史 bug：同一条消息被评价两次 ⇒ S/C/F 双倍累积，直接污染所有"心理引擎开 vs 关"的对照结论。

为什么这把尺子能红
  末尾用【同一套判据】去量一个"故意双计"的参照物，必须判为不合格。
  如果连双计都判合格，说明判据恒绿 = 等于没检查，脚本自己失败。

跑法
  python tools/test_psych_single_appraisal.py
"""
import os
import sys
import json
import shutil

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)

import enhanced_engine as ee
from core.psychology import Appraisal

MSG = "你又忘了说好的事，我特别失望"
FROM = "测试伙伴"
NAME = "回归守卫角色"

# 落盘目标放仓库内的 _scratch/（.gitignore 已忽略）；不用系统 Temp：沙箱下 sqlite 打不开。
_TMP = os.path.join(PROJ, "_scratch", "psych_guard_%d" % os.getpid())
shutil.rmtree(_TMP, ignore_errors=True)
os.makedirs(_TMP, exist_ok=True)

# ——— 把落盘目标全改到临时目录：守卫绝不污染 memory.db / thinking_*.jsonl / life_*.json ———
_RealMemory = ee.EnhancedMemory
_RealLife = ee.LifeState
_RealEmotion = ee.EmotionSystem
_RealDesire = ee.DesireSystem


class _NullLogger(object):
    """思考日志桩：不落盘。"""

    def __init__(self, *a, **k):
        pass

    def log(self, *a, **k):
        return None


ee.EnhancedMemory = lambda name, db_path=None, **kw: _RealMemory(
    name, db_path=os.path.join(_TMP, "memory.db"), **kw)
ee.LifeState = lambda name, state_file=None, routine=None: _RealLife(
    name, state_file=os.path.join(_TMP, "life_%s.json" % name), routine=routine)
ee.EmotionSystem = lambda name, state_file=None: _RealEmotion(
    name, state_file=os.path.join(_TMP, "emotion_%s.json" % name))
ee.DesireSystem = lambda name, db_path=None: _RealDesire(
    name, db_path=os.path.join(_TMP, "memory.db"))
ee.ThinkingLogger = _NullLogger
# 心理状态落盘改到临时目录：守卫不往仓库里写 psych_*.json
ee.PSYCH_STATE_DIR = _TMP


def _state_path(name):
    return os.path.join(_TMP, "psych_%s.json" % name)


def _stub_call_model(messages, **kw):
    """桩掉 LLM（本守卫不调云）：内心脑给 思考【…】，对外脑给一句对外言行。"""
    sys_p = messages[0].get("content", "") if messages else ""
    if "只输出这三项" in sys_p:
        content = "思考【他这话让我有点堵，先不吭声。】"
    else:
        content = "他把视线移向窗外，隔了会儿才开口。"
    return {"choices": [{"message": {"content": content}}]}


ee.call_model = _stub_call_model


def _fresh_agent(with_psych, name=NAME, psych=None, fresh_state=True):
    """构造一个干净角色，并塞进 1 条【尚未被评价】的 IM 消息。

    fresh_state=True（默认）先删掉该角色的状态文件，保证每步都从零状态起算；
    落盘往返测试用 fresh_state=False，才能真正检验"读回来"。
    """
    ee.PSYCHOLOGY_ENABLED = with_psych
    ee.agents.clear()
    ee.envs.env.clear()
    ee.msgCenter.paddingMsgList.clear()
    if fresh_state:
        try:
            os.remove(_state_path(name))
        except OSError:
            pass
    a = ee.EnhancedAgent(name=name, persona="测试人设", envName="咖啡馆", psych=psych)
    ee.msgCenter.send_message_by_msg(FROM, name, MSG)
    return a


def _spy_on_message(appr):
    """外部计数：不采信引擎自报的 evaluated，直接数 Appraisal.on_message 被调了几次。"""
    box = {"n": 0}
    orig = appr.on_message

    def counted(*a, **k):
        box["n"] += 1
        return orig(*a, **k)

    appr.on_message = counted
    return box


def _run_turn(with_psych):
    """走一轮真实的 get_action；返回 (agent, 外部评价计数)。"""
    a = _fresh_agent(with_psych)
    spy = _spy_on_message(a.psych) if a.psych is not None else {"n": 0}
    a.get_action(ee.envs.get_env("咖啡馆") or "这里没有人", "第1轮 第1天 09:00")
    return a, spy


def _verdict(appr, ref):
    """判据：状态量必须等于"单计"参照（±1e-9）。"""
    return (abs(appr.S - ref.S) < 1e-9
            and abs(appr.C - ref.C) < 1e-9
            and abs(appr.F - ref.F) < 1e-9)


def main():
    try:
        # ① 关侧：开关关闭 ⇒ 不构造心理引擎（逐字回退旧行为），一条消息也不评价
        a_off, spy_off = _run_turn(False)
        assert a_off.psych is None, "关侧不应构造心理引擎"
        assert spy_off["n"] == 0, "关侧不该调用 on_message，实测 %d 次" % spy_off["n"]
        assert (a_off.psych_forensics or {}).get("enabled") is not True, a_off.psych_forensics
        print("[OK] 关侧：psych is None，评价 0 次，留痕标记未启用")

        # ② 开侧：一条消息恰好评价一次（外部计数，不采信引擎自报）
        a_on, spy_on = _run_turn(True)
        fx = a_on.psych_forensics or {}
        assert spy_on["n"] == 1, "1 条消息实际评价了 %d 次（应为 1）" % spy_on["n"]
        assert fx.get("enabled") is True, fx
        assert fx.get("evaluated") == 1, "引擎自报 evaluated=%r" % fx.get("evaluated")
        assert fx.get("tick_dt_sec") == 0.0, (
            "sim_now=None 时不该推进时间，实测 tick_dt_sec=%r" % fx.get("tick_dt_sec"))
        print("[OK] 开侧：外部计数=%d，引擎自报 evaluated=%s，sim_now=None ⇒ tick_dt_sec=0（零行为变化）"
              % (spy_on["n"], fx.get("evaluated")))

        # ③ 状态量必须与"单计"参照逐位一致（含本轮开口释放的 on_express 0.4）
        ref = Appraisal(persona_params={})
        ref.on_message(MSG)
        ref_render = ref.render()          # 代码里 render() 在 on_express 之前
        ref.on_express(0.4)                # 本轮开口 ⇒ 扣减 S/F
        assert _verdict(a_on.psych, ref), (
            "状态与单计参照不符：agent S/C/F=%.6f/%.6f/%.6f vs ref %.6f/%.6f/%.6f"
            % (a_on.psych.S, a_on.psych.C, a_on.psych.F, ref.S, ref.C, ref.F))
        assert fx.get("render") == ref_render, (
            "注入 prompt 的那行与参照不符：%r vs %r" % (fx.get("render"), ref_render))
        print("[OK] 状态量 = 单计参照：S=%.3f C=%.4f F=%.3f，注入行与参照一致"
              % (a_on.psych.S, a_on.psych.C, a_on.psych.F))
        print("     注入 prompt 的原文：%r" % fx.get("render"))

        # ④ 尺子自检（能红）：同一判据量"故意双计"的参照物，必须判不合格
        bug = Appraisal(persona_params={})
        bug.on_message(MSG)
        bug.on_message(MSG)
        bug.on_express(0.4)
        assert not _verdict(bug, ref), "尺子对双计也判合格 ⇒ 恒绿，等于没检查"
        print("[OK] 尺子自检：双计参照被正确判为不合格（S=%.3f vs 单计 %.3f）"
              % (bug.S, ref.S))

        # ⑤ 留痕真的落进 events（WP2 的交付物）：临时 EventLog + dry-run 桩，零 API
        ee.envs.update_envInfo_by_AI = lambda *a, **k: None   # 场景改写会调 LLM，桩掉
        from event_log import EventLog
        elog = EventLog(base_dir=os.path.join(_TMP, "evlog"))
        ee.EVENT_LOG = elog
        ee.process_agent_turn(_fresh_agent(True), "第1轮 第1天 09:00",
                              dt_minutes=60, community_names=[], dry_run=True)
        elog.flush()
        recs = []
        with open(elog.raw_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    recs.append(json.loads(line))
        mine = [r for r in recs if r.get("agent") == NAME]
        assert mine, "process_agent_turn 没写出事件（多半中途抛异常，见上面 [ERROR]）"
        lt = (mine[-1].get("psych") or {}).get("last_turn") or {}
        assert lt.get("evaluated") == 1, "落盘留痕 evaluated=%r（应为 1）" % lt.get("evaluated")
        assert lt.get("render"), "落盘留痕 render 为空 ⇒ '没注入'与'没启用'仍无法区分"
        for k in ("S", "C", "F", "theta", "theta0", "M", "should_vent", "burst",
                  "vent_pressure", "outer_style_fired", "S_after", "theta_after"):
            assert k in lt, "留痕缺字段 %s" % k
        print("[OK] 留痕已落进 events：evaluated=%s vent=%.4f render=%r"
              % (lt.get("evaluated"), lt.get("vent_pressure") or 0.0,
                 (lt.get("render") or "")[:16] + "…"))

        # ⑥ 时间演化（D3=模拟时间）：tick 必须按 sim_now 之差推进 F/θ/M，且逐位可复现
        from datetime import datetime, timedelta
        MSG2 = "你总是这样，我真的受够了"
        T0 = datetime(2026, 9, 29, 9, 0)

        def _two_turn_run():
            a = _fresh_agent(True)                      # 第一轮：已注入 MSG
            a.get_action("这里没有人", "第1轮 第1天 09:00", sim_now=T0)
            ee.msgCenter.send_message_by_msg(FROM, NAME, MSG2)
            a.get_action("这里没有人", "第1轮 第1天 15:00", sim_now=T0 + timedelta(hours=6))
            return a

        a_t1 = _two_turn_run()
        fxt = a_t1.psych_forensics or {}
        assert abs((fxt.get("tick_dt_sec") or 0.0) - 6 * 3600.0) < 1e-6, (
            "第二轮应推进 6 小时，实测 tick_dt_sec=%r" % fxt.get("tick_dt_sec"))

        # 独立参照：完全按 get_action 的真实调用顺序重放（tick 发生在评价新消息【之前】）
        ref2 = Appraisal(persona_params={})
        ref2.on_message(MSG)
        ref2.on_express(0.4)                 # 第一轮：开口释放
        ref2.tick(6 * 3600.0)                # 两轮之间：只有时间在走
        ref2.on_message(MSG2)
        ref_render2 = ref2.render()          # 注入用（在开口释放之前）
        ref2.on_express(0.4)
        for k in ("S", "C", "F", "M", "theta"):
            got, want = getattr(a_t1.psych, k), getattr(ref2, k)
            assert abs(got - want) < 1e-9, "tick 接线后 %s 与独立参照不符：%r vs %r" % (k, got, want)
        assert fxt.get("render") == ref_render2, (fxt.get("render"), ref_render2)
        print("[OK] 模拟时间 tick：dt=%.0fs ⇒ S/C/F/M/θ 与独立参照逐位一致，注入行一致"
              % (fxt.get("tick_dt_sec") or 0.0))

        # 能红：若时间没推进，状态必然不同 ⇒ 这个判据不是恒绿
        no_tick = Appraisal(persona_params={})
        no_tick.on_message(MSG)
        no_tick.on_express(0.4)
        no_tick.on_message(MSG2)
        no_tick.on_express(0.4)
        assert abs(no_tick.F - ref2.F) > 1e-6, "tick 没改变任何状态 ⇒ 判据恒绿，等于没检查"
        print("[OK] 尺子自检：不推进时间 F=%.3f ≠ 推进 6h 后 F=%.3f" % (no_tick.F, ref2.F))

        # 可复现：同样输入 + 同样时间差 ⇒ 同样状态
        a_t2 = _two_turn_run()
        assert a_t1.psych.snapshot() == a_t2.psych.snapshot(), "两次同输入运行状态不一致"
        print("[OK] 可复现：两次同输入/同时间差 ⇒ 快照逐位一致")

        # ⑦ 放压阀门：过线必须【真的】泄压（而不是只换一句措辞），且是边沿触发
        MSGS = [MSG, MSG2, "第三次了，我说过多少遍", "你根本不在乎我，算了"]
        T1 = datetime(2026, 9, 29, 9, 0)

        def _world_run(rounds=100, valve=True):
            """走真实 get_action 的连续 N 轮（每轮一条负性消息 + 30 分钟模拟时间）。"""
            a = _fresh_agent(True)
            if not valve:
                # 焊死阀门 = 修复前的行为（对照臂）
                a.psych.vent = lambda *x, **k: {"S": a.psych.S, "F": a.psych.F,
                                                "theta": a.psych.theta}
            t = T1
            rows = []
            for i in range(rounds):
                ee.msgCenter.send_message_by_msg(FROM, NAME, MSGS[i % len(MSGS)])
                a.get_action("这里没有人", "第%d轮" % (i + 1), sim_now=t)
                rows.append(a.psych_forensics or {})
                t = t + timedelta(minutes=30)
            return rows

        rows_on = _world_run(100, valve=True)
        bursts = [r for r in rows_on if r.get("burst")]
        assert bursts, "100 轮负性输入一次都没爆发 ⇒ 阀门没接上"
        b0 = bursts[0]
        assert b0["S_after"] < 0.5 * b0["S"], (
            "爆发后 S 没泄掉：%.2f → %.2f" % (b0["S"], b0["S_after"]))
        assert b0["theta_after"] > b0["theta"], (
            "爆发后 θ 没回升：%.2f → %.2f" % (b0["theta"], b0["theta_after"]))
        capped_on = sum(1 for r in rows_on if (r.get("S") or 0) >= 99.99)
        assert capped_on == 0, "开了阀门 S 仍封顶 %d 轮" % capped_on
        assert rows_on[-1]["S"] < 70, "末轮 S=%.2f 仍长期憋着" % rows_on[-1]["S"]
        idx = [i for i, r in enumerate(rows_on) if r.get("burst")]
        gaps = [b - a for a, b in zip(idx, idx[1:])]
        assert gaps and min(gaps) >= 3, "爆发间隔过密 %r ⇒ 退化成每轮都炸" % gaps[:5]
        print("[OK] 阀门：100 轮爆发 %d 次（间隔 %s），首次 S %.1f→%.1f、θ %.1f→%.1f，"
              "全程未封顶，末轮 S=%.1f"
              % (len(bursts), gaps[:4], b0["S"], b0["S_after"], b0["theta"],
                 b0["theta_after"], rows_on[-1]["S"]))

        # 能红（对照臂 = 修复前行为）：阀门焊死 ⇒ S 必然封顶、只进不出
        rows_off = _world_run(100, valve=False)
        capped_off = sum(1 for r in rows_off if (r.get("S") or 0) >= 99.99)
        assert capped_off >= 50, (
            "焊死阀门也只封顶 %d 轮 ⇒ 判据区分不了修复前后（恒绿）" % capped_off)
        print("[OK] 尺子自检：阀门焊死（=修复前）S 封顶 %d 轮、末轮 %.1f ⇒ 与阀门开可区分"
              % (capped_off, rows_off[-1]["S"]))

        # ⑨ 状态落盘：per-agent 文件、退出程序后不清零、不同角色不互相覆盖
        a_p1 = _fresh_agent(True)                      # 干净起点
        a_p1.get_action("这里没有人", "落盘轮1")
        assert os.path.isfile(_state_path(NAME)), "没写出状态文件：%s" % _state_path(NAME)
        with open(_state_path(NAME), encoding="utf-8") as f:
            saved = json.load(f)
        a_p2 = _fresh_agent(True, fresh_state=False)   # 不删文件 ⇒ 应把状态读回来
        for k in ("S", "C", "F", "theta", "M"):
            got, want = getattr(a_p2.psych, k), float(saved[k])
            assert abs(got - want) < 1e-12, (
                "重新构造后 %s 未从文件恢复：%r vs 文件里的 %r" % (k, got, want))
        OTHER = "回归守卫角色乙"
        a_p3 = _fresh_agent(True, name=OTHER)          # 另一个角色
        a_p3.get_action("这里没有人", "落盘轮1")
        assert os.path.isfile(_state_path(OTHER)), "第二个角色没写出自己的状态文件"
        assert os.path.normcase(_state_path(NAME)) != os.path.normcase(_state_path(OTHER)), \
            "两个角色共用同一个状态文件 ⇒ 会互相覆盖"
        print("[OK] 落盘：%s 可恢复（S=%.3f），且每个角色一个文件、互不覆盖"
              % (os.path.basename(_state_path(NAME)), a_p2.psych.S))

        # 能红自检：把状态文件删掉再重构造 ⇒ 恢复必须失败（证明"能恢复"确实来自文件）
        os.remove(_state_path(NAME))
        a_p2b = _fresh_agent(True, fresh_state=False)
        assert abs(a_p2b.psych.S - float(saved["S"])) > 1e-9, (
            "状态文件已删却仍能恢复 S=%.3f ⇒ 判据没在量文件" % a_p2b.psych.S)
        print("[OK] 尺子自检：删掉状态文件后 S=%.1f（而非 %.1f）⇒ 恢复判据确实在量文件"
              % (a_p2b.psych.S, float(saved["S"])))

        # ⑩ 人设参数（D4）：同一套公式、不同角色参数 ⇒ 不同轨迹（从角色 JSON 读，不写死）
        with open(os.path.join(PROJ, "data", "AuvAgents.json"), encoding="utf-8") as f:
            _roles = dict((r["name"], r) for r in json.load(f))
        names = ("AUV", "AUV父亲", "蜂兵老师")
        calibrated = dict((n, _roles.get(n, {}).get("psych")) for n in names)
        assert all(calibrated.values()), "这三个角色都应带 psych 字段：%r" % (
            dict((k, bool(v)) for k, v in calibrated.items()))

        def _traj(p, rounds=20):
            """固定 20 轮同消息（只评价、不爆发）。记首过线轮数、S 到 50 的轮数、第 3 轮 S。

            注意：S 有 100 的封顶，撞顶后无法排序 ⇒ 不用"S 末值"当判据，
            改用不会被封顶掩盖的【蓄压速度】。
            """
            ap = Appraisal(persona_params=p or {})
            first_vent, first_s50, s3 = None, None, None
            for i in range(1, rounds + 1):
                ap.on_message("你又忘了说好的事，我特别失望")
                if first_vent is None and ap.should_vent():
                    first_vent = i
                if first_s50 is None and ap.S >= 50.0:
                    first_s50 = i
                if i == 3:
                    s3 = round(ap.S, 2)
            return {"vent": first_vent, "s50": first_s50, "s3": s3}

        r_supp = _traj(calibrated["AUV"])            # 压抑型
        r_irri = _traj(calibrated["AUV父亲"])         # 一点就炸型
        r_calm = _traj(calibrated["蜂兵老师"])        # 克制型
        r_def = _traj({})                            # 出厂默认（未标定）

        # 原型语义（只看方向，不看具体数值排序）：
        #   压抑型 = k_sup 最高（蓄压最快）；一点就炸型 = θ0 最低 + α 最高（最早过线）；克制型 = θ0 最高（最晚过线）
        # ★ 教训：早先这几条断言写的是"手工首标那一版的数值排序"（当时一点就炸 k_sup=6.0 < 克制 4.5），
        #   换成五轴推导后这层排序不再成立、守卫立刻报红。断言必须落在【语义】上，而不是某一次标定的数字上。
        p_supp, p_irri, p_calm = (calibrated["AUV"], calibrated["AUV父亲"], calibrated["蜂兵老师"])
        assert p_supp["k_sup"] >= max(p_irri["k_sup"], p_calm["k_sup"]), "压抑型的 k_sup 应最高"
        assert p_irri["theta0"] <= min(p_supp["theta0"], p_calm["theta0"]), "一点就炸型的 θ0 应最低"
        assert p_irri["alpha"] >= max(p_supp["alpha"], p_calm["alpha"]), "一点就炸型的 α 应最高"
        assert p_calm["theta0"] >= max(p_supp["theta0"], p_irri["theta0"]), "克制型的 θ0 应最高"
        assert r_irri["vent"] is not None, "一点就炸型 20 轮内都没过线 ⇒ 参数没生效"
        assert r_calm["vent"] is None or r_calm["vent"] > r_irri["vent"], (
            "克制型(首过线 %r) 不该比一点就炸型(%r) 更早过线" % (r_calm["vent"], r_irri["vent"]))
        assert r_supp["s50"] <= min(r_irri["s50"], r_calm["s50"]), (
            "压抑型蓄压应最快（S 到 50：压抑 %r / 一点就炸 %r / 克制 %r）"
            % (r_supp["s50"], r_irri["s50"], r_calm["s50"]))
        assert r_supp["s3"] >= max(r_irri["s3"], r_calm["s3"]), (
            "第 3 轮 S 压抑型应最高：%r" % [r_supp["s3"], r_irri["s3"], r_calm["s3"]])
        print("[OK] 原型语义：压抑 k_sup=%.1f/θ0=%.1f 最高蓄压；一点就炸 θ0=%.1f 最低+α=%.2f 最高 ⇒ 最早过线；"
              "克制 θ0=%.1f 最高 ｜ 首过线 一点就炸=%s 默认=%s 压抑=%s 克制=%s ｜ S到50 压抑=%s 默认=%s 一点就炸=%s 克制=%s"
              % (p_supp["k_sup"], p_supp["theta0"], p_irri["theta0"], p_irri["alpha"], p_calm["theta0"],
                 r_irri["vent"], r_def["vent"], r_supp["vent"], r_calm["vent"],
                 r_supp["s50"], r_def["s50"], r_irri["s50"], r_calm["s50"]))

        # ⑪ D7 开关：未标定角色是否启用（缺省 false=用出厂默认；true=必须标定才启用）
        a_def_agent = _fresh_agent(True)
        assert a_def_agent.psych is not None, "缺省应启用（用出厂默认）"
        assert a_def_agent.psych_params_source == "defaults", a_def_agent.psych_forensics
        ee.PSYCH_REQUIRE_CALIBRATED = True
        try:
            a_req = _fresh_agent(True)
            assert a_req.psych is None, "require_calibrated=true 时未标定角色不该启用"
            a_cal = _fresh_agent(True, psych=calibrated["AUV"])
            assert a_cal.psych is not None, "已标定角色在 require_calibrated 下仍应启用"
            assert a_cal.psych_params_source == "role_json", a_cal.psych_forensics
        finally:
            ee.PSYCH_REQUIRE_CALIBRATED = False
        # ⑩b 走真实入口：工厂加载角色 JSON ⇒ psych 必须【原值】读进 agent（框架只做读取）
        #     ★ 这里不再写死具体数值：只断言"引擎读到的 == 角色 JSON 里的"，
        #       否则参数一更新，断言就烂成假的失败（上一版写死 14.0/0.25/48.0，正是这样烂掉的）。
        import enhanced_agent_factory as fac
        _sample = [r for r in _roles.values()
                   if r["name"] in ("AUV", "AUV父亲", "蜂兵老师")]
        ee.PSYCHOLOGY_ENABLED = True
        ee.agents.clear()
        ee.envs.env.clear()
        ee.msgCenter.paddingMsgList.clear()
        fac.load_enhanced_agents_from_data(_sample)
        for _n in ("AUV", "AUV父亲", "蜂兵老师"):
            assert ee.agents[_n].psych_params_source == "role_json", "%s 的参数来源应为角色 JSON" % _n
            for _k, _v in (_roles[_n]["psych"] or {}).items():
                if _k.startswith("_"):
                    continue
                _got = ee.agents[_n].psych.p[_k]
                assert abs(_got - float(_v)) < 1e-9, \
                    "%s 的 %s 没按角色 JSON 读进引擎：%r vs %r" % (_n, _k, _got, _v)
        print("[OK] 工厂入口：三名角色 %d 个参数全部按角色 JSON 原值读进引擎（AUV k_sup=%.1f）"
              % (sum(len([k for k in (_roles[n]['psych'] or {}) if not k.startswith('_')])
                     for n in ("AUV", "AUV父亲", "蜂兵老师")),
                 ee.agents["AUV"].psych.p["k_sup"]))

        # 能红自检：三人都用出厂默认参数 ⇒ 上面的"严格排序"必然不成立（判据不是恒绿）
        _same = [_traj({})["s50"] for _ in range(3)]
        assert len(set(_same)) == 1, "同一套参数给出不同结果 ⇒ 存在随机源，判据不可信"
        assert not (_same[0] < _same[1] < _same[2]), "同参数也满足严格排序 ⇒ 判据恒绿"
        print("[OK] 尺子自检：同一套参数下排序退化为相等（%r）⇒ 差异化判据不是恒绿" % (_same,))

        print("[OK] D7 开关：缺省 params_source=%s；require_calibrated=true 时未标定即不启用、已标定照常"
              % a_def_agent.psych_params_source)

        # ⑫ 爆发线取证：单条注入离 0.7 有多远（说明短测落在静默区）
        print("[INFO] 单条注入 vent_pressure=%.4f（爆发线 0.7）⇒ 短测测不到爆发分支是设计使然"
              % (fx.get("vent_pressure") or 0.0))
        print("ALL PASS")
        return 0
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
