# -*- coding: utf-8 -*-
"""event_log.py - 结构化事件记录（按场景 / 按人物 两种视图）

每条"行动"被记成一条事件：{time, agent, scene, action, to?}
- 原始流 events.jsonl：机器可读，便于后续任意聚合
- record_by_scene.md：📍 某场景内，每个人都干了什么
- record_by_person.md：👤 某个人，在所有场景都干了什么

记录的是已过滤的对外文本（filter_thinking 之后），与"干净结果"一致。
"""
import os, json
from collections import defaultdict


class EventLog:
    def __init__(self, base_dir=".", raw_name="events.jsonl",
                 scene_name="record_by_scene.md", person_name="record_by_person.md"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        self.raw_path = os.path.join(base_dir, raw_name)
        self.scene_path = os.path.join(base_dir, scene_name)
        self.person_path = os.path.join(base_dir, person_name)
        self.events = []                 # 规范事件流
        self._by_scene = defaultdict(list)
        self._by_person = defaultdict(list)

    def record(self, time_label, agent, scene, action, msg_to=None, kind=None):
        """记一条行动事件。msg_to 为接收方列表（IM 时）；kind 标记类型（如 chitchat）。"""
        ev = {"time": time_label, "agent": agent, "scene": scene, "action": action}
        if msg_to:
            ev["to"] = list(msg_to)
        if kind:
            ev["kind"] = kind
        self.events.append(ev)
        self._by_scene[scene].append(ev)
        self._by_person[agent].append(ev)

    @staticmethod
    def _fmt_to(ev):
        t = ev.get("to")
        prefix = "💬 " if ev.get("kind") == "chitchat" else ""
        if t:
            return prefix + " → 发给【" + "、".join(t) + "】"
        return prefix

    def flush(self):
        """落盘：原始流 + 两种视图。幂等，可多次调用。"""
        # 1) 原始事件流（追加式重写，保证完整）
        with open(self.raw_path, "w", encoding="utf-8") as f:
            for ev in self.events:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")

        # 2) 按场景：某一场景内每个人都干了什么
        with open(self.scene_path, "w", encoding="utf-8") as f:
            f.write("# 按场景记录：某一场景内每个人都干了什么\n\n")
            for scene in sorted(self._by_scene):
                f.write(f"## 📍 {scene}\n\n")
                for ev in self._by_scene[scene]:
                    f.write(f"- [{ev['time']}] **{ev['agent']}**：{ev['action']}{self._fmt_to(ev)}\n")
                f.write("\n")

        # 3) 按人物：每个人都干了什么
        with open(self.person_path, "w", encoding="utf-8") as f:
            f.write("# 按人物记录：每个人都干了什么\n\n")
            for agent in sorted(self._by_person):
                f.write(f"## 👤 {agent}\n\n")
                for ev in self._by_person[agent]:
                    f.write(f"- [{ev['time']}] @{ev['scene']}：{ev['action']}{self._fmt_to(ev)}\n")
                f.write("\n")
