# -*- coding: utf-8 -*-
"""emotion_system.py —— 情绪状态系统"""
import json, os, time

class EmotionDimension:
    def __init__(self, name, value=0.5, decay_rate=0.1):
        self.name = name
        self.value = value
        self.decay_rate = decay_rate
        self.last_update = time.time()

    def update(self, delta, reason=""):
        self.value = max(0, min(1, self.value + delta))
        self.last_update = time.time()

    def decay(self):
        hours_passed = (time.time() - self.last_update) / 3600
        if hours_passed > 0:
            diff = self.value - 0.5
            decay_amount = diff * (1 - (1 - self.decay_rate) ** hours_passed)
            self.value = max(0, min(1, self.value - decay_amount))
            self.last_update = time.time()

    def to_dict(self):
        return {"name": self.name, "value": round(self.value, 3), "last_update": self.last_update}


class EmotionSystem:
    DIMENSIONS = {
        "happiness": (0.5, 0.15), "sadness": (0.3, 0.2), "anger": (0.2, 0.25),
        "fear": (0.2, 0.2), "surprise": (0.3, 0.3), "disgust": (0.2, 0.2),
    }
    EMOTION_LABELS = {
        "happy": ("happiness", 0.3), "sad": ("sadness", 0.3), "angry": ("anger", 0.3),
        "afraid": ("fear", 0.3), "surprised": ("surprise", 0.3), "disgusted": ("disgust", 0.3),
        "excited": ("happiness", 0.4), "worried": ("fear", 0.2), "annoyed": ("anger", 0.2),
        "calm": ("happiness", 0.1), "neutral": (None, 0),
    }

    def __init__(self, agent_name, state_file=None):
        self.agent_name = agent_name
        self.state_file = state_file or f"emotion_{agent_name}.json"
        self.dimensions = {name: EmotionDimension(name, v, d) for name, (v, d) in self.DIMENSIONS.items()}
        self.history = []
        self._load()

    def _load(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for name, values in data.get("dimensions", {}).items():
                    if name in self.dimensions:
                        self.dimensions[name].value = values.get("value", 0.5)
                        self.dimensions[name].last_update = values.get("last_update", time.time())
                self.history = data.get("history", [])[-100:]
            except Exception:
                pass

    def save(self):
        try:
            data = {"agent_name": self.agent_name, "dimensions": {n: d.to_dict() for n, d in self.dimensions.items()}, "history": self.history[-100:], "updated_at": time.time()}
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def update(self, emotion_type, intensity=0.5, reason=""):
        if emotion_type in self.EMOTION_LABELS:
            dimension_name, delta = self.EMOTION_LABELS[emotion_type]
            if dimension_name:
                self.dimensions[dimension_name].update(delta * intensity, reason)
        self.history.append({"time": time.time(), "emotion": emotion_type, "intensity": intensity, "reason": reason})
        for dim in self.dimensions.values():
            dim.decay()
        self.save()

    def get_current(self):
        for dim in self.dimensions.values():
            dim.decay()
        return {name: round(dim.value, 3) for name, dim in self.dimensions.items()}

    def get_dominant(self):
        current = self.get_current()
        if not current:
            return "neutral", 0.5
        return max(current.items(), key=lambda x: x[1])

    def get_context_string(self):
        dominant, value = self.get_dominant()
        mp = {"happiness": "开心", "sadness": "难过", "anger": "生气", "fear": "害怕", "surprise": "惊讶", "disgust": "厌恶"}
        label = mp.get(dominant, "平静")
        if value > 0.7: return f"情绪状态：非常{label}"
        elif value > 0.5: return f"情绪状态：{label}"
        else: return "情绪状态：平静"