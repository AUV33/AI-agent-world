# -*- coding: utf-8 -*-
"""
story_converter.py —— 致敬传奇AI项目 · 故事转换程序（自动关系网 + 错位排除）
=====================================================================
每次生成故事前，程序会：
  1. 读取角色设定（japanAgents.json 等）：通讯录 + 人设
  2. 基于设定建立"人物关系网"：通讯录关系 + 人设关键词延伸关系
     + 运行记录中的消息往来/同场景共处
  3. 自动排除错位关系（日志噪声）：
     - 过滤模板占位接收者（如"联系人名"）
     - 内容自报家门与发送者不符（"我是X"但发送者不是X）→ 丢弃
     - 同一消息被多个角色转发/串扰时，保留有设定依据的一方
  4. 由通讯录做"潜在关联"延伸（二度间接认识）
  5. 在正文前输出【人物关系网】，并把"消息→回复"串成连续对话

模式零（默认，自动适配所有日志）：
    python story_converter.py [日志] [输出]
        - 校园群体日志 → 六人群像小说（明远中学）
        - 日本篇单步日志 → 轻小说精简模式
        - 其他单步日志（Jec/malaya/Auv 等）→ 小说式排版
模式一（强制小说式排版）：
    python story_converter.py --novel [日志] [输出] [轮数] [--agents 设定文件]
模式二（轻小说精简模式）：
    python story_converter.py --light-novel [日志] [输出] [轮数] [--agents 设定文件]
模式三（校园六人群像）：
    python story_converter.py --school [日志] [输出]
=====================================================================
"""

import re
import sys
import os
import json
from collections import OrderedDict, Counter

# 默认日志、输出与角色设定文件（可在命令行覆盖）
DEFAULT_LOG = r"D:\致敬传奇AI项目\记录\原始日志\致敬传奇AI_连续5轮原始日志.txt"
DEFAULT_OUT = r"D:\致敬传奇AI项目\记录\故事\致敬传奇AI_小说式故事.txt"
DEFAULT_OUT_LN = r"D:\致敬传奇AI项目\记录\故事\致敬传奇AI_轻小说_自动版.txt"
DEFAULT_AGENTS = r"D:\致敬传奇AI项目\japanAgents.json"

# 模板占位接收者（日志噪声，直接排除）
PLACEHOLDER_RECEIVERS = {"联系人名", "消息内容", "待面试学生X"}

# 人设关键词 → 关系标签
REL_PHRASES = {
    "妈妈": "母女", "母亲": "母女", "女儿": "亲子", "儿子": "亲子",
    "父亲": "父子", "爸爸": "父子", "爸": "父子", "前夫": "前夫前妻",
    "老板": "老板与员工", "员工": "老板与员工", "网友": "网友",
    "朋友": "好友", "闺蜜": "好友",
}

# 权威关系标签（人工校准，覆盖自动推断）
RELATION_LABELS = {
    ("AUV", "AUV父亲"): "父子",
    ("AUV", "中岛美月"): "网友",
    ("AUV", "至"): "好友（暗恋与被暗恋）",
    ("AUV", "易先生"): "资助者与受助者",
    ("ISI教务", "ISI日本语学校admission面试官"): "教务与面试官",
    ("待面试学生", "札幌语言中心admission面试官"): "面试官与学生",
    ("坂田美优", "山田健太"): "前夫前妻",
    ("坂田美优", "山田阳菜"): "母女",
    ("坂田美优", "坂田美优妈妈"): "母女",
    ("坂田美优", "照相馆老板"): "老板与员工",
    ("坂田美优", "鸡腿"): "旧网恋对象",
    ("坂田美优妈妈", "苫小牧便利店老板"): "老板与员工",
    ("易先生", "鸡腿"): "资助者与受助者",
}

REL_KEYWORDS = [
    (("前夫", "闪婚", "抛弃", "离婚"), "前夫前妻"),
    (("妈妈", "母亲"), "母女"),
    (("女儿", "儿子"), "亲子"),
    (("父亲", "爸", "爸爸"), "父子"),
    (("网恋",), "旧网恋对象"),
    (("网友",), "网友"),
    (("老板",), "老板与员工"),
    (("员工",), "老板与员工"),
    (("资助",), "资助者与受助者"),
    (("暗恋", "喜欢"), "暗恋"),
]


# ---------------------------------------------------------------- 解析

def to_third_person(text, name):
    """把文本中引号外的第一人称"我"替换为角色名（"我们/自我/我国/我辈"等保留）。"""
    skip = ("我们", "自我", "我国", "我辈")
    out = []
    in_quote = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in "\"'“‘“「『":
            if not in_quote:
                in_quote = True
            out.append(ch)
            i += 1
            continue
        if ch in "\"'”’」』":
            in_quote = False
            out.append(ch)
            i += 1
            continue
        if not in_quote and ch == "我":
            if any(text.startswith(s, i) for s in skip):
                out.append(ch)
                i += 1
                continue
            out.append(name)
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def round_times(raw):
    """提取每轮的时间标签：{轮号: 时间文本}。"""
    res = {}
    for m in re.finditer(r"==========\s*第\s*(\d+)\s*轮\s*\|\s*([^=]+?)\s*==========", raw):
        res[int(m.group(1))] = m.group(2).strip()
    return res

def split_rounds(raw):
    raw = re.sub(r"\[重试[^\n]*\n?", "", raw)  # 过滤 API 重试提示噪声
    parts = re.split(r"==========\s*第\s*(\d+)\s*轮(?:\s*\|\s*[^=]+?)?\s*==========", raw)
    rounds = []
    for i in range(1, len(parts), 2):
        num = int(parts[i])
        body = parts[i + 1]
        body = re.split(r"==========\s*第\s*\d+\s*轮结束", body)[0]
        rounds.append((num, body))
    return rounds


def parse_round(body):
    events = []
    blocks = [b for b in re.split(r"-{20,}", body) if b.strip()]
    for blk in blocks:
        lines = blk.strip().splitlines()
        if not lines:
            continue
        line0 = re.sub(r"^\[[^\]]+\]\s*", "", lines[0].strip())
        m = re.match(r"^(.+?)\s+(.+?)\s*：$", line0)
        if not m:
            continue
        name, env = m.group(1).strip(), m.group(2).strip()
        idx = 1
        for j in range(1, len(lines)):
            if re.match(r"^[^：\n]+ ：$", lines[j].strip()):
                idx = j
                break
        action = "\n".join(lines[1:idx])
        events.append({
            "name": name,
            "env": env,
            "action": action,
            "messages": re.findall(r"向【(.+?)】发送(?:了)?【(.+?)】", action),
            "moves": re.findall(r"我要前往【(.+?)】", action),
            "agrees": re.findall(r"同意【(.+?)】的好友请求", action),
        })
    return events


def collect_events(rounds):
    events = []
    for num, body in rounds:
        for e in parse_round(body):
            e["round"] = num
            events.append(e)
    return events


def clean_action(action, name):
    t = action.strip()
    t = re.sub(r"思考【.*?】", "", t, flags=re.S)
    t = re.sub(r"更新记忆【.*?】", "", t, flags=re.S)
    t = re.sub(r"【发送消息成功】", "", t)
    t = re.sub(r"向【.+?】发送(?:了)?【.+?】", "", t, flags=re.S)
    t = re.sub(r"发送【.+?】", "", t, flags=re.S)
    t = re.sub(r"我要前往【.+?】", "", t)
    t = re.sub(r"同意【.+?】的好友请求", "", t)
    t = re.sub(r"决定接下来一小时的动作[：:【]*", "", t)
    t = re.sub(r"接下来一小时(的)?动作[：:【]*", "", t)
    t = re.sub(r"决定动作[：:【]*", "", t)
    t = re.sub(r"^(?:" + re.escape(name) + r")?动作[：:]\s*", "", t)
    t = re.sub(r"^】+", "", t)
    t = re.sub(r"】+$", "", t)
    t = re.sub(r"^我在", name + "在", t)
    t = re.sub(r"^我要", name + "要", t)
    t = re.sub(r"^我打算", name + "打算", t)
    t = re.sub(r"^我", name, t)
    t = re.sub(r"^在", name + "在", t)
    if t and not t.startswith(name):
        t = name + "：" + t.lstrip()
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t)
    t = re.sub(r"\n(?!\s)", " ", t)
    return t.strip()


# ------------------------------------------------------- 文学化改写
FEMALE_NAMES = {"坂田美优", "坂田美优妈妈", "至", "中岛美月", "山田阳菜"}
LOC_PRETTY = [
    ("日本-札幌-北区", "札幌北区"),
    ("日本-札幌-中央区", "札幌中央区"),
    ("日本-苫小牧", "苫小牧"),
    ("日本-饭田", "饭田"),
    ("日本-东京-新宿区", "东京新宿"),
    ("日本-东京-港区", "东京港区"),
    ("中国-清远", "清远"),
    ("中国-上海", "上海"),
    ("中国-泾县-AUV家", "泾县AUV家"),
    ("中国-泾县-至家", "泾县至家"),
]
LOC_LEADS = ("札幌", "东京", "苫小牧", "饭田", "清远", "上海", "泾县")


def literaryize(name, action):
    """把记录式动作句改写成文学化叙述句（纯规则，不调用 API）。"""
    t = clean_action(action, name)
    t = re.sub(r"^" + re.escape(name) + r"[：:]\s*", "", t)
    t = re.sub(r"^我[：:]", "", t)
    # 清理记录式套话
    t = re.sub(r"决定接下来一小时(?:的)?动作[：:【]*", "", t)
    t = re.sub(r"接下来一小时(?:的)?动作[：:【]*", "", t)
    t = re.sub(r"直接进行以下动作[：:]*", "", t)
    t = re.sub(r"决定动作[：:【]*", "", t)
    t = re.sub(r"^(?:" + re.escape(name) + r")?动作[：:]\s*", "", t)
    t = re.sub(r"我应", "", t)
    t = re.sub(r"[，。;；]?(?:不移动(?:场景|出[^。；]*)?|无需移动|不主动移动场景|不移动)[。；]?", "", t)
    t = re.sub(r"^留在", "留守在", t)
    # 常见动作的文学化表达
    t = re.sub(r"进行便利店日常经营", "打理着便利店的店面，", t)
    t = re.sub(r"进行(?:日常)?经营", "打理着店面，", t)
    t = re.sub(r"日常经营", "打理着店面", t)
    t = re.sub(r"整理(?:便利店)?(?:儿童)?零食货架", "把零食货架重新码放整齐", t)
    t = re.sub(r"核对收银台(?:的)?营业款", "清点了收银台里的营业款", t)
    t = re.sub(r"(?:在店门口)?(?:等候|等待)可能的应聘(?:面试者|者)(?:前来)?", "守在店门口，候着可能上门的应聘者", t)
    t = re.sub(r"整理(?:拍摄)?道具(?:与|和)面试登记表", "归拢了拍摄道具和面试登记表", t)
    t = re.sub(r"张贴临时招聘面试指引", "在门口贴好了招聘指引", t)
    t = re.sub(r"与(.+?)交流(.+?)(?:情况|标准)", r"和\1聊了聊\2", t)
    t = re.sub(r"与(.+?)做额外互动", r"和\1多做交流", t)
    t = re.sub(r"与(.+?)互动", r"和\1搭了几句话", t)
    t = re.sub(r"和(.+?)互动", r"和\1搭了几句话", t)
    t = re.sub(r"买(?:儿童)?零食", "挑了几包零食", t)
    t = re.sub(r"买一瓶水", "买了一瓶水", t)
    t = re.sub(r"散步休息", "在附近散步歇脚", t)
    t = re.sub(r"取出背着的iPad", "取下背着的iPad", t)
    t = re.sub(r"安静地画人体练习", "安静地画着人体练习", t)
    t = re.sub(r"画人体练习", "画着人体练习", t)
    t = re.sub(r"继续打开随身贴满二次元贴纸的厚重笔记本", "翻开那本贴满二次元贴纸的厚重笔记本", t)
    t = re.sub(r"给AUV做UE4相关的技术解答和帮忙调试", "给AUV讲解UE4的技术难题", t)
    t = re.sub(r"把笔记本上关于材质节点的笔记指给AUV看", "把材质节点的笔记指给AUV看", t)
    t = re.sub(r"确认明天(?:上班)?的排班", "确认了明天的排班", t)
    # 记录式残留清理
    t = re.sub(r"，我要", "，便", t)
    t = re.sub(r"我?将在", "打算在", t)
    t = re.sub(r"要留在", "留守在", t)
    t = re.sub(r"对接", "和", t)
    t = re.sub(r"进行(?:日常)?经营", "打理着店面，", t)
    t = re.sub(r"，同时", "，一边", t)
    t = re.sub(r"，并", "，又", t)
    # 位置美化（全句）
    for k, v in LOC_PRETTY:
        t = t.replace(k, v)
    t = re.sub(r"^在(?=札幌|东京|苫小牧|饭田|清远|上海|泾县)", "", t)
    # 主语处理
    if t.startswith("我要去"):
        t = "动身前往" + t[len("我要去"):]
    elif t.startswith("我去"):
        t = "前往" + t[len("我去"):]
    if not t.startswith(name):
        if t.startswith(LOC_LEADS):
            t = name + "在" + t
        elif not t.startswith(("他", "她")):
            t = name + t
    t = re.sub(r"^" + re.escape(name) + r"我", name, t)
    t = re.sub(r"（我）当前在店内[^。]*。", "", t)
    t = re.sub(r"，，", "，", t)
    t = re.sub(r"，又(?=[。；])", "。", t)
    t = re.sub(r"[【】]", "", t)
    t = re.sub(r"[ \t]+", " ", t).strip()
    if t and t[-1] not in "。！？」\"\"":
        t += "。"
    return t



# ------------------------------------------------------- 设定与关系网
def load_agents_config(path):
    """读取角色设定：返回 (角色名集合, 通讯录 dict, 人设 dict)。"""
    agents, addr, persona = set(), {}, {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for d in data:
            name = d.get("name")
            if not name:
                continue
            agents.add(name)
            addr[name] = set(d.get("addressBook") or [])
            persona[name] = d.get("persona") or ""
    except Exception as e:
        print(f"[StoryConverter] 设定文件读取失败，将仅基于日志生成：{e}")
    return agents, addr, persona


def _find_name(text, name):
    """边界感知的名字查找：避免把"坂田美优妈妈"误当成"坂田美优"。"""
    for m in re.finditer(re.escape(name), text):
        s, e = m.start(), m.end()
        prev = text[s - 1] if s > 0 else ""
        nxt = text[e] if e < len(text) else ""
        if re.match(r"[\u4e00-\u9fffA-Za-z]", prev) or re.match(r"[\u4e00-\u9fffA-Za-z]", nxt):
            continue
        return m
    return None


def extract_persona_relations(agents, persona):
    """基于人设延伸：A 的人设中提到 B，即建立一条带标签的关系（边界感知+短语优先）。"""
    rels = []
    for a, text in persona.items():
        for b in agents:
            if b == a or _find_name(text, b) is None:
                continue
            for sent in re.split(r"[。；;\n]", text):
                if _find_name(sent, b) is None:
                    continue
                label = "人设关联"
                m = re.search(re.escape(b) + r"的(.{1,4})[，。、；\s]", sent)
                if m and m.group(1) in REL_PHRASES:
                    label = REL_PHRASES[m.group(1)]
                else:
                    for kws, lab in REL_KEYWORDS:
                        hit = False
                        for kw in kws:
                            for km in re.finditer(kw, sent):
                                seg = sent[max(0, km.start() - 10):km.end() + 10]
                                if _find_name(seg, b):
                                    hit = True
                                    break
                            if hit:
                                break
                        if hit:
                            label = lab
                            break
                rels.append((a, b, label))
                break
    return rels


def filter_messages(events, agents, addr, persona):
    """清洗日志消息，排除错位/串扰：返回 [(轮号, 发送者, 接收者, 内容)]。"""
    raw = []
    for e in events:
        for to, msg in e["messages"]:
            raw.append((e["round"], e["name"], to, msg))

    # 1) 排除模板占位接收者
    raw = [r for r in raw if r[2] not in PLACEHOLDER_RECEIVERS]

    # 2) 自报家门与发送者不符 → 丢弃（如"我是美月"却由别人发出）
    def intro_mismatch(sender, content):
        m = re.search(r"我是(.+?)[，。！？\s「」]", content)
        return bool(m and m.group(1).strip() and m.group(1).strip() != sender)

    raw = [r for r in raw if not intro_mismatch(r[1], r[3])]

    # 3) 同一(接收者,内容)被多个发送者发出 → 保留有设定依据的一方
    def has_setting(sender, recv):
        if recv in persona.get(sender, ""):
            return True
        if sender in addr and recv in addr[sender]:
            return True
        if recv in addr and sender in addr[recv]:
            return True
        return False

    groups = {}
    for r in raw:
        groups.setdefault((r[2], r[3]), []).append(r)

    clean = []
    for (recv, content), items in groups.items():
        senders = {it[1] for it in items}
        if len(senders) == 1:
            clean.extend(items)
            continue
        chosen = next((s for s in senders if has_setting(s, recv)), None)
        if chosen is None:
            chosen = Counter(it[1] for it in items).most_common(1)[0][0]
        clean.extend(it for it in items if it[1] == chosen)
    return clean


def build_network(rounds, agents_path):
    """建立关系网：返回 (edges dict, potential 潜在关联, clean_msgs)。"""
    agents, addr, persona = load_agents_config(agents_path)
    events = collect_events(rounds)
    clean_msgs = filter_messages(events, agents, addr, persona)

    edges = {}
    def edge(a, b, label=None, src=None):
        key = tuple(sorted([a, b]))
        if key[0] == key[1]:
            return
        r = edges.setdefault(key, {"a": key[0], "b": key[1], "label": None,
                                   "msgs": 0, "co": 0, "src": set()})
        if label and not r["label"]:
            r["label"] = label
        if src:
            r["src"].add(src)

    # 1) 人设延伸
    for a, b, label in extract_persona_relations(agents, persona):
        edge(a, b, label, "人设")
    # 2) 通讯录
    for name, contacts in addr.items():
        for c in contacts:
            edge(name, c, "通讯录", "通讯录")
    # 3) 消息往来（已清洗）
    for rnd, s, r, msg in clean_msgs:
        edge(s, r, None, "消息")
        edges[tuple(sorted([s, r]))]["msgs"] += 1
    # 4) 同场景共处
    scene_round = {}
    for e in events:
        scene_round.setdefault((e["round"], e["env"]), set()).add(e["name"])
    for names in scene_round.values():
        names = list(names)
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                edge(a, b, "同场景", "同场")
                edges[tuple(sorted([a, b]))]["co"] += 1

    # 4.5) 权威关系标签覆盖自动推断
    for key, label in RELATION_LABELS.items():
        key = tuple(sorted(key))
        if key in edges:
            edges[key]["label"] = label

    # 5) 潜在关联：通讯录二度延伸（A↔B↔C 且 A、C 无直接关系）
    potential = []
    seen_pot = set()
    for a in addr:
        for b in addr[a]:
            for c in addr.get(b, ()):
                key = tuple(sorted([a, c]))
                if c != a and key not in edges and key not in seen_pot:
                    seen_pot.add(key)
                    potential.append((a, c, b))
    return edges, potential, clean_msgs


def render_network(edges, potential, limit=14):
    L = []
    L.append("【人物关系网】")
    L.append("　　（基于人设/通讯录建立，结合运行记录整合，已排除错位关联）")
    ordered = sorted(edges.values(), key=lambda r: -(r["msgs"] * 3 + r["co"]))
    for r in ordered[:limit]:
        parts = []
        if r["msgs"]:
            parts.append(f"{r['msgs']} 条消息")
        if r["co"]:
            parts.append(f"同场 {r['co']} 次")
        src_txt = "+".join(sorted(r["src"])) if r["src"] else "运行记录"
        label = r["label"] or "关联"
        line = f"　・ {r['a']} × {r['b']}（{label}）"
        if parts:
            line += "：" + "，".join(parts)
        line += f"　[来源:{src_txt}]"
        L.append(line)
    if potential:
        L.append("　　——潜在关联（由通讯录延伸）——")
        for a, c, via in potential[:8]:
            L.append(f"　・ {a} ↔ {c}（经 {via} 间接认识）")
    return "\n".join(L)


# ---------------------------------------------------------------- 模式一：小说式
def render_novel(rounds, max_rounds=None, agents_path=DEFAULT_AGENTS, times=None):
    if max_rounds:
        rounds = rounds[:max_rounds]
    edges, potential, clean_msgs = build_network(rounds, agents_path)
    total_agents = {e["name"] for e in collect_events(rounds)}

    msg_by = {}
    for rnd, s, r, msg in clean_msgs:
        msg_by.setdefault((rnd, s), []).append((r, msg))
    replies = {}
    for rnd, s, r, msg in clean_msgs:
        if msg == "申请好友":
            continue
        replies.setdefault((r, s), []).append((msg, rnd))
    replied = set()

    L = []
    L.append("《致敬传奇 · 群像》")
    L.append("—— 多智能体模拟故事 · 按时间线呈现 ——")
    L.append("")
    L.append("【楔子】")
    L.append("　　在札幌、苫小牧、饭田与泾县之间，")
    L.append("　　便利店老板守着货架，照相馆里飘着胶片的味道，")
    L.append("　　有人在等一场面试，有人在画人体练习，有人在等一条消息。")
    L.append("　　二十段互不相识的人生，在同一个世界里平行转动，偶尔交错。")
    L.append("")
    L.append(render_network(edges, potential, 12))
    L.append("")

    for num, body in rounds:
        events = parse_round(body)
        if not events:
            continue
        scenes = OrderedDict()
        for e in events:
            scenes.setdefault(e["env"], []).append(e)

        L.append("")
        L.append("═" * 46)
        L.append((f"第 {num} 章 · {times[num]}") if (times and times.get(num)) else f"第 {num} 章")
        L.append("═" * 46)
        L.append(f"　　（这一轮，故事在 {len(scenes)} 个地点同时上演：{'、'.join(scenes.keys())}）")
        L.append("")

        scene_items = list(scenes.items())
        for si, (env, evs) in enumerate(scene_items):
            L.append(f"◎ {env}")
            for e in evs:
                act = to_third_person(clean_action(e["action"], e["name"]), e["name"])
                if act:
                    L.append(f"　　{act}")
                for to, msg in msg_by.get((num, e["name"]), []):
                    if msg == "申请好友":
                        L.append(f"　　✦ {e['name']} 向 {to} 发去了好友申请。")
                    else:
                        L.append(f"　　✦ {e['name']} 对 {to} 说：「{msg}」")
                        if (e["name"], to, msg) not in replied:
                            replied.add((e["name"], to, msg))
                            later = [x for x in replies.get((to, e["name"]), []) if x[1] > num]
                            if later:
                                rmsg, rnum = later[0]
                                L.append(f"　　↳ 第 {rnum} 轮，{to} 回复：「{rmsg}」")
                for to in e["agrees"]:
                    L.append(f"　　✅ {e['name']} 同意了 {to} 的好友请求。")
                for dest in e["moves"]:
                    L.append(f"　　↪ {e['name']} 起身前往 {dest}。")
                L.append("")
            if si < len(scene_items) - 1:
                L.append("　　——与此同时，在另一个地方……")
                L.append("")

    L.append("")
    L.append("═" * 46)
    L.append("【尾声】")
    L.append("═" * 46)
    L.append(f"　　共上演 {len(rounds)} 轮，{len(total_agents)} 名角色登场，{len(clean_msgs)} 条有效消息。")
    L.append(f"　　自动整合出 {len(edges)} 组人物关联（人设/通讯录/运行记录），{len(potential)} 组潜在关联。")
    L.append("　　故事仍在继续。")
    return "\n".join(L)


# ---------------------------------------------------------------- 模式二：轻小说精简
CN_NUM = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]

LIGHT_NOVEL_TITLE = "《平行群像物语》"
LIGHT_NOVEL_SUB = "——平行世界里，平凡又交错的一天——"

STORYLINE_CHAPTERS = [
    {"title": "札幌北区：单亲妈妈的一天",
     "chars": ["坂田美优", "山田健太", "坂田美优妈妈", "照相馆老板", "山田阳菜",
               "札幌北区便利店老板", "苫小牧便利店老板", "札幌中央区便利店老板"]},
    {"title": "泾县：炸鸡与画板",
     "chars": ["AUV", "至", "AUV父亲", "中岛美月", "易先生", "饭田便利店老板"]},
    {"title": "清远：等待资助的毕业生",
     "chars": ["鸡腿"]},
    {"title": "东京：永远不会被通过的好友申请",
     "chars": ["ISI日本语学校admission面试官", "东京新宿区便利店老板",
               "AKKODIS面试官", "东京港区便利店老板", "札幌语言中心admission面试官"]},
]

PSYCH_LINES = {
    "坂田美优": "她盯着屏幕，心想：有些话一旦说出口，就再也收不回去了。",
    "山田健太": "他想见她们一面，可他也清楚，自己早就没有资格了。",
    "坂田美优妈妈": "她一边理货一边想：女儿一个人带着孩子，一定很辛苦吧。",
    "鸡腿": "他捏着手机，手心全是汗——这是自己唯一的机会了。",
    "AUV": "他看着画板，心想：万一……真的能去日本呢？",
    "至": "她嘴上凶巴巴的，耳尖却悄悄红了。",
    "AUV父亲": "他骂得越凶，心里越怕儿子真的被人骗走。",
    "中岛美月": "她咬了一口红薯，想：要是能见面就好了。",
    "易先生": "他笑了笑，心想：年轻人嘛，总该给个机会。",
    "札幌语言中心admission面试官": "他一次次按下发送，心想：到底什么时候才会有人通过啊。",
    "ISI日本语学校admission面试官": "他盯着好友申请列表，轻轻叹了口气。",
    "AKKODIS面试官": "他端着咖啡，心想：合适的人，怎么还不出现。",
    "照相馆老板": "他想，店里缺人手，得赶紧招一个才行。",
    "山田阳菜": "一岁的她还什么都不懂，只知道零食很甜。",
}
DEFAULT_PSYCH = "他在心里对自己说：先把眼前的事做好吧。"


def render_light_novel(rounds, max_rounds=None, agents_path=DEFAULT_AGENTS, record_style=False):
    if max_rounds:
        rounds = rounds[:max_rounds]
    edges, potential, clean_msgs = build_network(rounds, agents_path)
    msg_by = {}
    for rnd, s, r, msg in clean_msgs:
        msg_by.setdefault((rnd, s), []).append((r, msg))
    replies = {}
    for rnd, s, r, msg in clean_msgs:
        if msg == "申请好友":
            continue
        replies.setdefault((r, s), []).append((msg, rnd))
    seen_msg_note = set()

    L = []
    L.append(LIGHT_NOVEL_TITLE)
    L.append(LIGHT_NOVEL_SUB)
    L.append("")
    L.append("【序章】")
    L.append("　　在札幌、苫小牧、饭田与泾县之间，")
    L.append("　　二十个人各怀心事，过着平凡又彼此交错的一天。")
    L.append("　　有人守着便利店，有人画着画，有人在等一条迟迟不来的回复。")
    L.append("")
    L.append(render_network(edges, potential, 10))
    L.append("")

    for ci, ch in enumerate(STORYLINE_CHAPTERS, 1):
        L.append("")
        L.append("═" * 42)
        L.append(f"第{CN_NUM[ci-1]}话 · {ch['title']}")
        L.append("═" * 42)
        L.append("")
        char_set = set(ch["chars"])
        seen_actions = {}
        seen_msgs = set()
        for e in collect_events(rounds):
            if e["name"] not in char_set:
                continue
            act = clean_action(e["action"], e["name"]) if record_style else literaryize(e["name"], e["action"])
            if e["round"] == 1 and act and act.strip("。 ") != e["name"] and act not in seen_actions.get(e["name"], set()):
                seen_actions.setdefault(e["name"], set()).add(act)
                L.append(f"　　{act}")
                psych = PSYCH_LINES.get(e["name"], DEFAULT_PSYCH)
                L.append(f"　　（{psych}）")
            for to, msg in msg_by.get((e["round"], e["name"]), []):
                key = (e["name"], to, msg)
                if key in seen_msgs:
                    continue
                seen_msgs.add(key)
                if msg == "申请好友":
                    L.append(f"　　✦ {e['name']} 向 {to} 发去了好友申请。")
                else:
                    L.append(f"　　「{msg}」——{e['name']} 对 {to} 说。")
                    if key not in seen_msg_note:
                        seen_msg_note.add(key)
                        later = [x for x in replies.get((to, e["name"]), []) if x[1] > e["round"]]
                        if later:
                            rmsg, rnum = later[0]
                            L.append(f"　　（后来，{to} 回复：「{rmsg}」）")
            for to in e["agrees"]:
                L.append(f"　　✅ {e['name']} 同意了 {to} 的好友请求。")
        L.append("")

    L.append("")
    L.append("═" * 42)
    L.append("【终章】")
    L.append("═" * 42)
    L.append(f"　　{len(rounds)} 小时过去。")
    L.append("　　一天就这么过去了。")
    L.append("　　明天大概还是平凡的一天，但每个人都还在往前走。")
    return "\n".join(L)



# ================================================================
# 校园篇（明远中学 302 寝室 · 六人群像）——群体日志解析与故事生成
# ================================================================
SCHOOL_TITLE = "《302寝室的日常》"
SCHOOL_SUB = "——明远中学 · 六个室友的一天——"
DEFAULT_OUT_SCHOOL = r"D:\致敬传奇AI项目\记录\故事\明远中学_六人群像小说.txt"
SCHOOL_AGENTS = r"D:\致敬传奇AI项目\schoolAgents.json"
SCHOOL_ROOMS = {
    "陈子墨": "1号床，年级前五的学霸，温和克制，习惯把关心藏进细节里",
    "林阳": "2号床，高二(3)班班长，校篮球队主力前锋，阳光讲义气",
    "王浩宇": "3号床，王者段位的网瘾少年，随和好脾气，画画天赋点满",
    "赵天磊": "4号床，话少爱观察，看着冷淡其实比谁都细心",
    "孙一凡": "5号床，全校的“自来熟之王”，嘴贫爱闹，最怕孤独",
    "周景行": "6号床，讲究的小少爷，洁癖嘴硬，其实心很软",
}


def _latest_school_log():
    import glob
    cand = glob.glob(r"D:\致敬传奇AI项目\记录\原始日志\明远中学_群体记录_*.txt")
    return max(cand, key=os.path.getmtime) if cand else DEFAULT_LOG


def split_school_segments(raw):
    """解析校园群体日志：返回 [{idx, day, time, env, narration, memories}]。"""
    segs = []
    marker = re.compile(
        r"==========\s*第\s*(\d+)\s*段\s*\|(?:\s*第(\d+)天)?\s*([^|]+?)\s*\|\s*([^=]+?)\s*==========")
    for m in marker.finditer(raw):
        idx = int(m.group(1))
        day = int(m.group(2)) if m.group(2) else 1
        time_label, env = m.group(3).strip(), m.group(4).strip()
        body = raw[m.end():]
        end = re.search(r"==========\s*第\s*\d+\s*段结束", body)
        if end:
            body = body[:end.start()]
        narration = ""
        nm = re.search(r"【叙事】\s*(.+?)(?=\n\s*【角色记忆】|\Z)", body, re.S)
        if nm:
            narration = nm.group(1).strip()
        memories = {}
        mm = re.search(r"【角色记忆】\s*(.+?)\Z", body, re.S)
        if mm:
            for line in mm.group(1).splitlines():
                lm = re.match(r"^\s*([^\s：:]+)\s*[：:]\s*(.+)$", line)
                if lm:
                    memories[lm.group(1).strip()] = lm.group(2).strip()
        segs.append({"idx": idx, "day": day, "time": time_label, "env": env,
                     "narration": narration, "memories": memories})
    return segs


def render_school_network(agents_path):
    """校园关系网：六人室友（通讯录）+ 人设延伸。"""
    agents, addr, persona = load_agents_config(agents_path)
    lines = ["【人物关系网】", "　　（六人同为明远中学302寝室室友，关系由设定与运行记录整合）"]
    edges = []
    for name, contacts in addr.items():
        for c in contacts:
            if c in agents and name != c:
                key = tuple(sorted([name, c]))
                if key not in {(e[0], e[1]) for e in edges}:
                    edges.append((key[0], key[1], "室友"))
    for a, b, label in extract_persona_relations(agents, persona):
        key = tuple(sorted([a, b]))
        if key not in {(e[0], e[1]) for e in edges}:
            edges.append((key[0], key[1], label))
    for a, b, label in edges:
        lines.append(f"　・ {a} × {b}（{label}）")
    return "\n".join(lines)


def render_school_story(segments, agents_path=DEFAULT_AGENTS):
    """六人群像小说：序章 + 关系网 + 按时间段章节 + 各人心绪 + 终章。"""
    L = []
    L.append(SCHOOL_TITLE)
    L.append(SCHOOL_SUB)
    L.append("")
    L.append("【序章】")
    L.append("　　明远中学302寝室，六张床，六个人，六种截然不同的活法。")
    for name, desc in SCHOOL_ROOMS.items():
        L.append(f"　　{name}——{desc}。")
    L.append("　　他们在一个屋檐下，过着平凡又吵闹的高二。")
    L.append("")
    L.append(render_school_network(agents_path))
    L.append("")

    for seg in segments:
        L.append("")
        L.append("═" * 42)
        L.append(f"第{seg['idx']}章 · 第{seg['day']}天 {seg['time']} · {seg['env']}")
        L.append("═" * 42)
        L.append("")
        if seg["narration"]:
            L.append(seg["narration"])
        if seg["memories"]:
            L.append("")
            L.append("　　── 各自的心绪 ──")
            for name in SCHOOL_ROOMS:
                if name in seg["memories"]:
                    L.append(f"　　{name}：{seg['memories'][name]}")
        L.append("")

    L.append("")
    L.append("═" * 42)
    L.append("【终章】")
    L.append("═" * 42)
    L.append(f"　　{len(segments)} 个时段过去，这一天终于安静下来。")
    L.append("　　明天，六个人还会在302寝室的灯光下，继续这样平凡又吵闹地生活下去。")
    return "\n".join(L)



# ================================================================
# 校园单步记录 → 六人群像小说
# ================================================================
SCHOOL_PSYCH = {
    "陈子墨": "他想：先把眼前的事做好，比什么都强。",
    "林阳": "他抓了抓头发，心想：兄弟的事，不能含糊。",
    "王浩宇": "他打了个哈欠，脑子里还转着昨晚的团战。",
    "赵天磊": "他什么都没说，只是把细节默默记在心里。",
    "孙一凡": "他嘴上不停，心里却比谁都怕冷场。",
    "周景行": "他嘴硬地哼了一声，其实早就记在了心上。",
}
DEFAULT_SCHOOL_PSYCH = "他在心里叹了口气，把这件小事记了下来。"


def render_school_story_single(rounds, agents_path=DEFAULT_AGENTS, times=None):
    """单步校园记录 → 六人群像小说（按轮/场景整合，含心理描写）。"""
    L = []
    L.append(SCHOOL_TITLE)
    L.append(SCHOOL_SUB)
    L.append("")
    L.append("【序章】")
    L.append("　　明远中学302寝室，六张床，六个人，六种截然不同的活法。")
    for name, desc in SCHOOL_ROOMS.items():
        L.append(f"　　{name}——{desc}。")
    L.append("　　他们在一个屋檐下，过着平凡又吵闹的高二。")
    L.append("")
    L.append(render_school_network(agents_path))
    L.append("")

    msg_by = {}
    for e in collect_events(rounds):
        for to, msg in e["messages"]:
            msg_by.setdefault((e["round"], e["name"]), []).append((to, msg))

    for num, body in rounds:
        events = parse_round(body)
        if not events:
            continue
        scenes = OrderedDict()
        for e in events:
            scenes.setdefault(e["env"], []).append(e)

        L.append("")
        L.append("═" * 42)
        cnum = CN_NUM[num - 1] if 1 <= num <= 10 else str(num)
        L.append((f"第{cnum}轮 · {times[num]} · 六人各自的一天") if (times and times.get(num)) else f"第{cnum}轮 · 六人各自的一天")
        L.append("═" * 42)
        L.append("")
        for env, evs in scenes.items():
            L.append(f"◎ {env}")
            for e in evs:
                act = to_third_person(literaryize(e["name"], e["action"]), e["name"])
                if act:
                    L.append(f"　　{act}")
                psych = SCHOOL_PSYCH.get(e["name"], DEFAULT_SCHOOL_PSYCH)
                L.append(f"　　（{psych}）")
                for to, msg in msg_by.get((num, e["name"]), []):
                    if msg == "申请好友":
                        L.append(f"　　✦ {e['name']} 向 {to} 发去了好友申请。")
                    else:
                        L.append(f"　　✦ {e['name']} 对 {to} 说：「{msg}」")
                for to in e["agrees"]:
                    L.append(f"　　✅ {e['name']} 同意了 {to} 的好友请求。")
                for dest in e["moves"]:
                    L.append(f"　　↪ {e['name']} 起身前往 {dest}。")
                L.append("")
        L.append("　　——与此同时，六个人的故事在校园各处平行上演。")

    L.append("")
    L.append("═" * 42)
    L.append("【终章】")
    L.append("═" * 42)
    L.append(f"　　{len(rounds)} 轮过去，六个人各自回到 302 寝室的灯光下。")
    L.append("　　明天，他们还会在同一个屋檐下，继续这样平凡又吵闹地生活下去。")
    return "\n".join(L)


def render_school_auto(raw, agents_path=DEFAULT_AGENTS):
    """校园日志自动适配：群体段日志→群像小说；单步记录→群像小说。"""
    if re.search(r"==========\s*第\s*\d+\s*段\s*\|", raw):
        return render_school_story(split_school_segments(raw), agents_path)
    return render_school_story_single(split_rounds(raw), agents_path, times=round_times(raw))

# ================================================================
# 自动适配：检测日志格式 + 匹配角色设定 + 自动选择生成模式
# ================================================================
CONFIG_FILES = [
    r"D:\致敬传奇AI项目\schoolAgents.json",
    r"D:\致敬传奇AI项目\japanAgents.json",
    r"D:\致敬传奇AI项目\JecAgents.json",
    r"D:\致敬传奇AI项目\malayaAgents.json",
    r"D:\致敬传奇AI项目\AuvAgents.json",
]


def detect_log_format(raw):
    """返回日志格式：school_group（第N段|群体） / single_step（名字 场景 ：单步）。"""
    if re.search(r"==========\s*第\s*\d+\s*段\s*\|", raw):
        return "school_group"
    return "single_step"


def pick_agents_file(raw):
    """根据日志中出现的角色名，自动匹配最合适的角色设定文件。"""
    names_in_log = set()
    for num, body in split_rounds(raw):
        for e in parse_round(body):
            names_in_log.add(e["name"])
    if not names_in_log:
        for name in SCHOOL_ROOMS:
            if name in raw:
                names_in_log.add(name)
    best, best_score = None, -1
    for path in CONFIG_FILES:
        agents, addr, persona = load_agents_config(path)
        score = sum(1 for n in agents if n in names_in_log)
        if score > best_score:
            best, best_score = path, score
    return best or DEFAULT_AGENTS


def default_out_for(log):
    base = os.path.splitext(os.path.basename(log))[0]
    return os.path.join(r"D:\致敬传奇AI项目\记录\故事", base + "_故事.txt")


# ---------------------------------------------------------------- 入口
def main():
    args = sys.argv[1:]
    school = "--school" in args
    light_novel = "--light-novel" in args or "--ln" in args
    novel = "--novel" in args
    record_style = "--record" in args
    args = [a for a in args if a not in ("--light-novel", "--ln", "--record", "--school", "--novel")]

    agents_path = None
    if "--agents" in args:
        i = args.index("--agents")
        agents_path = args[i + 1] if i + 1 < len(args) else None
        args = args[:i] + args[i + 2:]

    log = args[0] if len(args) > 0 else (_latest_school_log() if school else DEFAULT_LOG)
    out = args[1] if len(args) > 1 else None
    rounds = int(args[2]) if len(args) > 2 else None

    if not os.path.exists(log):
        print(f"[StoryConverter] 找不到日志文件：{log}")
        sys.exit(1)

    with open(log, encoding="utf-8") as f:
        raw = f.read()

    fmt = detect_log_format(raw)
    auto = not (school or light_novel or novel)
    if agents_path is None:
        if school or (auto and fmt == "school_group"):
            agents_path = SCHOOL_AGENTS
        else:
            agents_path = pick_agents_file(raw)

    if out is None:
        out = (DEFAULT_OUT_SCHOOL if (school or agents_path == r"D:\致敬传奇AI项目\schoolAgents.json")
               else default_out_for(log))

    is_school = (agents_path == r"D:\致敬传奇AI项目\schoolAgents.json")

    if is_school:
        text = render_school_auto(raw, agents_path)
        tag = "校园六人群像模式（群像叙事+心理描写）"
    elif light_novel or (auto and agents_path == r"D:\致敬传奇AI项目\japanAgents.json"):
        text = render_light_novel(split_rounds(raw), rounds, agents_path, record_style=record_style)
        tag = "轻小说精简模式（关系网+错位排除）" if light_novel else "自动适配·轻小说（日本篇）"
    else:
        text = render_novel(split_rounds(raw), rounds, agents_path, times=round_times(raw))
        tag = "小说式排版（关系网+错位排除）" if novel else "自动适配·小说式"

    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[StoryConverter] [{tag}] 已生成：{out}")
    print(f"[StoryConverter] 设定文件：{agents_path}")
    n_seg = len(split_school_segments(raw)) if fmt == "school_group" else len(split_rounds(raw))
    print(f"[StoryConverter] 共 {n_seg} 段 → 输出 {len(text)} 字符")


if __name__ == "__main__":
    main()
