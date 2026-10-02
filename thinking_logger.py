# -*- coding: utf-8 -*-
"""thinking_logger.py - Thinking Log System"""
import json, os, time, re
from datetime import datetime
from collections import Counter


class ThinkingLogger:
    def __init__(self, agent_name, log_file=None):
        self.agent_name = agent_name
        self.log_file = log_file or f"thinking_{agent_name}.jsonl"
        self.entries = []
        self._load()

    def _load(self):
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            self.entries.append(json.loads(line))
            except Exception:
                pass

    def log(self, messages, think="", reply=""):
        entry = {
            "agent": self.agent_name,
            "time": time.time(),
            "time_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "messages": [str(m)[:200] for m in (messages or [])],
            "think": think,
            "reply": (reply or "")[:500],
        }
        self.entries.append(entry)
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass
        return entry

    def get_recent(self, limit=10):
        return self.entries[-limit:]

    def get_today(self):
        today = datetime.now().strftime("%Y-%m-%d")
        return [e for e in self.entries if e.get("time_str", "").startswith(today)]

    def analyze(self, limit=100):
        recent = self.entries[-limit:]
        if not recent:
            return {"total": 0}
        tl = [len(e.get("think", "")) for e in recent if e.get("think")]
        rl = [len(e.get("reply", "")) for e in recent if e.get("reply")]
        ht = sum(1 for e in recent if e.get("think"))
        at = " ".join([e.get("think", "") for e in recent])
        words = re.findall(r'[\u4e00-\u9fa5]{2,4}', at)
        counter = Counter(words)
        kw = [w for w, c in counter.most_common(10) if c >= 2]
        return {
            "total": len(recent),
            "think_rate": ht / len(recent) if recent else 0,
            "avg_think_length": sum(tl) / len(tl) if tl else 0,
            "avg_reply_length": sum(rl) / len(rl) if rl else 0,
            "keywords": kw,
        }

    def get_think_patterns(self):
        pats = {"decision_making": 0, "emotion_processing": 0, "memory_recall": 0, "planning": 0, "analysis": 0}
        km = {
            "decision_making": ["决定", "选择", "应该", "要不要", "是否"],
            "emotion_processing": ["感觉", "心情", "开心", "难过", "生气", "害怕"],
            "memory_recall": ["记得", "想起", "以前", "之前", "曾经"],
            "planning": ["计划", "打算", "准备", "接下来", "然后"],
            "analysis": ["分析", "思考", "理解", "明白", "发现"],
        }
        for e in self.entries:
            th = e.get("think", "")
            for pat, kws in km.items():
                if any(k in th for k in kws):
                    pats[pat] += 1
        return pats

    def export_for_analysis(self, output_file=None):
        a = {
            "agent": self.agent_name,
            "total_entries": len(self.entries),
            "analysis": self.analyze(),
            "patterns": self.get_think_patterns(),
            "recent_entries": self.get_recent(20),
        }
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(a, f, ensure_ascii=False, indent=2)
        return a