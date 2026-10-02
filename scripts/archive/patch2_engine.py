#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补丁2：让闲聊生成可靠（重试 + 兜底），避免推理模型偶发空内容导致闲聊层失效。"""
import io

PATH = "enhanced_engine.py"
s = io.open(PATH, "r", encoding="utf-8").read()

# 1) 顶层导入 time（兜底重试用）
assert "import re, os, sys, json, random" in s, "import line not found"
s = s.replace("import re, os, sys, json, random",
              "import re, os, sys, json, random, time")

# 2) 替换 generate_chitchat：加重试与兜底
OLD = '''def generate_chitchat(agent, target, gossip_about, time_label, history_lines):
    """生成一条轻松闲聊消息（非任务），可顺带八卦第三方。返回消息正文。"""
    sys_p = (
        f"你是{agent.name}，一个活生生的人。你内里真实的样子：{agent.persona_cognitive}。\\n"
        f"现在是{time_label}，你在{agent.envName}。\\n"
        f"你打算给你的联系人【{target}】发一条轻松的闲聊消息——不是正事，就是朋友间随便聊聊："
        f"吐槽天气/日常、分享件小事、问候，或者顺带提起一个你们都认识的人。\\n"
    )
    if history_lines:
        sys_p += f"你们近期的往来（可以自然接上「上次你…」之类）：\\n{history_lines}\\n"
    if gossip_about:
        sys_p += (f"消息里可以顺带提一句你们共同认识的【{gossip_about}】的近况或八卦，"
                  f"像朋友传话那样自然。\\n")
    sys_p += ("只输出这一条消息的正文内容（不要带「向【】发送」前缀，不要任何解释或引号），"
              "用你平时说话的语气，简短自然，一两句就好。")
    user_p = f"写一条发给【{target}】的闲聊消息。"
    try:
        rsp = call_model([{"role": "system", "content": sys_p},
                          {"role": "user", "content": user_p}],
                         max_tokens=CHITCHAT_MAX_TOKENS)
        return getContent(rsp).strip().strip('"').strip("'").strip()
    except Exception as e:
        print(f"[WARN] 闲聊生成失败：{e}")
        return ""'''

NEW = '''def _chitchat_fallback(agent, target, gossip_about):
    """LLM 不可用时的兜底闲聊（保证闲聊层始终有产出）。"""
    base = [
        f"{target}，在忙吗？我这边刚闲下来，随便想想你。",
        f"{target}，今天天气怪舒服的，你那儿咋样？",
        f"{target}，刚泡了杯茶，突然想找你唠两句。",
        f"{target}，最近过得咋样？有空一起瞎溜达啊。",
    ]
    msg = random.choice(base)
    if gossip_about:
        msg += f"（对了，{gossip_about}最近好像挺有意思的。）"
    return msg


def generate_chitchat(agent, target, gossip_about, time_label, history_lines):
    """生成一条轻松闲聊消息（非任务），可顺带八卦第三方。返回消息正文。
    含重试与兜底：推理模型偶发返回空（截断/限流）时重试，仍失败则用模板兜底。"""
    sys_p = (
        f"你是{agent.name}，一个活生生的人。你内里真实的样子：{agent.persona_cognitive}。\\n"
        f"现在是{time_label}，你在{agent.envName}。\\n"
        f"你打算给你的联系人【{target}】发一条轻松的闲聊消息——不是正事，就是朋友间随便聊聊："
        f"吐槽天气/日常、分享件小事、问候，或者顺带提起一个你们都认识的人。\\n"
    )
    if history_lines:
        sys_p += f"你们近期的往来（可以自然接上「上次你…」之类）：\\n{history_lines}\\n"
    if gossip_about:
        sys_p += (f"消息里可以顺带提一句你们共同认识的【{gossip_about}】的近况或八卦，"
                  f"像朋友传话那样自然。\\n")
    sys_p += ("只输出这一条消息的正文内容（不要带「向【】发送」前缀，不要任何解释或引号），"
              "用你平时说话的语气，简短自然，一两句就好。")
    user_p = f"写一条发给【{target}】的闲聊消息。"
    last = ""
    for _attempt in range(3):
        try:
            rsp = call_model([{"role": "system", "content": sys_p},
                              {"role": "user", "content": user_p}],
                             max_tokens=CHITCHAT_MAX_TOKENS)
            last = getContent(rsp).strip().strip('"').strip("'").strip()
        except Exception as e:
            print(f"[WARN] 闲聊生成异常：{e}")
            last = ""
        if last:
            return last
        time.sleep(1.5)  # 限流时退避
    return _chitchat_fallback(agent, target, gossip_about)'''

assert OLD in s, "generate_chitchat old block not found"
s = s.replace(OLD, NEW, 1)
print("[OK] generate_chitchat 已加重试+兜底")

io.open(PATH, "w", encoding="utf-8").write(s)
print("patch2 写入完成。")
