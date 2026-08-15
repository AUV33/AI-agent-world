# -*- coding: utf-8 -*-
"""
life_state.py —— 生活状态系统（参考水濑祈架构）
=====================================================================
特性：
  - 作息时间表
  -活动状态机
  - 跨天记忆
  - 随机事件

用法：
  from life_state import LifeState
  
  life = LifeState("陈子墨")
  state = life.get_current_state()
  activity = life.get_activity()
=====================================================================
"""
import json
import os
import random
import time
from datetime import datetime, timedelta


class LifeState:
    """生活状态系统"""

    # 高中生作息时间表
    SCHEDULE = {
        "weekday": {
            0: "sleep",      # 00:00 - 睡觉
            6: "waking",     # 06:00 - 起床
            7: "breakfast",  # 07:00 - 早餐
            8: "class",      # 08:00 - 上课
            12: "lunch",     # 12:00 - 午餐
            13: "rest",      # 13:00 - 午休
            14: "class",     # 14:00 - 上课
            17: "dinner",    # 17:00 - 晚餐
            18: "study",     # 18:00 - 晚自习
            21: "free",      # 21:00 - 自由时间
            22: "sleep",     # 22:00 - 睡觉
        },
        "weekend": {
            0: "sleep",
            8: "waking",
            9: "breakfast",
            10: "free",
            12: "lunch",
            13: "rest",
            14: "free",
            18: "dinner",
            19: "free",
            22: "sleep",
        }
    }

    # 活动描述
    ACTIVITIES = {
        "sleep": ["睡觉", "熟睡中", "做梦"],
        "waking": ["刚醒来", "赖床", "起床"],
        "breakfast": ["吃早餐", "在食堂", "啃面包"],
        "class": ["上课", "听课", "自习"],
        "lunch": ["吃午饭", "在食堂", "和同学一起"],
        "rest": ["午休", "趴着睡", "休息"],
        "dinner": ["吃晚饭", "在食堂", "泡面"],
        "study": ["晚自习", "刷题", "复习"],
        "free": ["自由活动", "在宿舍", "打球", "看手机", "打游戏", "看番"],
    }

    # 场景映射
    LOCATIONS = {
        "sleep": "宿舍楼-302寝室",
        "waking": "宿舍楼-302寝室",
        "breakfast": "食堂",
        "class": "教学楼-高二(3)班",
        "lunch": "食堂",
        "rest": "宿舍楼-302寝室",
        "dinner": "食堂",
        "study": "教学楼-高二(3)班",
        "free": "宿舍楼-302寝室",
    }

    def __init__(self, agent_name, state_file=None):
        self.agent_name = agent_name
        self.state_file = state_file or f"life_{agent_name}.json"
        self.data = {
            "date": "",
            "state": "sleep",
            "activity": "",
            "location": "",
            "state_changed": 0.0,
            "today": {
                "wake": None,
                "sleep": None,
                "meals": [],
                "events": [],
                "mood_changes": [],
            },
            "history": [],
        }
        self._load()
        self._check_new_day()

    def _load(self):
        """加载状态"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    self.data.update(loaded)
            except Exception:
                pass

    def save(self):
        """保存状态"""
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _check_new_day(self):
        """检查是否是新的一天"""
        today = datetime.now().strftime("%Y-%m-%d")
        if self.data.get("date") != today:
            # 保存昨天的记录
            if self.data.get("date"):
                yesterday = dict(self.data.get("today") or {})
                yesterday["date"] = self.data.get("date")
                self.data.setdefault("history", []).append(yesterday)
                self.data["history"] = self.data["history"][-30:]  # 保留30天
            
            # 重置今天
            self.data["date"] = today
            self.data["state"] = "sleep"
            self.data["activity"] = ""
            self.data["location"] = ""
            self.data["today"] = {
                "wake": None,
                "sleep": None,
                "meals": [],
                "events": [],
                "mood_changes": [],
            }
            self.save()

    def get_schedule_state(self, hour=None, weekday=None):
        """根据时间获取应该处于的状态"""
        now = datetime.now()
        hour = hour or now.hour
        weekday = weekday or now.weekday()
        
        schedule = self.SCHEDULE["weekend" if weekday >= 5 else "weekday"]
        
        # 找到当前时间对应的状态
        current_state = "sleep"
        for h in sorted(schedule.keys()):
            if hour >= h:
                current_state = schedule[h]
        
        return current_state

    def update(self):
        """更新状态（根据时间自动更新）"""
        now = datetime.now()
        scheduled_state = self.get_schedule_state()
        
        # 如果状态发生变化
        if scheduled_state != self.data["state"]:
            old_state = self.data["state"]
            self.data["state"] = scheduled_state
            self.data["state_changed"] = time.time()
            
            # 记录特殊事件
            if scheduled_state == "waking":
                self.data["today"]["wake"] = now.strftime("%H:%M")
            elif scheduled_state == "sleep" and old_state != "sleep":
                self.data["today"]["sleep"] = now.strftime("%H:%M")
            elif scheduled_state in ["breakfast", "lunch", "dinner"]:
                self.data["today"]["meals"].append({
                    "time": now.strftime("%H:%M"),
                    "meal": scheduled_state
                })
            
            # 更新活动和位置
            self._update_activity()
            self.save()
        
        return self.data["state"]

    def _update_activity(self):
        """更新活动描述"""
        state = self.data["state"]
        activities = self.ACTIVITIES.get(state, ["未知活动"])
        self.data["activity"] = random.choice(activities)
        self.data["location"] = self.LOCATIONS.get(state, "未知地点")

    def get_current_state(self):
        """获取当前状态"""
        self.update()
        return {
            "state": self.data["state"],
            "activity": self.data["activity"],
            "location": self.data["location"],
            "time_in_state": time.time() - self.data.get("state_changed", time.time()),
        }

    def get_context_string(self):
        """获取用于prompt的状态描述"""
        state = self.get_current_state()
        time_in_state = state["time_in_state"]
        
        if time_in_state < 300:  # 5分钟内
            time_desc = "刚刚"
        elif time_in_state < 3600:  # 1小时内
            time_desc = f"{int(time_in_state / 60)}分钟前"
        else:
            time_desc = f"{int(time_in_state / 3600)}小时前"
        
        return f"当前状态：{state['activity']}（在{state['location']}，{time_desc}开始）"

    def add_event(self, event_type, description):
        """添加事件"""
        self.data["today"]["events"].append({
            "time": datetime.now().strftime("%H:%M"),
            "type": event_type,
            "description": description
        })
        self.save()

    def get_today_summary(self):
        """获取今天的总结"""
        today = self.data["today"]
        parts = []
        
        if today["wake"]:
            parts.append(f"起床时间：{today['wake']}")
        if today["sleep"]:
            parts.append(f"睡觉时间：{today['sleep']}")
        if today["meals"]:
            meals_desc = "、".join([f"{m['meal']}({m['time']})" for m in today["meals"]])
            parts.append(f"用餐：{meals_desc}")
        if today["events"]:
            parts.append(f"事件：{len(today['events'])}件")
        
        return "；".join(parts) if parts else "今天暂无记录"

    def is_awake(self):
        """是否醒着"""
        state = self.get_current_state()["state"]
        return state not in ["sleep"]

    def is_in_class(self):
        """是否在上课"""
        state = self.get_current_state()["state"]
        return state == "class"

    def is_free(self):
        """是否空闲"""
        state = self.get_current_state()["state"]
        return state == "free"


# 测试代码
if __name__ == "__main__":
    life = LifeState("测试角色")
    state = life.get_current_state()
    print(f"当前状态: {state}")
    print(f"上下文描述: {life.get_context_string()}")
    print(f"今天总结: {life.get_today_summary()}")
