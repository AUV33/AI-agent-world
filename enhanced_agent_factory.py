# -*- coding: utf-8 -*-
"""enhanced_agent_factory.py - 增强版角色工厂"""
import json, os, sys

PROJ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJ)

from enhanced_engine import EnhancedAgent, envs, agents, BOND_ENABLED, CONFIG
from bond_system import bonds


def load_enhanced_agents(file_path):
    """加载增强版角色设定（支持impressions字段）"""
    with open(file_path, 'r', encoding='utf-8') as f:
        agents_data = json.load(f)

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
            life_summary=data.get('life', '')
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
            life_summary=data.get('life', '')
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