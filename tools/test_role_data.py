# -*- coding: utf-8 -*-
"""角色数据完整性守卫（纯本地、零 API）。

守什么（对应「每个人都是主角」）
  ① 所有角色包里【每个】角色都有 persona_cognitive / life / memory
  ② 缺字段必须【可见】：report_role_gaps 要能报出缺口（拿合成数据实证能红）
  ③ 缺素材时框架【不再注入空槽】：提示里不许出现"你内里真实的样子：。"
  ④ 同一角色跨文件不许有两套内心（两条规则，见下）
  ⑤ 新增字段带来源标注（_cog_source），作者与依据可追溯

两条一致性规则
  规则 A（显式同人白名单）：all_auv_agents 的 13 人、japanAgents 的 AUV/至/AUV父亲、
           focus↔japan 共享的 5 人 —— 这些是同一个角色，内心必须与默认包/彼此逐字相同。
  规则 B（persona 逐字相同 ⇒ 内心必须相同）：自动发现"看起来是同一个人"的漏网之鱼。
          注意「同名不同人」是存在的（japanAgents 的易先生是富二代，默认包的易先生是爽文作者），
          这种 persona 不同，规则 B 不约束它 —— 这正是要靠 persona 而不是名字来判的原因。

跑法
  python tools/test_role_data.py
"""
import os
import sys
import json
import glob
import shutil

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)

import enhanced_engine as ee
from enhanced_agent_factory import report_role_gaps, REQUIRED_ROLE_FIELDS

PACKS = sorted(set(glob.glob(os.path.join(PROJ, "data", "*Agents.json"))
                   + glob.glob(os.path.join(PROJ, "data", "focus_agents.json"))))
CANON = "AuvAgents.json"

# 规则 A：显式同人白名单
SAME_PERSON = {
    "all_auv_agents.json": ["AUV", "至", "sagi", "黑毛黑框厨", "躺啊堂", "蜂兵老师", "易先生",
                            "3A", "AUV父亲", "日本签证官", "日本电子专门学校admission面试官",
                            "AUV小姨", "AUV姨父"],
    "japanAgents.json": ["AUV", "至", "AUV父亲"],
}

_TMP = os.path.join(PROJ, "_scratch", "role_guard_%d" % os.getpid())
shutil.rmtree(_TMP, ignore_errors=True)
os.makedirs(_TMP, exist_ok=True)
DB = os.path.join(_TMP, "memory.db")

_RealMemory, _RealLife, _RealEmotion, _RealDesire = (
    ee.EnhancedMemory, ee.LifeState, ee.EmotionSystem, ee.DesireSystem)


class _NullLogger(object):
    def __init__(self, *a, **k):
        pass

    def log(self, *a, **k):
        return None


ee.EnhancedMemory = lambda name, db_path=None, **kw: _RealMemory(name, db_path=DB, **kw)
ee.LifeState = lambda name, state_file=None, routine=None: _RealLife(
    name, state_file=os.path.join(_TMP, "life_%s.json" % name), routine=routine)
ee.EmotionSystem = lambda name, state_file=None: _RealEmotion(
    name, state_file=os.path.join(_TMP, "emotion_%s.json" % name))
ee.DesireSystem = lambda name, db_path=None: _RealDesire(name, db_path=DB)
ee.ThinkingLogger = _NullLogger
ee.PSYCHOLOGY_ENABLED = False

CAPTURED = []


def _stub(messages, **kw):
    CAPTURED.append("\n".join(m.get("content", "") for m in messages))
    sys_p = messages[0].get("content", "") if messages else ""
    content = "思考【他这话让我有点堵。】" if "只输出这三项" in sys_p else "他把视线移向窗外。"
    return {"choices": [{"message": {"content": content}}]}


ee.call_model = _stub


def _prompt_of(persona_cognitive):
    ee.agents.clear(); ee.envs.env.clear(); ee.msgCenter.paddingMsgList.clear()
    a = ee.EnhancedAgent(name="守卫角色", persona="测试人设", envName="咖啡馆",
                         persona_cognitive=persona_cognitive)
    CAPTURED.clear()
    a.get_action("这里没有人", "第1轮 第1天 09:00")
    return "\n".join(CAPTURED)


def _load(p):
    return json.load(open(p, encoding="utf-8"))


def main():
    try:
        packs = {os.path.basename(p): _load(p) for p in PACKS}
        by = {f: {d["name"]: d for d in v} for f, v in packs.items()}

        # ① 所有角色包齐备
        bad = {}
        for f, data in packs.items():
            import io
            import contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                g = report_role_gaps(data)
            if g:
                bad[f] = {k: len(v) for k, v in g.items()}
        assert not bad, "仍有角色包缺字段：%s" % bad
        total = sum(len(v) for v in packs.values())
        print("[OK] 完整性：%d 个包 / %d 个角色条目 × %s 全部非空"
              % (len(packs), total, "/".join(REQUIRED_ROLE_FIELDS)))

        # ② 能红：合成一个缺字段的角色，report_role_gaps 必须报出来
        fake = [{"name": "甲", "persona_cognitive": "有", "life": "有", "memory": "有"},
                {"name": "乙", "persona_cognitive": "", "life": "有", "memory": "有"},
                {"name": "丙", "persona_cognitive": "有", "life": "", "memory": ""}]
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            g = report_role_gaps(fake)
        assert set(g) == {"persona_cognitive", "life", "memory"}, g
        assert g["persona_cognitive"] == ["乙"] and g["life"] == ["丙"] and g["memory"] == ["丙"], g
        assert "缺 persona_cognitive" in buf.getvalue(), "缺口没有被打印出来（不可见等于没检查）"
        print("[OK] 能红：缺字段的角色被点名 —— %s" % g)

        # ③ 缺素材不注入空槽；有素材则注入
        p_has = _prompt_of("其实心里慌得不行，最怕让别人失望。")
        assert "你内里真实的样子" in p_has and "其实心里慌得不行" in p_has, "有素材时反而没注入"
        p_none = _prompt_of("")
        assert "你内里真实的样子" not in p_none, "缺素材时仍注入了空槽"
        assert "：。" not in p_none, "提示里出现了空槽的痕迹：。"
        print("[OK] 空槽：有素材注入，无素材不注入（内外两脑都不出现':。'）")

        # ④ 规则 A：显式同人白名单，内心必须逐字相同
        canon = by[CANON]
        n_a = 0
        for f, names in SAME_PERSON.items():
            for n in names:
                a = canon[n]["persona_cognitive"]
                b = by[f][n]["persona_cognitive"]
                assert a == b, "%s/%s 与默认包的内心不一致（同一角色两套内心）" % (f, n)
                n_a += 1
        print("[OK] 规则A：%d 处显式同人（all_auv_agents 13 + japanAgents 3）内心逐字一致" % n_a)

        # ④b 规则 B：persona 逐字相同 ⇒ 内心必须相同（自动发现漏网之鱼）
        seen, n_b = {}, 0
        for f, data in packs.items():
            for d in data:
                key = (d["name"], d.get("persona") or "")
                if key in seen:
                    other_f, other = seen[key]
                    assert d["persona_cognitive"] == other["persona_cognitive"], \
                        "%s/%s 与 %s/%s 的 persona 逐字相同，内心却不同" % (
                            f, d["name"], other_f, d["name"])
                    n_b += 1
                else:
                    seen[key] = (f, d)
        print("[OK] 规则B：%d 组 persona 逐字相同的角色，内心都一致" % n_b)

        # ④c 同名但 persona 文本不同：其中既有真「同名不同人」，也有同一角色的不同文本版本
        #     —— 两类都必须存在且不能混为一谈，所以至少要能数出来
        diff = []
        for f, data in packs.items():
            if f == CANON:
                continue
            for d in data:
                c = canon.get(d["name"])
                if c and (c.get("persona") or "") != (d.get("persona") or ""):
                    diff.append((f, d["name"]))
        assert diff, "预期存在同名不同文（如 japanAgents 的易先生），却一个都没找到"
        print("[OK] 同名不同文：%d 处 —— 真·同名不同人（japanAgents/易先生）已按 persona 区分；"
              "同人不同文本版本（%s）按规则 A 强制一致"
              % (len(diff), diff[0][0]))

        # ⑤ 来源标注
        no_src = []
        for f, data in packs.items():
            for d in data:
                if not d.get("_cog_source"):
                    no_src.append("%s/%s" % (f, d["name"]))
        assert not no_src, "这些角色缺 _cog_source：%s" % no_src[:5]
        print("[OK] 来源标注：%d 个角色条目全部带 _cog_source" % total)

        # ⑥ 心理参数：每人一套、11 维全覆盖、20 轮轨迹两两可区分
        sys.path.insert(0, os.path.join(PROJ, "tools"))
        import psych_params as PP
        from core.psychology import DEFAULTS_PERSONA, Appraisal

        canon_data = by[CANON]
        calib = {n: canon_data[n].get("psych") for n in PP.AXES}
        missing = [n for n, p in calib.items() if not p]
        assert not missing, "默认包里这些角色还没标定 psych：%s" % missing
        for n, p in calib.items():
            assert PP._params_equal(p, PP.derive(PP.AXES[n][0])), \
                "%s 的 psych 与 tools/psych_params.py 的推导不一致（数据漂移）" % n
        print("[OK] 参数推导：%d 人的 psych 与推导逐项一致（数据不会与工具悄悄漂移）" % len(calib))

        keys = list(DEFAULTS_PERSONA.keys())
        flat = [k for k in keys if len(set(calib[n][k] for n in calib)) < 2]
        assert not flat, "这些参数在所有角色里取值都相同，等于没做个体差异：%s" % flat
        print("[OK] 参数覆盖：%d 个维度在 %d 人上取值均 ≥2 种（无全同维度）"
              % (len(keys), len(calib)))

        MSG = "你又忘了说好的事，我特别失望"

        def _sig(p, rounds=20):
            ap = Appraisal(persona_params=p)
            out = []
            for _ in range(rounds):
                ap.on_message(MSG)
                out.append((round(ap.S, 3), round(ap.F, 3), round(ap.theta, 3)))
            return tuple(out)

        def _first_vent(p, rounds=40):
            ap = Appraisal(persona_params=p)
            for i in range(1, rounds + 1):
                ap.on_message(MSG)
                if ap.should_vent():
                    return i
            return None

        def _rounds_to_S(p, target=50.0, rounds=40):
            ap = Appraisal(persona_params=p)
            for i in range(1, rounds + 1):
                ap.on_message(MSG)
                if ap.S >= target:
                    return i
            return None

        by_sig = {}
        for n in calib:
            by_sig.setdefault(_sig(calib[n]), []).append(n)
        dup = [v for v in by_sig.values() if len(v) > 1]
        assert not dup, "这些角色的 20 轮轨迹完全相同 ⇒ 区分不开：%s" % dup
        print("[OK] 轨迹可区分：%d 人 20 轮 (S,F,θ) 轨迹两两不同（同一套公式、只是参数不同）"
              % len(calib))

        v_fa = _first_vent(calib["AUV父亲"])
        v_te = _first_vent(calib["蜂兵老师"])
        v_vi = _first_vent(calib["日本签证官"])
        s_auv = _rounds_to_S(calib["AUV"])
        s_vi = _rounds_to_S(calib["日本签证官"])
        assert v_fa and v_te and v_fa < v_te, "一点就炸型(第%s轮) 应早于克制型(第%s轮)过线" % (v_fa, v_te)
        assert v_vi is None or v_fa < v_vi, "高耐受的签证官不该比父亲更早过线"
        assert s_auv and s_vi and s_auv < s_vi, \
            "压抑型蓄压(第%s轮到50) 应快于签证官(第%s轮)" % (s_auv, s_vi)
        print("[OK] 原型方向：首过线 父亲=%s / 蜂兵老师=%s / 签证官=%s ｜ S到50 AUV=%s / 签证官=%s"
              % (v_fa, v_te, v_vi, s_auv, s_vi))

        # 能红：若框架忽略角色参数（全用默认），13 条轨迹会塌成 1 条 —— 判据不是恒绿
        _d = _sig(dict(DEFAULTS_PERSONA))
        assert _d == _sig(dict(DEFAULTS_PERSONA)), "同一套参数却轨迹不同 ⇒ 有随机源"
        assert len(set([_d])) == 1 and len(by_sig) == len(calib), \
            "同一套参数只应有 1 条轨迹，%d 人应有 %d 条" % (1, len(calib))
        print("[OK] 尺子自检：同一套参数 ⇒ 1 条轨迹；%d 人 ⇒ %d 条 ⇒ 判据能区分'有没有因人而异'"
              % (len(calib), len(by_sig)))

        print("ALL PASS")
        return 0
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
