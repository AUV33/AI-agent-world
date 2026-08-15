# -*- coding: utf-8 -*-
"""
group_engine.py —— 六人一起活动（群体模式）底层引擎
=====================================================
将 302 寝室的六个室友的人设一起带入，每轮生成一场六人共同参与的
校园群像活动（叙事 + 对话 + 各自记忆更新 + 场景状态更新）。

用法（由 run_school.py 调用）：
    from group_engine import run_group_step
    narration, mem_block = run_group_step(agent_list, time_label, env_name, scene_hint)
"""
import re
from caller import call_model
from engine import envs, getContent

# 一天的时间安排：每项 = (时间标签, 场景, 场景补充说明)
DAY_SCHEDULE = [
    ("06:40", "宿舍楼-302寝室", "早起的铃声响起，六人陆续醒来，洗漱、叠被、整理内务，准备去吃早饭上早读。"),
    ("07:30", "教学楼-高二(3)班", "早读时间，六人在同一间教室，各坐各的位置。"),
    ("08:30", "教学楼-高二(3)班", "上午第一节课，课堂上的小插曲。"),
    ("10:20", "操场-篮球场", "上午大课间，六人一起活动。"),
    ("12:10", "食堂", "午饭时间，六人端着餐盘围坐一桌。"),
    ("14:00", "教学楼-高二(3)班", "下午的课程，课间的小打闹。"),
    ("17:30", "操场-篮球场", "放学后，六人结伴打球或散步回寝室。"),
    ("19:00", "宿舍楼-302寝室", "晚餐后回到寝室，各自忙碌又互相搭话。"),
    ("21:30", "宿舍楼-302寝室", "洗漱、洗衣、阳台上的闲聊，卧谈会渐渐开始。"),
    ("23:00", "宿舍楼-302寝室", "熄灯前最后一段闲谈，准备就寝。"),
]


def build_group_prompt(agent_list, time_label, env_name, scene_hint=""):
    env_info = envs.get_env(env_name) or "这里还没有人"
    lines = []
    for i, a in enumerate(agent_list, 1):
        mem = a.memory or "（暂无记忆）"
        lines.append(f"{i}. {a.name}（{a.persona}）｜当前所在：{a.envName}｜记忆：{mem}")
    people = "\n".join(lines)
    header = f"现在时间是{time_label}，地点是{env_name}。"
    if scene_hint:
        header += scene_hint
    prompt = (
        header +
        "\n\n以下是六名室友（他们互相认识，都是明远中学302寝室的室友，六个人都在这个场景里）：\n" + people +
        f"\n\n场景当前状态：{env_info}\n\n"
        "请模拟接下来这段时间里六人一起的活动，六个人都必须出场，要有真实的对话、动作与细节互动。"
        "用校园群像小说的叙事方式输出，包含对话（用引号）。注意：每个人的人设、性格与说话方式要保持一致，不要崩人设。\n"
        "输出格式严格如下：\n"
        "【叙事】\n<400字左右的叙事，精炼克制，结尾单独一行【下一小时】给出接下来的走向>\n\n"
        "【角色记忆】\n陈子墨：<一句话，本轮属于陈子墨的记忆要点>\n林阳：<一句话>\n王浩宇：<一句话>\n赵天磊：<一句话>\n孙一凡：<一句话>\n周景行：<一句话>\n"
        "（六人全部都要列出，名字后面必须跟中文冒号，每人一句话）"
    )
    sys_prompt = (
        "你是一名高中校园生活小说作者，擅长写真实细腻的六人群像日常。"
        "笔触克制、生活化，带有淡淡的青春气息；人物对话符合各自性格。"
    )
    return sys_prompt, prompt


def parse_group_output(text, agent_list):
    """从模型输出中拆出【叙事】与【角色记忆】，并更新每个角色的记忆。"""
    narration = text.strip()
    mem_block = ""
    m = re.search(r'【角色记忆】\s*(.+)$', text, re.S)
    if m:
        mem_block = m.group(1)
        narration = text[:m.start()].strip()
    # 更新各自记忆（名字后跟中文冒号或英文冒号）
    if mem_block:
        for a in agent_list:
            mm = re.search(re.escape(a.name) + r'[:：]\s*([^\n]+)', mem_block)
            if mm:
                a.memory = mm.group(1).strip()
    return narration, mem_block


def run_group_step(agent_list, time_label="", env_name=None, scene_hint=""):
    """六人一起活动：生成一场群体活动叙事，更新六人记忆与场景状态。"""
    if not agent_list:
        return "", ""
    if env_name is None:
        env_name = agent_list[0].envName
    sys_prompt, prompt = build_group_prompt(agent_list, time_label, env_name, scene_hint)
    response = call_model([
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": prompt},
    ], max_tokens=600)
    text = getContent(response)
    narration, mem_block = parse_group_output(text, agent_list)

    # 更新场景状态
    envs.update_envInfo_by_str(env_name, f"{time_label}，{env_name}：{narration}")
    # 六人统一移动到当前场景
    for a in agent_list:
        a.envName = env_name
    return narration, mem_block
