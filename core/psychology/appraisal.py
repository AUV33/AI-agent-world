# -*- coding: utf-8 -*-
r"""appraisal · 评价 → 情绪 → 抑制负荷（本地、零 LLM、纯数值）

★ 移植自 D:\mizuse\core\appraisal.py（2026-10-02），去 person 耦合：
  - 原版 `Appraisal(persona_params=...)` 已参数化，本版原样保留；
  - `event_parse` 改为相对导入（from . import event_parse）；
  - NRC 覆盖层（lexicon_nrc_zh.json）保持"读不到就降级"的语义，不入库。

★ 这个模块是「本地机器做活着的那一半」的第一块砖。它【不调用任何模型】，
  只做数值演化，而且【没有随机源】—— 所以它的每一步都完全可复现。

依据（详见 mizuse README §七）：
  · 抑制不降低负性体验、也不反弹（Gross & Levenson 1997）
    ⇒ ★ S 不随时间自然衰减；只在【表达】时扣减
  · 抑制升高交感激活、占用工作记忆（Gross & Levenson 1993；Richards & Gross 2000）
    ⇒ ★ 存在一个与情绪强度平行的成本量 C，影响耐心与记忆质量
  · 长期/反复的负性激活会【降低攻击阈限】（Berkowitz 1989/1990）
    ⇒ ★ θ 不是常数：θ(t) = θ₀ − α × 激活基线
  · 攻击强度 ∝ 挫折强度（Dollard et al. 1939）
    ⇒ 量 F 的存在

状态量（每人一份，可选落盘到 data_dir/appraisal_state.json）：
  S       抑制池 0~100   不自然衰减；抑制时累加，表达时扣减
  C       成本   0~1     平行量；影响耐心（→θ 更低）与记忆质量
  F       挫折   0~100   慢衰减（与 S 不同：F 是可以消的）
  theta   当前攻击阈限    θ = θ₀ − α×激活基线（被压下后慢慢回升）
  M       心境  -1~1     小时-天级慢变量（t248 分层：mood）
  events  最近事件环形缓冲（用于解释"为什么她现在这样"）

人格参数（由角色 JSON 的 `psych` 字段给；缺省值保守，见 DEFAULTS_PERSONA）：
  k_sup   抑制累积系数        （压抑型偏高）
  k_cost  成本累积系数
  kappa   表达扣减系数
  beta    爆发后泄压比例
  alpha   阈限下调系数        （一点就炸型偏高）
  theta0  阈限基线            （逆来顺受型偏高）
  tau_F   挫折衰减时间常数（秒）
  tau_scale 情绪持续时间的个体缩放（1.0=文献中位数；>1=更记仇）
  tau_theta 阈限回升时间常数（秒）
  k_mood  单个事件推动心境的比例
  tau_mood 心境回落时间常数（秒）

用法：
    from core.psychology import Appraisal
    ap = Appraisal(persona_params={...})          # 参数缺省用 DEFAULTS_PERSONA
    ap.on_message("我今天特别累 什么都不想干", relevance=0.8)
    ap.on_express(0.6)
    ap.tick(3600)
    line = ap.render()        # 一行注入文案
    ap.should_vent()          # 是否该爆发
"""
import io
import json
import math
import os
import time

# ——— 缺省人格参数（★ 工程标定值，无文献依据；必须按角色重新标定）———
DEFAULTS_PERSONA = {
    "k_sup": 8.0,        # 抑制累积
    "k_cost": 0.9,       # 成本累积
    "kappa": 0.6,        # 表达扣减
    "beta": 0.3,         # 爆发后泄压
    "alpha": 0.25,       # 阈限下调
    "theta0": 65.0,      # 阈限基线
    "tau_F": 6 * 3600.0,     # 挫折衰减（兜底值；有情绪种类时按 EMO_KIND_HOURS 取）
    "tau_scale": 1.0,        # 情绪持续时间的个体缩放（1.0=文献中位数；>1=更记仇）
    "tau_theta": 12 * 3600.0,  # 阈限回升 12h
    "k_mood": 0.08,            # 单个事件把心境往它的愉悦度方向推 8%
    "tau_mood": 24 * 3600.0,   # 心境向 0 回落的时间常数（24h）
}

# ——— 事件评价用的规则词表（★ 零 LLM；可被外部覆盖）———
LEX = {
    "block": [("没睡好", 1.0), ("累", 0.8), ("加班", 0.9), ("头疼", 1.0), ("生病", 1.2),
              ("难受", 1.0), ("烦", 0.7), ("压力", 0.8), ("不顺", 0.9), ("被骂", 1.1),
              ("失败", 1.0), ("来不及", 0.8), ("搞砸", 1.2)],
    "expect": [("又", 0.6), ("还是", 0.7), ("第三次", 0.9), ("说了多少遍", 1.0),
               ("不是说了", 1.0), ("忘了", 0.8), ("没回", 0.7),
               ("没做到", 1.2), ("放鸽子", 1.2), ("食言", 1.2), ("没兑现", 1.1),
               ("失约", 1.1), ("说话不算", 1.1), ("答应过", 0.9)],
    "rel": [("你", 0.5), ("我们", 0.7), ("答应", 0.9), ("说好", 0.9), ("一直", 0.6),
            ("每次", 0.8), ("总是", 0.8)],
    "pos": [("谢谢", 0.9), ("喜欢", 1.0), ("想你了", 1.1), ("辛苦", 0.7), ("开心", 1.0),
            ("好评", 1.0), ("过了", 0.8), ("顺利", 0.9)],
    "blame_other": [("都怪", 1.0), ("因为你", 1.0), ("你总是", 0.9), ("你又", 0.8),
                    ("你根本", 1.0), ("你没", 0.6), ("你从不", 1.0)],
    "blame_self": [("我不好", 1.0), ("是我的错", 1.0), ("我太", 0.7)],
}

# ★ 输入端 v2 —— 词表补丁（与匹配器升级同时开）
LEX_V2_ADD = {
    "block": [
        ("恨", 1.4), ("受够", 1.3), ("受不了", 1.2), ("崩溃", 1.3), ("绝望", 1.4),
        ("心寒", 1.0), ("愤怒", 1.0),
        ("难过", 0.9), ("失望", 0.9), ("伤心", 0.9), ("委屈", 0.9), ("介意", 0.9),
        ("生气", 0.8), ("过分", 0.8), ("讨厌", 0.8), ("凭什么", 0.9), ("不公平", 0.8),
        ("敷衍", 0.7), ("忽视", 0.7), ("冷落", 0.7),
        ("有点烦", 0.4), ("不太舒服", 0.3), ("算了", 0.2),
    ],
}

# NRC 覆盖层（文件不入库；读不到 ⇒ 只用手工补丁，如实降级）
LEX_NRC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lexicon_nrc_zh.json")
_NRC_CACHE = None


def _nrc_lex():
    """★ 读不到返回 {}（三态：读不到是"未就绪"，不是"没问题"）。"""
    global _NRC_CACHE
    if _NRC_CACHE is None:
        _NRC_CACHE = {}
        try:
            if os.path.isfile(LEX_NRC_PATH):
                _d = json.load(io.open(LEX_NRC_PATH, encoding="utf-8"))
                _NRC_CACHE = dict((str(_w), float(_v))
                                  for _w, _v in (_d.get("block") or {}).items())
        except Exception:
            _NRC_CACHE = {}
    return _NRC_CACHE


def nrc_lex_size():
    return len(_nrc_lex())


def input_lex_desc():
    """★ 输入端口径的一行自述——让"同一开关两种行为"可见。"""
    if _INPUT_LEX != "v2":
        return "v1"
    n = nrc_lex_size()
    return "v2(+nrc%d)" % n if n else "v2(+nrc0 ★覆盖层未装，仅手工补丁)"


# ★ 情绪种类的持续时间中位数（小时）—— Verduyn & Lavrijsen 2015, Emotion
EMO_KIND_HOURS = {
    "sad":   120.0,   # 悲伤（最长）
    "hate":  60.0,    # 憎恨
    "joy":   35.0,    # 喜悦
    "fear":  6.0,     # 恐惧/焦虑
    "anger": 3.0,     # 愤怒
    "shame": 0.5,     # 羞耻/厌恶/无聊（最短）
}
EMO_KIND_WORDS = [
    ("sad",   ("难过", "伤心", "低落", "想哭", "失落", "委屈", "孤独", "寂寞", "丧")),
    ("hate",  ("讨厌", "恨", "恶心", "再也不想", "受够", "受不了")),
    ("joy",   ("开心", "高兴", "喜欢", "想你", "太好了", "哈哈")),
    ("fear",  ("害怕", "担心", "焦虑", "慌", "怕")),
    ("anger", ("生气", "愤怒", "烦", "气死", "凭什么", "有病")),
    ("shame", ("丢人", "尴尬", "羞", "不好意思", "蠢")),
]


def _emo_kind(text, polarity):
    """判情绪种类（★ 确定性：按列表顺序）。判不出时按极性给缺省。"""
    for kind, ws in EMO_KIND_WORDS:
        for w in ws:
            if w in (text or ""):
                return kind
    if polarity < 0:
        return "anger"
    if polarity > 0:
        return "joy"
    return ""


# ——— 匹配器 v2（★ 与 v1 的差别：会切词、会否定）———
_NEG_MARKS = ("不", "没", "无", "毫不", "毫无", "未", "甭")
_COMPOUND_LEX = set("积劳疲连堆成串接年岁月日渐增囤聚少多")
_COMPOUND_SUF = set("子术局案话者犯")
_INPUT_LEX = "v1"          # ★ 缺省 v1 ⇒ 未开时本模块行为与改动前逐字相同


def set_input_lex(mode):
    """★ 唯一的开关入口。mode 取 "v2"/"v1"（缺省 v1）。"""
    global _INPUT_LEX
    _INPUT_LEX = "v2" if str(mode or "").strip().lower() in ("v2", "2", "on", "true", "yes") else "v1"
    return _INPUT_LEX


def input_lex():
    return _INPUT_LEX


def _hit_v2(text, items):
    """★ 与 v1 的三点差别：① 长词优先并占位 ② 单字词要求前后非构词字符 ③ 词前 3 字内有否定标记则压制。"""
    text = text or ""
    used = [False] * len(text)
    out = []
    for w, v in sorted(items, key=lambda kv: len(kv[0]), reverse=True):
        i = 0
        while True:
            j = text.find(w, i)
            if j < 0:
                break
            if not any(used[j:j + len(w)]):
                prev = text[j - 1] if j > 0 else ""
                nxt = text[j + len(w)] if j + len(w) < len(text) else ""
                blocked = (len(w) == 1 and (
                    prev in _COMPOUND_LEX or prev in _COMPOUND_SUF
                    or nxt in _COMPOUND_LEX or nxt in _COMPOUND_SUF))
                if not blocked:
                    window = text[max(0, j - 3):j]
                    neg = (not any(m in w for m in _NEG_MARKS)) and \
                          any(m in window for m in _NEG_MARKS)
                    if not neg:
                        out.append((w, v))
                for k in range(j, j + len(w)):
                    used[k] = True
            i = j + 1
    return out


def _hit(text, items):
    """返回 [(词, 强度)] 的命中（★ 确定性）。v2 由 set_input_lex("v2") 打开。"""
    if _INPUT_LEX == "v2":
        return _hit_v2(text, items)
    out = []
    for w, v in items:
        if w in text:
            out.append((w, v))
    return out


def _sigmoid(x):
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def appraise(text):
    """从一句话里抽 OCC 五维的【粗略代理】（零 LLM、确定性）。

    返回 dict：{goal_relevance, expectation_violation, desirability, agency, controllability, hits, event, actor, event_evidence}
    """
    t = text or ""
    lex = LEX
    if _INPUT_LEX == "v2":
        lex = dict((_k, list(LEX[_k]) + list(LEX_V2_ADD.get(_k, []))) for _k in LEX)
        _nrc = _nrc_lex()
        if _nrc:
            lex["block"] = lex["block"] + [(_w, _v) for _w, _v in _nrc.items()]
    blk = _hit(t, lex["block"])
    exp = _hit(t, lex["expect"])
    rel = _hit(t, lex["rel"])
    pos = _hit(t, lex["pos"])
    bo = _hit(t, lex["blame_other"])
    bs = _hit(t, lex["blame_self"])

    block_v = sum(v for _, v in blk)
    expect_v = sum(v for _, v in exp)
    rel_v = sum(v for _, v in rel)
    pos_v = sum(v for _, v in pos)
    bo_v = sum(v for _, v in bo)
    bs_v = sum(v for _, v in bs)

    goal_relevance = min(1.0, rel_v / 2.5)
    expectation_violation = min(1.0, expect_v / 2.0)
    neg_v = block_v + expect_v * (0.4 + 0.6 * min(1.0, rel_v / 2.5))
    desirability = min(1.0, pos_v / 2.5) - min(1.0, neg_v / 2.5)
    agency = 0.0
    tot = bo_v + bs_v
    if tot > 0:
        agency = (bo_v - bs_v) / tot
    controllability = 0.5

    # ★ 事件解释层（OCC 原意：评价作用在【被解释的事件】上）
    _ev = None
    try:
        from . import event_parse as _ep
        _ev = _ep.parse(t)
    except Exception:
        _ev = None
    if _ev and _ev.get("event"):
        expectation_violation = max(expectation_violation, float(_ev["expected"]))
        _dv = float(_ev["desirability"])
        if _dv != 0.0:
            desirability = _dv if abs(_dv) >= abs(desirability) else desirability
        controllability = float(_ev["controllability"])
        _a = _ev.get("actor")
        if _a == "other":
            agency = 1.0 if desirability < 0 else 0.0
        elif _a == "self":
            agency = -1.0
        elif _a == "circumstance":
            agency = 0.0
        goal_relevance = max(goal_relevance, 0.5)

    return {
        "goal_relevance": round(goal_relevance, 4),
        "expectation_violation": round(expectation_violation, 4),
        "desirability": round(desirability, 4),
        "agency": round(agency, 4),
        "controllability": controllability,
        "hits": {"block": [w for w, _ in blk], "expect": [w for w, _ in exp],
                 "rel": [w for w, _ in rel], "pos": [w for w, _ in pos]},
        "event": (_ev or {}).get("event"),
        "actor": (_ev or {}).get("actor"),
        "event_evidence": (_ev or {}).get("evidence", ""),
    }


def emotion_from_appraisal(a):
    """OCC 五维 → 情绪强度（0~5）与极性。"""
    gr = a["goal_relevance"]
    ev = a["expectation_violation"]
    de = a["desirability"]
    strength = (0.4 + 0.6 * gr) * (0.45 + 0.85 * ev) * (1.0 + abs(de)) * 1.9
    strength = max(0.0, min(5.0, strength))
    return {"strength": round(strength, 4), "polarity": (1 if de > 0 else (-1 if de < 0 else 0))}


class Appraisal(object):
    """评价 → 情绪 → 抑制负荷。纯本地、无随机源、可复现。"""

    def __init__(self, persona_params=None, data_dir=None, input_lex_mode="v1"):
        self.p = dict(DEFAULTS_PERSONA)
        if persona_params:
            for k in DEFAULTS_PERSONA:
                if k in persona_params:
                    try:
                        self.p[k] = float(persona_params[k])
                    except Exception:
                        pass
        self.input_lex = set_input_lex(input_lex_mode)
        self.S = 0.0          # 抑制池 0~100
        self.C = 0.0          # 成本 0~1
        self.F = 0.0          # 挫折 0~100
        self.M = 0.0          # 心境 -1~1
        self.theta = self.p["theta0"]
        self.events = []      # 环形缓冲（最多 40 条）
        self._last_ts = None
        self._last_kind = ""
        self.data_dir = data_dir
        self._load()

    # ——— 落盘 ———
    def _path(self):
        if not self.data_dir:
            return None
        return os.path.join(self.data_dir, "appraisal_state.json")

    def _load(self):
        p = self._path()
        if not p or not os.path.isfile(p):
            return
        try:
            d = json.load(io.open(p, encoding="utf-8"))
            self.S = float(d.get("S", 0.0))
            self.C = float(d.get("C", 0.0))
            self.F = float(d.get("F", 0.0))
            self.M = max(-1.0, min(1.0, float(d.get("M", 0.0))))
            self.theta = float(d.get("theta", self.p["theta0"]))
            self.events = list(d.get("events") or [])[-40:]
            self._last_ts = d.get("ts")
        except Exception:
            pass

    def save(self):
        p = self._path()
        if not p:
            return
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            io.open(p, "w", encoding="utf-8", newline="\n").write(json.dumps({
                "S": round(self.S, 3), "C": round(self.C, 4), "F": round(self.F, 3),
                "M": round(self.M, 3),
                "theta": round(self.theta, 3), "ts": time.time(),
                "events": self.events[-40:],
            }, ensure_ascii=False, indent=1) + "\n")
        except Exception:
            pass

    # ——— 演化 ———
    def tick(self, dt_sec, active=True):
        """推进 dt 秒。★ 纯确定性：同样的 dt 序列 ⇒ 同样的状态。"""
        if dt_sec <= 0:
            return
        _tau = self.p["tau_F"]
        if getattr(self, "_last_kind", "") in EMO_KIND_HOURS:
            _tau = EMO_KIND_HOURS[self._last_kind] * 3600.0 * float(self.p.get("tau_scale", 1.0))
        self.F *= math.exp(-dt_sec / max(1.0, _tau))
        # ② S（抑制池）【不衰减】—— G&L 1997：抑制是"冻住"不是"排掉"
        self.theta += (self.p["theta0"] - self.theta) * (1.0 - math.exp(-dt_sec / max(1.0, self.p["tau_theta"])))
        self.M *= math.exp(-dt_sec / max(1.0, float(self.p.get("tau_mood", 24 * 3600.0))))

    def activation_baseline(self):
        """激活基线（0~1）：S 与 C 的合成 —— 它决定 θ 被压低多少。"""
        return min(1.0, (self.S / 100.0) * 0.7 + self.C * 0.3)

    def on_message(self, text, relevance=None):
        """评价一条进来的消息，更新 S / F / θ。返回本次的评价结果。"""
        a = appraise(text)
        if relevance is not None:
            a["goal_relevance"] = max(0.0, min(1.0, float(relevance)))
        emo = emotion_from_appraisal(a)
        strength = emo["strength"]
        neg = strength if emo["polarity"] < 0 else 0.0
        pos = strength if emo["polarity"] > 0 else 0.0

        if neg > 0:
            self.S = min(100.0, self.S + self.p["k_sup"] * neg * (0.5 + 0.5 * a["goal_relevance"]))
            self.C = min(1.0, self.C + self.p["k_cost"] * neg / 5.0)
            self.F = min(100.0, self.F + neg * 2.0 * (1.0 + a["expectation_violation"]) / 2.0)
        if pos > 0:
            self.S = max(0.0, self.S - 0.5 * pos)
            self.F = max(0.0, self.F - 0.5 * pos)

        _d = a.get("desirability")
        if _d is not None:
            _km = float(self.p.get("k_mood", 0.08))
            self.M = max(-1.0, min(1.0, self.M + _km * (float(_d) - self.M)))

        self.theta = max(5.0, self.p["theta0"] - self.p["alpha"] * 100.0 * self.activation_baseline())
        _kind = _emo_kind(text, emo["polarity"])
        self.events.append({
            "kind": _kind,
            "t": round(time.time(), 1), "txt": (text or "")[:60],
            "emo": emo["strength"], "pol": emo["polarity"],
            "S": round(self.S, 2), "F": round(self.F, 2), "theta": round(self.theta, 2),
            "occ": {k: a[k] for k in ("goal_relevance", "expectation_violation", "desirability")},
        })
        self.events = self.events[-40:]
        self._last_kind = _kind
        return {"appraisal": a, "emotion": emo, "kind": _kind,
                "S": round(self.S, 3), "F": round(self.F, 3), "theta": round(self.theta, 3)}

    def on_express(self, amount=1.0):
        """她【表达】了 —— 扣减 S（说出来能减压）。amount 0~1。"""
        amount = max(0.0, min(1.0, float(amount)))
        self.S = max(0.0, self.S - self.p["kappa"] * 12.0 * amount)
        self.F = max(0.0, self.F - 6.0 * amount)
        return {"S": round(self.S, 3), "F": round(self.F, 3)}

    # ——— 判定与渲染 ———
    def vent_pressure(self):
        """外化压力 0~1：用 sigmoid（★ 不是硬阈值）。"""
        kt = 12.0
        return round(_sigmoid((self.F + self.S * 0.5 - self.theta) / kt), 4)

    def should_vent(self, line=0.7):
        return self.vent_pressure() >= line

    def vent(self):
        """爆发一次：泄掉大半（β）但不归零；θ 短暂回升。"""
        self.S *= self.p["beta"]
        self.F *= self.p["beta"]
        self.theta = min(self.p["theta0"], self.theta + 15.0)
        return {"S": round(self.S, 3), "F": round(self.F, 3), "theta": round(self.theta, 3)}

    def render(self):
        """渲染成 1~2 行注入文案。★ 语气一律中性：怎么表现由人设决定（零个性化）。"""
        p = self.vent_pressure()
        if p >= 0.7:
            mood = "你现在憋着一股火，一点就着；下句话很可能不客气。"
        elif self.S >= 55:
            mood = "你心里压着些没说的东西，有点沉，不太想顺着聊。"
        elif self.S >= 25:
            mood = "你隐约有点不痛快，但还不明显。"
        else:
            mood = ""
        line = mood
        if self.C >= 0.5:
            line += ("你有些累，耐心比平时差。")
        if not line:
            return ""
        return "（此刻的你：" + line + "这是你的状态，不是对他的评价。）"

    def snapshot(self):
        """调试/取证用（★ 全部是确定性的量）。"""
        return {"S": round(self.S, 3), "C": round(self.C, 4), "F": round(self.F, 3),
                "theta": round(self.theta, 3), "theta0": self.p["theta0"],
                "M": round(self.M, 3),
                "activation": round(self.activation_baseline(), 4),
                "vent_pressure": self.vent_pressure(), "events": len(self.events)}
