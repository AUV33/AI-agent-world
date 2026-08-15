# -*- coding: utf-8 -*-
"""
thinking_logger.py —— 思考日志系统（参考水濑祈架构）
=====================================================================
特性：
  - 记录AI的内心思考过程
  - 分离思考与回复
  - 支持思考分析
  - JSONL格式便于后续处理

用法：
  from thinking_logger import ThinkingLogger
  
  logger = ThinkingLogger("陈子墨")
  logger.log(messages, think="我在想...", reply="我说...")
  analysis = logger.analyze()
=====================================================================
"""
import json
import os
import time
from datetime import datetime
from collections import Counter


class ThinkingLogger:
    """思考日志系统"""

    def __init__(self, agent_name, log_file=None):
        self.agent_name = agent_name
        self.log_file = log_file or f"thinking_{agent_name}.jsonl"
        self.entries = []
        self._load()

    def _load(self):
        """加载历史日志"""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            self.entries.append(json.loads(line))
            except Exception:
                pass

    def log(self, messages, think="", reply="", context=None):
        """
        记录一次思考过程
        
        Args:
            messages: 发送给模型的消息
            think: 内心思考
            reply: 最终回复
            context: 额外上下文
        """
        entry = {
            "time": time.time(),
            "time_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "agent": self.agent_name,
            "messages": messages if isinstance(messages, list) else [messages],
            "think": think,
            "reply": reply,
            "context": context or {},
        }
        
        self.entries.append(entry)
        
        # 写入文件
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass
        
        return entry

    def get_recent(self, limit=10):
        """获取最近的思考记录"""
        return self.entries[-limit:]

    def get_today(self):
        """获取今天的思考记录"""
        today = datetime.now().strftime("%Y-%m-%d")
        return [e for e in self.entries if e.get("time_str", "").startswith(today)]

    def analyze(self, limit=100):
        """分析思考模式"""
        recent = self.entries[-limit:]
        if not recent:
            return {"total": 0}
        
        # 统计思考长度
        think_lengths = [len(e.get("think", "")) for e in recent if e.get("think")]
        reply_lengths = [len(e.get("reply", "")) for e in recent if e.get("reply")]
        
        # 统计思考频率
        has_think = sum(1 for e in recent if e.get("think"))
        
        # 提取关键词
        all_thinks = " ".join([e.get("think", "") for e in recent])
        words = self._extract_keywords(all_thinks)
        
        return {
            "total": len(recent),
            "think_rate": has_think / len(recent) if recent else 0,
            "avg_think_length": sum(think_lengths) / len(think_lengths) if think_lengths else 0,
            "avg_reply_length": sum(reply_lengths) / len(reply_lengths) if reply_lengths else 0,
            "keywords": words[:10],
            "time_range": {
                "start": recent[0].get("time_str"),
                "end": recent[-1].get("time_str"),
            }
        }

    def _extract_keywords(self, text):
        """提取关键词（简单实现）"""
        # 简单的中文分词
        import re
        words = re.findall(r'[\u4e00-\u9fa5]{2,4}', text)
        counter = Counter(words)
        return [word for word, count in counter.most_common(20) if count >= 2]

    def get_think_patterns(self):
        """分析思考模式"""
        patterns = {
            "decision_making": 0,  # 决策类思考
            "emotion_processing": 0,  # 情绪处理
            "memory_recall": 0,  # 回忆
            "planning": 0,  # 计划
            "analysis": 0,  # 分析
        }
        
        keywords_map = {
            "decision_making": ["决定", "选择", "应该", "要不要", "是否"],
            "emotion_processing": ["感觉", "心情", "开心", "难过", "生气", "害怕"],
            "memory_recall": ["记得", "想起", "以前", "之前", "曾经"],
            "planning": ["计划", "打算", "准备", "接下来", "然后"],
            "analysis": ["分析", "思考", "理解", "明白", "发现"],
        }
        
        for entry in self.entries:
            think = entry.get("think", "")
            for pattern, keywords in keywords_map.items():
                if any(kw in think for kw in keywords):
                    patterns[pattern] += 1
        
        return patterns

    def export_for_analysis(self, output_file=None):
        """导出用于分析"""
        analysis = {
            "agent": self.agent_name,
            "total_entries": len(self.entries),
            "analysis": self.analyze(),
            "patterns": self.get_think_patterns(),
            "recent_entries": self.get_recent(20),
        }
        
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(analysis, f, ensure_ascii=False, indent=2)
        
        return analysis


# 测试代码
if __name__ == "__main__":
    logger = ThinkingLogger("测试角色")
    
    # 模拟思考记录
    logger.log(
        messages=["今天天气不错"],
        think="阳光很好，适合出去走走，但是作业还没写完...",
        reply="嗯，天气确实不错"
    )
    
    logger.log(
        messages=["考试考得怎么样"],
        think="这次数学考得不好，有点难过，但不想让别人看出来...",
        reply="还行吧，就那样"
    )
    
    analysis = logger.analyze()
    print(f"分析结果: {json.dumps(analysis, ensure_ascii=False, indent=2)}")
    
    patterns = logger.get_think_patterns()
    print(f"思考模式: {patterns}")
