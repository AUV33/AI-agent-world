# -*- coding: utf-8 -*-
"""bond_system.py - 关系纽带系统（参考水濑祈 bond/focus 分层认知）

水濑祈设计核心：角色之间要"具体看见一个人"，而非对谁都一样。
本系统为每对角色维护一条关系：强度(strength 0~1) + 简短叙事(note)。
- 强度随 IM 往来增长、随时间轻微衰减；
- 行动时把"你与他人的关系"注入上下文，让角色带着关系底色去反应；
- 幂等 ensure，重复加载不会覆盖已有关系值。

存储复用共享 memory.db 的 bonds 表，零额外 API（沿用水濑祈"轻量优先"原则）。
"""
import sqlite3, time, os
from datetime import datetime

PROJ = os.path.dirname(os.path.abspath(__file__))


class BondSystem:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.join(PROJ, "memory.db")
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "CREATE TABLE IF NOT EXISTS bonds ("
            "agent_a TEXT NOT NULL, agent_b TEXT NOT NULL, "
            "strength REAL DEFAULT 0.3, note TEXT DEFAULT '', "
            "updated_at REAL, updated_str TEXT, "
            "PRIMARY KEY (agent_a, agent_b))"
        )
        conn.commit()
        conn.close()

    def set_db_path(self, db_path):
        """把关系库换到另一个文件（一次运行一个 run_dir 时用），并保证表存在。

        实验隔离需要：两次运行若共用 memory.db，上一轮的羁绊会污染这一轮。
        """
        self.db_path = db_path
        self._init_db()
        return self.db_path

    def _key(self, a, b):
        return (a, b) if a <= b else (b, a)

    def ensure(self, a, b, init_strength=0.3):
        """确保关系行存在（幂等，已存在不覆盖）。"""
        a_k, b_k = self._key(a, b)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT 1 FROM bonds WHERE agent_a=? AND agent_b=?", (a_k, b_k))
        if not c.fetchone():
            c.execute(
                "INSERT INTO bonds (agent_a,agent_b,strength,note,updated_at,updated_str) VALUES (?,?,?,?,?,?)",
                (a_k, b_k, init_strength, "", time.time(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
        conn.close()

    def update(self, a, b, delta, note=None):
        a_k, b_k = self._key(a, b)
        self.ensure(a, b)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT strength,note FROM bonds WHERE agent_a=? AND agent_b=?", (a_k, b_k))
        strength, old_note = c.fetchone()
        new_strength = max(0.0, min(1.0, strength + delta))
        new_note = note if note else old_note
        c.execute(
            "UPDATE bonds SET strength=?,note=?,updated_at=?,updated_str=? WHERE agent_a=? AND agent_b=?",
            (new_strength, new_note, time.time(), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), a_k, b_k),
        )
        conn.commit()
        conn.close()
        return new_strength

    def get(self, a, b):
        a_k, b_k = self._key(a, b)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT strength,note FROM bonds WHERE agent_a=? AND agent_b=?", (a_k, b_k))
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        return {"strength": row[0], "note": row[1]}

    def get_context(self, agent, limit=6):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "SELECT agent_a,agent_b,strength,note FROM bonds WHERE agent_a=? OR agent_b=? ORDER BY strength DESC",
            (agent, agent),
        )
        rows = c.fetchall()
        conn.close()
        parts = []
        for a_k, b_k, strength, note in rows:
            if strength < 0.05:
                continue
            other = b_k if a_k == agent else a_k
            label = (
                "亲密" if strength >= 0.7 else
                "熟悉" if strength >= 0.45 else
                "认识" if strength >= 0.25 else
                "疏远"
            )
            line = f"与{other}：{label}（{strength:.2f}）"
            if note:
                line += f"——{note}"
            parts.append(line)
            if len(parts) >= limit:
                break
        return "；".join(parts) if parts else "（暂无明显关系）"

    def decay_all(self, amount=None):
        """按天轻微衰减所有关系强度（由调用方按时间推进触发）。"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        amt = amount if amount is not None else 0.008
        c.execute("UPDATE bonds SET strength=MAX(0.0, strength-?)", (amt,))
        conn.commit()
        conn.close()


bonds = BondSystem()
