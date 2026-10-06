# -*- coding: utf-8 -*-
"""life_state.py - Life State System"""
import json, os, time
from datetime import datetime


class LifeState:
    SCHEDULE = {
        "06:00-07:00": ("起床洗漱", "宿舍"),
        "07:00-08:00": ("早餐", "食堂"),
        "08:00-12:00": ("上课", "教室"),
        "12:00-14:00": ("午餐和午休", "食堂/宿舍"),
        "14:00-17:30": ("上课", "教室"),
        "17:30-19:00": ("晚餐和休息", "食堂"),
        "19:00-21:00": ("晚自习", "教室"),
        "21:00-23:00": ("自由活动", "宿舍"),
        "23:00-06:00": ("睡觉", "宿舍"),
    }

    def __init__(self, agent_name, state_file=None, routine=None):
        self.agent_name = agent_name
        self.state_file = state_file or f"life_{agent_name}.json"
        self.custom_activity = None
        self.custom_location = None
        self.sim_now = None          # 模拟时钟（datetime 或 "HH:MM"/"YYYY-MM-DD HH:MM"）；None 时回退真实时钟
        self.routine = routine or self.SCHEDULE   # per-agent 生活轨迹；None 时用默认学生表
        self.events = []
        self._load()

    def _load(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.custom_activity = data.get("custom_activity")
                self.custom_location = data.get("custom_location")
                self.events = data.get("events", [])[-200:]
            except Exception:
                pass

    def save(self):
        try:
            data = {
                "agent_name": self.agent_name,
                "custom_activity": self.custom_activity,
                "custom_location": self.custom_location,
                "events": self.events[-200:],
                "updated_at": time.time(),
            }
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @staticmethod
    def _hm_to_min(t):
        h, m = map(int, t.split(":"))
        return h * 60 + m

    @staticmethod
    def _resolve_time(ref):
        """把 sim_now（datetime / 'HH:MM' / 'YYYY-MM-DD HH:MM' / None）归一成 datetime。"""
        if ref is None:
            return datetime.now()
        if isinstance(ref, datetime):
            return ref
        s = str(ref).strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%H:%M"):
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                pass
        try:
            return datetime.strptime(s[-5:], "%H:%M")
        except Exception:
            return datetime.now()

    def get_current_state(self, sim_now=None):
        if self.custom_activity:
            return {"activity": self.custom_activity, "location": self.custom_location or "未知"}
        now = self._resolve_time(sim_now if sim_now is not None else self.sim_now)
        current_time = now.strftime("%H:%M")
        cur = self._hm_to_min(current_time)
        # 支持两种 routine 格式：dict{"08:00-12:00":(act,loc)} 或 list[{"start","end","activity","location"}]
        if isinstance(self.routine, list):
            for seg in self.routine:
                s = self._hm_to_min(seg["start"])
                e = self._hm_to_min(seg["end"])
                act = seg.get("activity", "自由活动")
                loc = seg.get("location", "未知")
                if s <= e:
                    if s <= cur < e:
                        return {"activity": act, "location": loc}
                else:  # 跨午夜时段
                    if cur >= s or cur < e:
                        return {"activity": act, "location": loc}
        else:
            for time_range, (activity, location) in self.routine.items():
                start, end = time_range.split("-")
                s, e = self._hm_to_min(start), self._hm_to_min(end)
                if s <= e:
                    if s <= cur < e:
                        return {"activity": activity, "location": location}
                else:  # 跨午夜时段（如 23:00-06:00）
                    if cur >= s or cur < e:
                        return {"activity": activity, "location": location}
        return {"activity": "自由活动", "location": "未知"}

    def set_custom_activity(self, activity, location=None):
        self.custom_activity = activity
        self.custom_location = location
        self.add_event("custom", f"自定义活动：{activity}（{location}）")
        self.save()

    def clear_custom_activity(self):
        self.custom_activity = None
        self.custom_location = None
        self.save()

    def add_event(self, event_type, description):
        event = {
            "time": time.time(),
            "time_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": event_type,
            "description": description,
        }
        self.events.append(event)
        self.save()

    def get_schedule_context(self):
        state = self.get_current_state()
        now = self._resolve_time(self.sim_now).strftime("%H:%M")
        return f"当前时间：{now}，活动：{state['activity']}，位置：{state['location']}"