# -*- coding: utf-8 -*-
r"""event_parse · 事件解释层（OCC 原意：评价作用在【被解释的事件】上）

★ 移植自 D:\mizuse\core\event_parse.py（2026-10-02），去 person 耦合，仅改相对导入。
  原模块说明：appraisal 作用在"被解释的事件"上，不是句子的表面词。
  我们此前若直接吃 LLM 输出/表面词，句子理解错了整条下游全错。
  学费实例（mizuse 原话）：曾把「我有点想你了」判成 agency=+1.00（归因全给对方），而那是示好。

★ 本层做什么 / 不做什么：
   做：把一句话解析成【事件三元组 + 三个判断】
         (actor 谁造成的, action 发生了什么, object 对谁)
         (expected 意料外吗, desirability 对我好不好, controllability 我能改变吗)
   不做：不做情绪（那是 appraisal 的事）、不调 LLM（零云、确定性）

★ 每个模板的三重防线（照 mizuse persona_infer 的规矩）：
   ① 命中词必须【逐字】在原文里（evidence 记录它）
   ② 模板必须能指出它依据的是原文的哪个片段
   ③ 输出的值必须在量程内
"""
import re

# ---------------------------------------------------------------------------
# 事件模板：每条 = (事件名, actor 缺省, 正则, 五维基线, 说明)
#   ★ 基线的量程：expected 0~1 ｜ desirability -1~1 ｜ controllability 0~1
#   ★ 优先级：数组靠前的先匹配（更具体的在前）
# ---------------------------------------------------------------------------
TEMPLATES = [
    # ——— 承诺未兑现（最常被误解的一类："又忘了"不是抱怨，是期待落空）———
    ("承诺未兑现", "other",
     r"(说好的[^，。！？]{0,12}(没|不)|答应[^，。！？]{0,10}(没|不)|又忘|忘了[^，。！？]{0,6}(说|答应)|"
     r"从来没做到|说到没做到|放我鸽子|说话不算数)",
     {"expected": 0.85, "desirability": -0.75, "controllability": 0.3},
     "对方答应过的事没做到 ⇒ 期待落空，且我对此无能为力"),

    # ——— 守信 / 兑现 ———
    ("守信", "other",
     r"(说到做到|做到了|办好了|真去做了|没有食言|这次没忘|记得[^，。！？]{0,6}(还|带|买))",
     {"expected": 0.6, "desirability": 0.7, "controllability": 0.7},
     "答应的事做到了 ⇒ 期待被证实，正性"),

    # ——— 被冷落 / 被忽略 ———
    ("被冷落", "other",
     r"(不理我|不回我|没回我|忘了回|把我晾|冷落|当我不存在|消息都不回)",
     {"expected": 0.5, "desirability": -0.7, "controllability": 0.35},
     "对方没给回应 ⇒ 关系上的被忽略"),

    # ——— 指责 / 攻击（actor 明确是对方）———
    ("被指责", "other",
     r"(都怪你|因为你[^，。！？]{0,8}(才|所以)|你总是|你又|你根本|你从来没|你没[^，。！？]{0,6}过)",
     {"expected": 0.45, "desirability": -0.8, "controllability": 0.25},
     "对方在把责任推给我 / 数落我 ⇒ 负性且带归因"),

    # ——— 道歉 / 修复 ———
    ("道歉", "other",
     r"(对不起|抱歉|是我的错|我错了|怪我[^，。！？]{0,4}(没|不|让)|原谅我)",
     {"expected": 0.4, "desirability": -0.2, "controllability": 0.6},
     "对方认错 ⇒ 事件本身轻微负性但带修复意图，可控（不该按指责的强度计）"),

    # ——— 被贬低 / 被比较（必须指向【我】，自贬不算）———
    ("被贬低", "other",
     r"(你(真|也太|这么|这么简单都)[^，。！？]{0,6}(笨|蠢|没用|废物)|你看看人家|还不如(一个|别人|人家)|"
     r"跟你说话真累|你懂什么)",
     {"expected": 0.3, "desirability": -0.8, "controllability": 0.3},
     "对方贬低我 ⇒ 强负性、低可控。★ 「我太笨了」是自贬（归因在自己），不得命中此模板"),

    # ——— 请求被拒 ———
    ("请求被拒", "other",
     r"(不答应|拒绝(了|我)|不同意|不给我|不肯(给|陪|帮))",
     {"expected": 0.4, "desirability": -0.5, "controllability": 0.5},
     "我求的事被拒 ⇒ 负性，但对方有拒绝的权利 ⇒ 可控性居中"),

    # ——— 被惦记 / 被照顾（行动上的在意，比口头示好更重）———
    ("被惦记", "other",
     r"(给你(带|留|买|做)|特地|特意(来|给|陪)|想到你[^，。！？]{0,4}(就|了)|帮你(留|占|问))",
     {"expected": 0.5, "desirability": 0.8, "controllability": 0.7},
     "对方用行动照顾我 ⇒ 强正性"),

    # ——— 被认可 ———
    ("被认可", "other",
     r"(你真(棒|好|厉害|贴心|温柔)|多亏(你|有你)|幸亏(你|有你)|全靠你|还是你(好|懂我)|你最懂|有你在[^，。！？]{0,4}(好|踏实))",
     {"expected": 0.4, "desirability": 0.75, "controllability": 0.7},
     "对方肯定我 ⇒ 正性"),

    # ——— ★ 示好 / 亲昵（★ 这一类就是当年被误判成责备的那种；正性 ⇒ parse 里带否定护栏）———
    ("示好", "other",
     r"(想你了|想你|喜欢你|在意你|惦记|想你陪|抱抱|贴贴|在等你|等你回来)",
     {"expected": 0.35, "desirability": 0.8, "controllability": 0.7},
     "对方表达亲近 ⇒ 正性。★ 注意：这里【没有】指责词，绝不能判成 negative"),

    # ——— 求助 / 示弱（对方在求助，不是攻击）———
    ("求助", "other",
     r"(怎么办|帮帮我|救救|撑不住|受不了了|我完了|谁都不理我|没人管我)",
     {"expected": 0.6, "desirability": -0.5, "controllability": 0.6},
     "对方在求助/示弱 ⇒ 负性但可控，且需要回应而不是对抗"),

    # ——— 好消息 / 达成 ———
    ("好消息", "other",
     r"(过了|成了|拿到了|拿到了吗|太好了|终于|顺利|成功|录取|offer|加薪|升职)",
     {"expected": 0.7, "desirability": 0.85, "controllability": 0.4},
     "事情成了 ⇒ 正性、略意外"),

    # ——— 自身受挫（actor 是自己/环境，不是对方）———
    ("自身受挫", "circumstance",
     r"(我今天特别累|累死了|不想动|什么都不想干|烦躁|压力大|扛不住|没睡好|失眠)",
     {"expected": 0.3, "desirability": -0.6, "controllability": 0.35},
     "他自己状态差 ⇒ 负性，但【不是对方造成的】⇒ agency 不该指向对话方"),

    # ——— 道别 / 要离开 ———
    ("要离开", "other",
     r"(先不聊|我走了|下线|睡觉去了|明天再说|改天聊|挂了啊)",
     {"expected": 0.5, "desirability": -0.2, "controllability": 0.6},
     "对方要结束对话 ⇒ 轻微负性，可控"),
]

# actor 的取值：other（对方）/ self（说话者自己）/ circumstance（处境）
ACTOR_VALUES = ("other", "self", "circumstance")


def parse(text):
    """把一句话解释成事件。没有模板命中 ⇒ 返回 event=None（★ 不硬编，宁可留白）。

    返回 dict：
      {event, actor, expected, desirability, controllability, evidence}
      evidence = 【逐字】命中的片段（防线①：引用必须在原文里）

    ★ 正性模板的否定护栏：命中片段前 2 字内有「不/没/别/无」时，
      该正性命中作废、继续找下一个模板 —— 否则「我不想你了」会被判成示好（正性）。
      负性模板不适用此护栏（「不回我」「没做到」本来就是负性表达）。
    """
    t = str(text or "")
    for name, actor, pat, vals, _why in TEMPLATES:
        m = re.search(pat, t)
        if m:
            frag = m.group(0)                      # ★ 逐字片段，不改写
            if frag and frag in t:                 # 防线①：确实在原文里
                if vals["desirability"] > 0:
                    _pre = t[max(0, m.start() - 2):m.start()]
                    if any(_w in _pre for _w in ("不", "没", "别", "无")):
                        continue                   # 否定护栏：正性命中作废
                return {
                    "event": name,
                    "actor": actor,
                    "expected": vals["expected"],
                    "desirability": vals["desirability"],
                    "controllability": vals["controllability"],
                    "evidence": frag,
                }
    return {"event": None, "actor": None, "expected": None,
            "desirability": None, "controllability": None, "evidence": ""}


def has_any(text):
    """★ 只回答"有没有被解释成事件"（供上层的 fallback 判断用）。"""
    return parse(text)["event"] is not None
