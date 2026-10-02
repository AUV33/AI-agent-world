#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性补丁：把动森式互动增强写入 enhanced_engine.py（绕过工具写入问题）。"""
import io, sys

PATH = "enhanced_engine.py"
with io.open(PATH, "r", encoding="utf-8") as f:
    s = f.read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit(f"[FAIL] 期望替换 {n} 次，实际 {c} 次：\n{old[:80]}")
    s = s.replace(old, new, n)
    print(f"[OK] 替换成功（{c} 次）")

# 1) import random
rep("import re, os, sys, json", "import re, os, sys, json, random")

# 2) 配置开关
rep(
    'FORGET_LAMBDA = CONFIG.get("forget_lambda_base_days", 30)\n'
    'REFLECTION_BATCH = CONFIG.get("reflection_batch_size", 8)',
    'FORGET_LAMBDA = CONFIG.get("forget_lambda_base_days", 30)\n'
    'REFLECTION_BATCH = CONFIG.get("reflection_batch_size", 8)\n'
    '# 动森式互动增强开关（闲聊层 / 跨场景八卦 / 长期往来记忆）\n'
    'CHITCHAT_ENABLED = CONFIG.get("chitchat_enabled", False)\n'
    'CHITCHAT_PROB = CONFIG.get("chitchat_prob", 0.55)\n'
    'CHITCHAT_MAX_TOKENS = CONFIG.get("chitchat_max_tokens", 400)\n'
    'GOSSIP_ENABLED = CONFIG.get("gossip_enabled", False)\n'
    'LONGTERM_MEMORY_ENABLED = CONFIG.get("longterm_memory_enabled", False)\n'
    'INTERACTION_HISTORY_LIMIT = CONFIG.get("interaction_history_limit", 4)\n'
    'INTERACTION_CONTEXT_PAIRS = CONFIG.get("interaction_context_pairs", 6)'
)

# 3) _build_inner 签名
rep(
    "    def _build_inner(self, envInfo, time_label, life_state_info, emotion_context, memory_context,\n"
    "                     imp_text, desire_text, bond_text, rep_text, rumor_text, im_text):",
    "    def _build_inner(self, envInfo, time_label, life_state_info, emotion_context, memory_context,\n"
    "                     imp_text, desire_text, bond_text, rep_text, rumor_text, im_text,\n"
    "                     interaction_text=\"\"):"
)

# 4) _build_inner 模板注入
rep(
    "{memory_context}\n{imp_text}{desire_text}{bond_text}{rep_text}{rumor_text}{im_text}",
    "{memory_context}\n{imp_text}{desire_text}{bond_text}{rep_text}{rumor_text}{interaction_text}{im_text}"
)

# 5) get_action 调用
rep(
    "            imp_text, desire_text, bond_text, rep_text, rumor_text, im_text)",
    "            imp_text, desire_text, bond_text, rep_text, rumor_text, im_text,\n"
    "            interaction_text=self._build_interaction_context())"
)

# 6) 在 _extract_im_targets 后追加辅助函数
OLD_TARGETS = (
    'def _extract_im_targets(action):\n'
    '    """从行动文本中提取 IM 收件人（向【x】发送【...】）。"""\n'
    '    targets = [m[0] for m in re.findall(r\'向【(.+?)】发送【(.+?)】\', action)]\n'
    '    if not targets:\n'
    '        targets = [m[0] for m in re.findall(r\'向(.+?)发送【(.+?)】\', action)]\n'
    '    return targets'
)
NEW_TARGETS = OLD_TARGETS + '''


def _extract_im_pairs(action):
    """从行动文本中提取 (收件人, 内容) 对。"""
    pairs = re.findall(r'向【(.+?)】发送【(.+?)】', action)
    if not pairs:
        pairs = re.findall(r'向(.+?)发送【(.+?)】', action)
    return [(t, c) for t, c in pairs]


def _build_interaction_context(agent):
    """汇总与通讯录联系人的近期往来（跨轮持久化），用于让角色'记起上次'。"""
    if not LONGTERM_MEMORY_ENABLED:
        return ""
    book = list(agent.addressBook)
    if BOND_ENABLED:
        try:
            book.sort(key=lambda n: bonds.get(agent.name, n).get('strength', 0), reverse=True)
        except Exception:
            pass
    parts = []
    for other in book[:INTERACTION_CONTEXT_PAIRS]:
        hist = agent.memory_system.get_interaction_history_with(other, INTERACTION_HISTORY_LIMIT)
        if hist:
            lines = [f"  - [{h['time_label']}][{'你→他' if h['direction'] == 'sent' else '他→你'}] {h['content']}"
                     for h in hist]
            parts.append(f"你和{other}的近期往来：\\n" + "\\n".join(lines))
    if not parts:
        return ""
    return ("\\n\\n【你和通讯录里人的近期往来（跨轮也记得，可自然接上\\"上次你…\\"）】\\n"
            + "\\n".join(parts))


def generate_chitchat(agent, target, gossip_about, time_label, history_lines):
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
        return ""


def maybe_chitchat(agent, time_label, community_names=None, dry_run=False):
    """动森式闲聊层：按概率给一个联系人发非任务消息（可跨场景、可八卦第三方）。
    返回本次实际发送消息的收件人列表（供运行时触发加急回复）。"""
    if dry_run or not CHITCHAT_ENABLED:
        return []
    if random.random() > CHITCHAT_PROB:
        return []
    contacts = [c for c in agent.addressBook if c != agent.name]
    loaded = [n for n in agents if n != agent.name]
    loaded_contacts = [c for c in contacts if c in agents]
    target_pool = loaded_contacts or loaded
    if not target_pool:
        return []
    target = random.choice(target_pool)

    gossip_about = None
    if GOSSIP_ENABLED and random.random() < 0.5:
        pool = [c for c in (list(agent.addressBook) + list(community_names or []))
                if c not in (agent.name, target)]
        if pool:
            gossip_about = random.choice(pool)

    hist = agent.memory_system.get_interaction_history_with(target, INTERACTION_HISTORY_LIMIT)
    history_lines = "\\n".join(
        f"[{h['time_label']}][{'你→他' if h['direction'] == 'sent' else '他→你'}] {h['content']}"
        for h in hist)
    msg = generate_chitchat(agent, target, gossip_about, time_label, history_lines)
    if not msg:
        return []

    msgCenter.send_message_by_msg(agent.name, target, msg)
    if BOND_ENABLED and target in agents:
        bonds.update(agent.name, target, CONFIG.get("bond_growth_per_im", 0.03), note="闲聊往来")
    agent.memory_system.log_interaction(target, "sent", msg, time_label)
    if target in agents:
        agents[target].memory_system.log_interaction(agent.name, "received", msg, time_label)
    if EVENT_LOG is not None:
        EVENT_LOG.record(time_label, agent.name, agent.envName,
                         f"向【{target}】发送【{msg}】", msg_to=[target], kind="chitchat")
    return [target]
'''
rep(OLD_TARGETS, NEW_TARGETS)

# 7) process_agent_turn 签名
rep(
    'def process_agent_turn(agent, time_label="", dt_minutes=60):',
    'def process_agent_turn(agent, time_label="", dt_minutes=60, community_names=None, dry_run=False):'
)

# 8) process_agent_turn docstring
rep(
    '    避免双脑/泄露逻辑在多处重复。单角色异常不影响整场。返回过滤后的对外文本。"""',
    '    避免双脑/泄露逻辑在多处重复。单角色异常不影响整场。\n'
    '    返回 (过滤后的对外文本, 本次闲聊发送目标列表)。"""'
)

# 9) IM 处理块
rep(
    '        _im_targets = _extract_im_targets(filtered_action)\n'
    '        if BOND_ENABLED:\n'
    '            for _tgt in _im_targets:\n'
    '                if _tgt in agents:\n'
    '                    bonds.update(agent.name, _tgt, CONFIG.get("bond_growth_per_im", 0.03), note="近期有往来")\n'
    '\n'
    '        # 结构化事件记录（按场景/按人物两种视图）；由运行时启用\n'
    '        if EVENT_LOG is not None:\n'
    '            EVENT_LOG.record(time_label, agent.name, agent.envName, filtered_action,\n'
    '                             msg_to=_im_targets)',
    '        # 主行动里的 IM：关系升温 + 记录跨轮往来\n'
    '        _im_pairs = _extract_im_pairs(filtered_action)\n'
    '        _im_targets = [t for t, _ in _im_pairs]\n'
    '        if BOND_ENABLED:\n'
    '            for _tgt in _im_targets:\n'
    '                if _tgt in agents:\n'
    '                    bonds.update(agent.name, _tgt, CONFIG.get("bond_growth_per_im", 0.03), note="近期有往来")\n'
    '        for _tgt, _content in _im_pairs:\n'
    '            agent.memory_system.log_interaction(_tgt, "sent", _content, time_label)\n'
    '            if _tgt in agents:\n'
    '                agents[_tgt].memory_system.log_interaction(agent.name, "received", _content, time_label)\n'
    '\n'
    '        # 结构化事件记录（按场景/按人物两种视图）；由运行时启用\n'
    '        if EVENT_LOG is not None:\n'
    '            EVENT_LOG.record(time_label, agent.name, agent.envName, filtered_action,\n'
    '                             msg_to=_im_targets)'
)

# 10) 返回前加闲聊 + 返回元组
rep(
    '        envs.update_envInfo_by_AI(agent.name, old_envName, agent, filtered_action)\n'
    '        if new_envName != old_envName:\n'
    '            envs.update_envInfo_by_AI(agent.name, new_envName, agent, filtered_action)\n'
    "        print('------------------------------')\n"
    '        sys.stdout.flush()   # 每个角色处理完即刷盘，便于实时查看与防丢\n'
    '        return filtered_action\n'
    '    except Exception as e:\n'
    '        print(f"[ERROR] 角色 {agent.name} 处理失败：{type(e).__name__}: {e}")\n'
    "        print('------------------------------')\n"
    '        sys.stdout.flush()\n'
    '        return ""',
    '        envs.update_envInfo_by_AI(agent.name, old_envName, agent, filtered_action)\n'
    '        if new_envName != old_envName:\n'
    '            envs.update_envInfo_by_AI(agent.name, new_envName, agent, filtered_action)\n'
    '\n'
    '        # 动森式闲聊层（非任务消息，可跨场景/八卦第三方）\n'
    '        chitchat_targets = maybe_chitchat(agent, time_label, community_names, dry_run=dry_run)\n'
    '\n'
    "        print('------------------------------')\n"
    '        sys.stdout.flush()   # 每个角色处理完即刷盘，便于实时查看与防丢\n'
    '        return filtered_action, chitchat_targets\n'
    '    except Exception as e:\n'
    '        print(f"[ERROR] 角色 {agent.name} 处理失败：{type(e).__name__}: {e}")\n'
    "        print('------------------------------')\n"
    '        sys.stdout.flush()\n'
    '        return "", []'
)

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(s)
print("全部补丁写入完成。")
