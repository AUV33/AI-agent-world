# -*- coding: utf-8 -*-
"""
emotion_system.py —— 情绪状态系统（参考水濑祈架构）
=====================================================================
特性：
  - 多维度情绪跟踪（快乐/悲伤/愤怒/恐惧/惊讶/厌恶）
  - 情绪衰减机制
  - 情绪影响行为决策
  - 情绪历史记录

用法：
  from emotion_system import EmotionSystem
  
  emotion = EmotionSystem("陈子墨")
  emotion.update("happy", 0.8, "考试考得好")
  current = emotion.get_current()
=====================================================================
"""
import json
import os
import time
from datetime import datetime


class EmotionDimension:
    """情绪维度"""
    def __init__(self, name, value=0.5, decay_rate=0.1):
        self.name = name
        self.value = value  # 0-1之间
        self.decay_rate = decay_rate  # 每小时衰减率
        self.last_update = time.time()
    
    def update(self, delta, reason=""):
        """更新情绪值"""
        self.value = max(0, min(1, self.value + delta))
        self.last_update = time.time()
    
    def decay(self):
        """情绪衰减"""
        hours_passed = (time.time() - self.last_update) / 3600
        if hours_passed > 0:
            # 向中性(0.5)衰减
            diff = self.value - 0.5
            decay_amount = diff * (1 - (1 - self.decay_rate) ** hours_passed)
            self.value = max(0, min(1, self.value - decay_amount))
            self.last_update = time.time()
    
    def to_dict(self):
        return {
            "name": self.name,
            "value": round(self.value, 3),
            "last_update": self.last_update
        }


class EmotionSystem:
    """情绪状态系统"""

    # 基础情绪维度
    DIMENSIONS = {
        "happiness": EmotionDimension("happiness", 0.5, 0.15),  # 快乐
        "sadness": EmotionDimension("sadness", 0.3, 0.2),       # 悲伤
        "anger": EmotionDimension("anger", 0.2, 0.25),          # 愤怒
        "fear": EmotionDimension("fear", 0.2, 0.2),             # 恐惧
        "surprise": EmotionDimension("surprise", 0.3, 0.3),     # 惊讶
        "disgust": EmotionDimension("disgust", 0.2, 0.2),       # 厌恶
    }

    # 情绪标签映射
    EMOTION_LABELS = {
        "happy": ("happiness", 0.3),
        "sad": ("sadness", 0.3),
        "angry": ("anger", 0.3),
        "afraid": ("fear", 0.3),
        "surprised": ("surprise", 0.3),
        "disgusted": ("disgust", 0.3),
        "excited": ("happiness", 0.4),
        "worried": ("fear", 0.2),
        "annoyed": ("anger", 0.2),
        "calm": ("happiness", 0.1),
        "neutral": (None, 0),
    }

    def __init__(self, agent_name, state_file=None):
        self.agent_name = agent_name
        self.state_file = state_file or f"emotion_{agent_name}.json"
        self.dimensions = {name: EmotionDimension(name) for name in self.DIMENSIONS}
        self.history = []
        self._load()

    def _load(self):
        """加载情绪状态"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for name, values in data.get("dimensions", {}).items():
                    if name in self.dimensions:
                        self.dimensions[name].value = values.get("value", 0.5)
                        self.dimensions[name].last_update = values.get("last_update", time.time())
                self.history = data.get("history", [])[-100:]  # 保留最近100条
            except Exception:
                pass

    def save(self):
        """保存情绪状态"""
        try:
            data = {
                "agent_name": self.agent_name,
                "dimensions": {name: dim.to_dict() for name, dim in self.dimensions.items()},
                "history": self.history[-100:],
                "updated_at": time.time()
            }
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def update(self, emotion_type, intensity=0.5, reason=""):
        """
        更新情绪状态
        
        Args:
            emotion_type: 情绪类型 (happy, sad, angry, afraid, surprised, disgusted, calm, neutral)
            intensity: 强度 (0-1)
            reason: 原因
        """
        if emotion_type in self.EMOTION_LABELS:
            dimension_name, delta = self.EMOTION_LABELS[emotion_type]
            if dimension_name:
                self.dimensions[dimension_name].update(delta * intensity, reason)
        
        # 记录历史
        self.history.append({
            "time": time.time(),
            "emotion": emotion_type,
            "intensity": intensity,
            "reason": reason,
            "state": self.get_state()
        })
        
        # 执行衰减
        self._decay_all()
        
        # 保存
        self.save()

    def _decay_all(self):
        """执行所有维度的衰减"""
        for dim in self.dimensions.values():
            dim.decay()

    def get_state(self):
        """获取当前情绪状态"""
        self._decay_all()
        return {name: round(dim.value, 3) for name, dim in self.dimensions.items()}

    def get_dominant(self):
        """获取主导情绪"""
        state = self.get_state()
        # 排除中性情绪
        non_neutral = {k: v for k, v in state.items() if k not in ["surprise", "disgust"] and abs(v - 0.5) > 0.1}
        if not non_neutral:
            return "neutral", 0.5
        
        dominant = max(non_neutral.items(), key=lambda x: abs(x[1] - 0.5))
        return dominant[0], dominant[1]

    def get_label(self):
        """获取情绪标签"""
        emotion, value = self.get_dominant()
        if emotion == "neutral" or abs(value - 0.5) < 0.15:
            return "平静"
        
        labels = {
            "happiness": "开心" if value > 0.6 else "略好",
            "sadness": "难过" if value > 0.6 else "低落",
            "anger": "愤怒" if value > 0.6 else "烦躁",
            "fear": "恐惧" if value > 0.6 else "担忧",
        }
        return labels.get(emotion, "平静")

    def get_mood_modifier(self):
        """获取情绪对行为的影响系数"""
        state = self.get_state()
        happiness = state.get("happiness", 0.5)
        sadness = state.get("sadness", 0.3)
        anger = state.get("anger", 0.2)
        
        # 计算整体心情 (-1到1)
        mood = (happiness - 0.5) * 2 - (sadness - 0.3) * 1.5 - (anger - 0.2) * 1
        return max(-1, min(1, mood))

    def get_context_string(self):
        """获取用于prompt的情绪描述"""
        label = self.get_label()
        mood = self.get_mood_modifier()
        
        if abs(mood) < 0.2:
            return f"当前心情：{label}（平静）"
        elif mood > 0:
            return f"当前心情：{label}（{mood:.1%}积极）"
        else:
            return f"当前心情：{label}（{abs(mood):.1%}消极）"

    def get_detailed_state(self):
        """获取详细的情绪状态（用于调试）"""
        state = self.get_state()
        dominant, value = self.get_dominant()
        return {
            "agent": self.agent_name,
            "dominant": dominant,
            "dominant_value": value,
            "label": self.get_label(),
            "mood_modifier": self.get_mood_modifier(),
            "dimensions": state,
            "history_count": len(self.history)
        }


# 测试代码
if __name__ == "__main__":
    emotion = EmotionSystem("测试角色")
    
    # 模拟情绪变化
    emotion.update("happy", 0.8, "考试考得好")
    print(f"当前情绪: {emotion.get_label()}")
    print(f"心情系数: {emotion.get_mood_modifier():.2f}")
    print(f"详细状态: {json.dumps(emotion.get_detailed_state(), ensure_ascii=False, indent=2)}")
    
    emotion.update("angry", 0.5, "被人嘲讽")
    print(f"\n情绪变化后: {emotion.get_label()}")
    print(f"心情系数: {emotion.get_mood_modifier():.2f}")
