# -*- coding: utf-8 -*-
"""
enhanced_memory.py —— 增强版记忆系统（参考水濑祈架构）
=====================================================================
特性：
  - SQLite 持久化存储
  - 记忆压缩机制（避免上下文过长）
  - 会话级记忆隔离
  - 长期事实存储
  - 情感状态跟踪
  - 内心想法记录

用法：
  from enhanced_memory import EnhancedMemory
  
  memory = EnhancedMemory(agent_name="陈子墨", db_path="memory.db")
  memory.add_message("今天考试考得不错")
  memory.add_fact("成绩在年级前五")
  context = memory.get_context(max_tokens=500)
=====================================================================
"""
import json
import os
import sqlite3
import threading
import time
from datetime import datetime


class EnhancedMemory:
    """增强版记忆系统"""

    SCHEMA = """
    PRAGMA journal_mode=WAL;
    PRAGMA synchronous=NORMAL;
    PRAGMA cache_size=-8000;

    -- 对话历史
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_name TEXT NOT NULL,
        timestamp REAL NOT NULL,
        content TEXT NOT NULL,
        msg_type TEXT DEFAULT 'action',
        compressed INTEGER DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_msg_agent_ts ON messages(agent_name, timestamp);

    -- 摘要记忆（压缩后的历史）
    CREATE TABLE IF NOT EXISTS summaries (
        agent_name TEXT PRIMARY KEY,
        summary TEXT,
        updated_at REAL
    );

    -- 长期事实
    CREATE TABLE IF NOT EXISTS facts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_name TEXT NOT NULL,
        content TEXT NOT NULL,
        category TEXT DEFAULT 'general',
        importance INTEGER DEFAULT 1,
        created_at REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_facts_agent ON facts(agent_name);

    -- 情感状态
    CREATE TABLE IF NOT EXISTS emotions (
        agent_name TEXT PRIMARY KEY,
        value INTEGER DEFAULT 50,
        label TEXT DEFAULT 'neutral',
        reasons TEXT,
        updated_at REAL
    );

    -- 内心想法
    CREATE TABLE IF NOT EXISTS thoughts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_name TEXT NOT NULL,
        content TEXT NOT NULL,
        context TEXT,
        created_at REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_thoughts_agent ON thoughts(agent_name);

    -- 人际关系印象
    CREATE TABLE IF NOT EXISTS impressions (
        agent_name TEXT NOT NULL,
        target_name TEXT NOT NULL,
        impression TEXT,
        sentiment INTEGER DEFAULT 0,
        updated_at REAL,
        PRIMARY KEY (agent_name, target_name)
    );

    -- 事件记录
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_name TEXT NOT NULL,
        event_type TEXT,
        description TEXT,
        participants TEXT,
        location TEXT,
        created_at REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_events_agent ON events(agent_name);
    """

    def __init__(self, agent_name, db_path=None, limit=20):
        self.agent_name = agent_name
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), "memory.db")
        self.limit = limit
        self.lock = threading.Lock()
        self._conn = None
        self._init_db()

    def _get_conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript(self.SCHEMA)
        conn.commit()

    def add_message(self, content, msg_type="action"):
        """添加一条消息到记忆"""
        with self.lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO messages (agent_name, timestamp, content, msg_type) VALUES (?, ?, ?, ?)",
                (self.agent_name, time.time(), content, msg_type)
            )
            conn.commit()
            self._maybe_compress()

    def add_fact(self, content, category="general", importance=1):
        """添加一条长期事实"""
        with self.lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO facts (agent_name, content, category, importance, created_at) VALUES (?, ?, ?, ?, ?)",
                (self.agent_name, content, category, importance, time.time())
            )
            conn.commit()

    def add_thought(self, content, context=""):
        """添加一条内心想法"""
        with self.lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO thoughts (agent_name, content, context, created_at) VALUES (?, ?, ?, ?)",
                (self.agent_name, content, context, time.time())
            )
            conn.commit()

    def add_event(self, event_type, description, participants="", location=""):
        """添加一条事件记录"""
        with self.lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO events (agent_name, event_type, description, participants, location, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (self.agent_name, event_type, description, participants, location, time.time())
            )
            conn.commit()

    def update_impression(self, target_name, impression, sentiment=0):
        """更新对某人的印象"""
        with self.lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO impressions (agent_name, target_name, impression, sentiment, updated_at) 
                   VALUES (?, ?, ?, ?, ?)""",
                (self.agent_name, target_name, impression, sentiment, time.time())
            )
            conn.commit()

    def update_emotion(self, value, label, reasons=""):
        """更新情绪状态"""
        with self.lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO emotions (agent_name, value, label, reasons, updated_at) 
                   VALUES (?, ?, ?, ?, ?)""",
                (self.agent_name, value, label, json.dumps(reasons, ensure_ascii=False), time.time())
            )
            conn.commit()

    def get_recent_messages(self, limit=None):
        """获取最近的消息"""
        limit = limit or self.limit
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT content, msg_type, timestamp FROM messages WHERE agent_name = ? AND compressed = 0 ORDER BY timestamp DESC LIMIT ?",
            (self.agent_name, limit)
        ).fetchall()
        return [{"content": r[0], "type": r[1], "time": r[2]} for r in reversed(rows)]

    def get_facts(self, limit=10):
        """获取长期事实"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT content, category, importance FROM facts WHERE agent_name = ? ORDER BY importance DESC, created_at DESC LIMIT ?",
            (self.agent_name, limit)
        ).fetchall()
        return [{"content": r[0], "category": r[1], "importance": r[2]} for r in rows]

    def get_impressions(self):
        """获取所有印象"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT target_name, impression, sentiment FROM impressions WHERE agent_name = ?",
            (self.agent_name,)
        ).fetchall()
        return {r[0]: {"impression": r[1], "sentiment": r[2]} for r in rows}

    def get_emotion(self):
        """获取当前情绪状态"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT value, label, reasons FROM emotions WHERE agent_name = ?",
            (self.agent_name,)
        ).fetchone()
        if row:
            return {
                "value": row[0],
                "label": row[1],
                "reasons": json.loads(row[2]) if row[2] else []
            }
        return {"value": 50, "label": "neutral", "reasons": []}

    def get_summary(self):
        """获取记忆摘要"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT summary FROM summaries WHERE agent_name = ?",
            (self.agent_name,)
        ).fetchone()
        return row[0] if row else ""

    def get_context(self, max_tokens=500):
        """获取完整的记忆上下文"""
        parts = []
        
        # 摘要
        summary = self.get_summary()
        if summary:
            parts.append(f"【记忆摘要】{summary}")
        
        # 情绪
        emotion = self.get_emotion()
        if emotion["label"] != "neutral":
            parts.append(f"【当前情绪】{emotion['label']}（{emotion['value']}/100）")
        
        # 长期事实
        facts = self.get_facts(5)
        if facts:
            facts_text = "；".join([f["content"] for f in facts])
            parts.append(f"【重要事实】{facts_text}")
        
        # 印象
        impressions = self.get_impressions()
        if impressions:
            imp_parts = []
            for name, data in list(impressions.items())[:5]:
                imp_parts.append(f"对{name}：{data['impression']}")
            parts.append(f"【对他人的印象】{'；'.join(imp_parts)}")
        
        # 最近消息
        recent = self.get_recent_messages(10)
        if recent:
            recent_text = "\n".join([f"- {m['content']}" for m in recent[-5:]])
            parts.append(f"【最近经历】\n{recent_text}")
        
        return "\n\n".join(parts)

    def _maybe_compress(self):
        """压缩旧消息（保留最近N条，其余转为摘要）"""
        conn = self._get_conn()
        count = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE agent_name = ? AND compressed = 0",
            (self.agent_name,)
        ).fetchone()[0]
        
        if count <= self.limit * 2:
            return
        
        # 获取需要压缩的消息
        old_messages = conn.execute(
            "SELECT id, content FROM messages WHERE agent_name = ? AND compressed = 0 ORDER BY timestamp ASC LIMIT ?",
            (self.agent_name, count - self.limit)
        ).fetchall()
        
        if not old_messages:
            return
        
        # 生成摘要（简单拼接，实际可以用LLM压缩）
        summary_parts = [m[1][:50] for m in old_messages[:10]]
        new_summary = "；".join(summary_parts)
        
        # 更新摘要
        old_summary = self.get_summary()
        combined = f"{old_summary}；{new_summary}" if old_summary else new_summary
        
        conn.execute(
            """INSERT OR REPLACE INTO summaries (agent_name, summary, updated_at) 
               VALUES (?, ?, ?)""",
            (self.agent_name, combined[-1000:], time.time())  # 保留最后1000字符
        )
        
        # 标记为已压缩
        ids = [m[0] for m in old_messages]
        placeholders = ",".join(["?"] * len(ids))
        conn.execute(
            f"UPDATE messages SET compressed = 1 WHERE id IN ({placeholders})",
            ids
        )
        conn.commit()

    def export_for_prompt(self):
        """导出用于prompt的记忆内容"""
        return self.get_context()


# 测试代码
if __name__ == "__main__":
    memory = EnhancedMemory("测试角色")
    memory.add_message("今天天气不错")
    memory.add_fact("喜欢晴天")
    memory.update_emotion(70, "happy", ["天气好"])
    memory.update_impression("林阳", "开朗的家伙", 60)
    
    print(memory.get_context())
