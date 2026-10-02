# -*- coding: utf-8 -*-
"""environment.py - 世界状态单一事实源（对标 OASIS Environment Server）。

把分散在 engine.py 的 agents / envs / msgCenter 与 bond_system.bonds、
enhanced_engine.FACE2FACE_TALKS 收敛到一个 World 对象，作为世界状态的
唯一入口与重置点。agent 之间只经 World 读写，禁止直改对方状态/时钟。

设计原则（见《运行流重构设计》）：
1. 单一事实源 —— 世界状态只在此处持有与重置。
2. 环境中介 —— agent 间交互只通过 World 传播，不直改对方。
3. 调度独立 —— World 不含调度逻辑（见 time_engine.py）。
4. 事件驱动 —— IM / f2f / 移动经 EventBus 通知观察者（见 event_bus.py）。
"""
import engine
from bond_system import bonds
import enhanced_engine


class World:
    """世界状态容器：持有 engine 的既有实例（同一对象引用，无重复状态）。"""

    def __init__(self):
        # 直接持有 engine 的既有实例，避免状态分裂
        self.agents = engine.agents
        self.envs = engine.envs
        self.msgCenter = engine.msgCenter
        self.bonds = bonds
        self.face_to_face = enhanced_engine.FACE2FACE_TALKS

    # ---------------- 重置（唯一重置点） ----------------
    def reset(self):
        """清空全局世界状态，保证每次连续运行从干净环境开始。"""
        self.agents.clear()
        self.envs.env.clear()
        self.msgCenter.paddingMsgList.clear()
        self.face_to_face.clear()

    # ---------------- 场景 ----------------
    def get_env(self, name):
        return self.envs.get_env(name)

    def add_env(self, name, info=''):
        self.envs.add_env(name, info)

    def get_all_envNameList(self):
        return self.envs.get_all_envNameList()

    def update_envInfo_by_AI(self, *args, **kwargs):
        return self.envs.update_envInfo_by_AI(*args, **kwargs)

    # ---------------- IM（异步投递，纯投递不拉钟） ----------------
    def send_im(self, frm, to, msg):
        self.msgCenter.send_message_by_msg(frm, to, msg)

    def send_im_by_action(self, frm, action):
        return self.msgCenter.send_message_by_action(frm, action)

    def get_padding_msg(self, name):
        return self.msgCenter.get_padding_msg(name)

    # ---------------- 关系 ----------------
    def bond_update(self, a, b, delta, note=''):
        if self.bonds is not None:
            self.bonds.update(a, b, delta, note=note)

    # ---------------- 当面会话（Phase 3 落地） ----------------
    def record_face_to_face(self, scene, participants, started_by, time_label, topic=''):
        """记录一场当面会话，供同场景旁观者经 get_joinable_context 看到并加入。"""
        self.face_to_face.setdefault(scene, []).append({
            'participants': set(participants),
            'started_by': started_by,
            'started_at': time_label,
            'topic': topic,
        })

    def get_joinable_context(self, agent):
        """返回同场景、agent 不在其中、可加入的当面会话描述（空串=无可加入）。"""
        scene = agent.envName
        talks = self.face_to_face.get(scene, [])
        lines = []
        for t in talks:
            if agent.name in t['participants']:
                continue
            others = '、'.join(sorted(p for p in t['participants'] if p != agent.name))
            if others:
                lines.append(f"{others}正在{scene}当面聊（始于{t['started_at']}）")
        return '\n'.join(lines)
