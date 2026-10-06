# -*- coding: utf-8 -*-
"""enhanced_agent_factory.py - 增强版角色工厂"""
import json, os, sys

PROJ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJ)

from enhanced_engine import EnhancedAgent, envs, agents, BOND_ENABLED, CONFIG
from bond_system import bonds


ROUTINES_FILE = os.path.join(PROJ, "data", "routines.json")
_ROUTINES_CACHE = None


def _get_routines():
    """加载 per-agent 生活轨迹（data/routines.json），缓存；缺失时返回 {}。"""
    global _ROUTINES_CACHE
    if _ROUTINES_CACHE is not None:
        return _ROUTINES_CACHE
    _ROUTINES_CACHE = {}
    if os.path.exists(ROUTINES_FILE):
        try:
            with open(ROUTINES_FILE, 'r', encoding='utf-8') as f:
                _ROUTINES_CACHE = json.load(f)
        except Exception:
            _ROUTINES_CACHE = {}
    return _ROUTINES_CACHE


def _register_routine_scenes(routines):
    """把轨迹里出现的所有 location 注册为场景（幂等），确保角色能按轨迹移动过去。"""
    for _segs in routines.values():
        for _seg in _segs:
            _loc = _seg.get("location")
            if _loc and _loc not in envs.get_all_envNameList():
                envs.add_env(_loc, '')


REQUIRED_ROLE_FIELDS = ("persona_cognitive", "life", "memory")


def report_role_gaps(agents_data):
    """角色数据完整性自检：缺内心素材的角色【必须可见】，不许静默变成空槽。

    为什么要有这一步：「每个人都是主角」——一个角色没有 persona_cognitive，
    他的内心脑提示里"你内里真实的样子：。"就是空的，双脑会退化成单脑，
    而这件事在日志里完全看不出来（历史缺陷：默认 13 人里 10 人缺该字段）。
    返回 {字段: [角色名, ...]}（只含确实有缺口的字段）。
    """
    gaps = {}
    for k in REQUIRED_ROLE_FIELDS:
        missing = [d.get("name") for d in agents_data if not d.get(k)]
        if missing:
            gaps[k] = missing
    if gaps:
        for k, names in gaps.items():
            print("[角色数据] 缺 %s：%d/%d 人 —— %s"
                  % (k, len(names), len(agents_data), "、".join(names)))
    else:
        print("[角色数据] 完整性自检通过：%d 人都有 persona_cognitive / life / memory"
              % len(agents_data))
    return gaps


def load_enhanced_agents(file_path):
    """加载增强版角色设定（支持impressions字段）"""
    with open(file_path, 'r', encoding='utf-8') as f:
        agents_data = json.load(f)

    report_role_gaps(agents_data)
    routines = _get_routines()
    _register_routine_scenes(routines)

    for data in agents_data:
        env_name = data.get('初始位置', data.get('envName', '未知'))
        if env_name not in envs.get_all_envNameList():
            envs.add_env(env_name, '')

        agent = EnhancedAgent(
            name=data['name'],
            persona=data['persona'],
            envName=env_name,
            memory=data.get('memory', ''),
            impressions=data.get('impressions', None),
            addressBook=data.get('addressBook', []),
            persona_cognitive=data.get('persona_cognitive', ''),
            desires=data.get('desires', []),
            life_summary=data.get('life', ''),
            psych=data.get('psych'),
            routine=routines.get(data['name'])
        )
        agents[data['name']] = agent

    # 参考水濑祈 bond 分层：按通讯录预置角色间关系强度（幂等，重复加载不覆盖已有值）
    if BOND_ENABLED:
        for _ag in agents.values():
            for _other in _ag.addressBook:
                if _other in agents:
                    bonds.ensure(_ag.name, _other, CONFIG.get("bond_init_in_book", 0.5))


def load_enhanced_agents_from_data(agents_data):
    """从已解析的角色数据列表加载（供"只加载子集"场景复用）。"""
    report_role_gaps(agents_data)
    routines = _get_routines()
    _register_routine_scenes(routines)

    for data in agents_data:
        env_name = data.get('初始位置', data.get('envName', '未知'))
        if env_name not in envs.get_all_envNameList():
            envs.add_env(env_name, '')

        agent = EnhancedAgent(
            name=data['name'],
            persona=data['persona'],
            envName=env_name,
            memory=data.get('memory', ''),
            impressions=data.get('impressions', None),
            addressBook=data.get('addressBook', []),
            persona_cognitive=data.get('persona_cognitive', ''),
            desires=data.get('desires', []),
            life_summary=data.get('life', ''),
            psych=data.get('psych'),
            routine=routines.get(data['name'])
        )
        agents[data['name']] = agent

    # 参考水濑祈 bond 分层：按通讯录预置角色间关系强度（幂等，重复加载不覆盖已有值）
    if BOND_ENABLED:
        for _ag in agents.values():
            for _other in _ag.addressBook:
                if _other in agents:
                    bonds.ensure(_ag.name, _other, CONFIG.get("bond_init_in_book", 0.5))


def update_envs_with_agents_info():
    """更新场景中的角色信息"""
    env_agents = {}
    for agent in agents.values():
        env_name = agent.envName
        if env_name not in env_agents:
            env_agents[env_name] = []
        env_agents[env_name].append(agent)

    for env_name, agent_list in env_agents.items():
        agent_names = [a.name for a in agent_list]
        agents_info = f"场景中有: {', '.join(agent_names)}"
        envs.update_envInfo_by_str(env_name, agents_info)