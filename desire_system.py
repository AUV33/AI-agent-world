# -*- coding: utf-8 -*-
"""desire_system.py - 欲望/未来惦记(focus)系统（参考水濑祈 desire/focus 分层，并强化"人味"）

设计理念（来自对"人"的观察）：
- 每个人都有自己独立的人生，先过好自己这一摊，再从人生里割舍出"惦记"。
- 惦记有轻重：精力有限，要紧的先顾，不急的先放一放（割舍）。
- 一直没成，也许就放弃了；但有些事越放不下越酿成执念，死也不罢手。
- 这才像人：不是一条永不掉线的待办清单，而是会权衡、会泄气、也会钻牛角尖。

每条欲望字段：
- content      内容
- strength     "热度/冲动"(0~1)，会随搁置衰减
- weight       "轻重"(0~1)，权衡时的优先级，基本稳定
- life_anchor 这条惦记从哪段人生里割出来（学业/人际/自我/前途…）
- obsession    是否执念(0/1)：放不下，强度不衰减，不会放弃
- attempts     尝试次数
- failures     连续失败次数
- since_progress 距上次有进展的轮数（用来判断是否"一直没成"）
- done/given_up 完成 / 放弃
存储复用共享 memory.db 的 desires 表，零额外 API；旧库自动迁移新列。
"""
import sqlite3, time, os, re, json
from datetime import datetime

PROJ = os.path.dirname(os.path.abspath(__file__))

# 自读配置，避免与 engine 形成循环依赖
try:
    with open(os.path.join(PROJ, "world_config.json"), "r", encoding="utf-8") as _f:
        _CFG = json.load(_f)
except Exception:
    _CFG = {}
GIVEUP_ENABLED = _CFG.get("desire_give_up_enabled", True)
GIVEUP_ROUNDS = _CFG.get("desire_give_up_rounds", 8)      # 连续多少轮没进展 → 可能放弃
DECAY = _CFG.get("desire_decay_rate", 0.04)               # 每轮搁置的强度衰减
OBSESSION_ENABLED = _CFG.get("desire_obsession_enabled", True)
OBSESSION_ROUNDS = _CFG.get("desire_obsession_rounds", 5) # 重要的事搁多久开始酿成执念
OBSESSION_WEIGHT = _CFG.get("desire_obsession_weight", 0.85)  # 多"要紧"才算可能成执念


class DesireSystem:
    def __init__(self, agent_name, db_path=None):
        self.agent_name = agent_name
        self.db_path = db_path or os.path.join(PROJ, "memory.db")
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        c.execute(
            "CREATE TABLE IF NOT EXISTS desires ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "agent_name TEXT NOT NULL, content TEXT NOT NULL, "
            "strength REAL DEFAULT 0.6, done INTEGER DEFAULT 0, "
            "created_at REAL, created_str TEXT)"
        )
        # 迁移：旧库补新列（带 DEFAULT 时 SQLite 会自动回填已有行）
        cols = {r[1] for r in c.execute("PRAGMA table_info(desires)").fetchall()}
        for col, ddl in [
            ("weight", "REAL DEFAULT 0.6"),
            ("life_anchor", "TEXT DEFAULT ''"),
            ("obsession", "INTEGER DEFAULT 0"),
            ("attempts", "INTEGER DEFAULT 0"),
            ("failures", "INTEGER DEFAULT 0"),
            ("since_progress", "INTEGER DEFAULT 0"),
            ("given_up", "INTEGER DEFAULT 0"),
        ]:
            if col not in cols:
                c.execute(f"ALTER TABLE desires ADD COLUMN {col} {ddl}")
        conn.commit()
        conn.close()

    # ---------- 写入 ----------
    def add(self, content, strength=0.6, weight=None, life_anchor="", obsession=False):
        # 支持直接传 dict（来自角色配置）：{"content":..., "weight":..., "life_anchor":..., "obsession":...}
        if isinstance(content, dict):
            d = content
            content = d.get("content", "")
            strength = float(d.get("strength", strength))
            weight = d.get("weight", weight)
            life_anchor = d.get("life_anchor", life_anchor)
            obsession = bool(d.get("obsession", obsession))
        content = (content or "").strip()
        if not content:
            return
        if weight is None:
            weight = strength
        weight = float(weight)
        obsession = 1 if obsession else 0
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        # 防重：已存在相同/包含关系的活跃欲望则跳过，避免反思周期反复堆积近义欲望
        c.execute("SELECT content FROM desires WHERE agent_name=? AND done=0 AND given_up=0",
                  (self.agent_name,))
        existing = [r[0] for r in c.fetchall()]
        for ex in existing:
            if content in ex or ex in content:
                conn.close()
                return
        now = time.time()
        c.execute(
            "INSERT INTO desires "
            "(agent_name,content,strength,weight,life_anchor,obsession,done,created_at,created_str) "
            "VALUES (?,?,?,?,?,?,0,?,?)",
            (self.agent_name, content, strength, weight, life_anchor or "", obsession,
             now, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        conn.close()

    def mark_done(self, content):
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        c.execute(
            "UPDATE desires SET done=1, given_up=0 WHERE agent_name=? AND content=?",
            (self.agent_name, content),
        )
        conn.commit()
        conn.close()

    def promote_obsession(self, content):
        """主动把某条惦记升为执念（反思或剧情触发）。支持语义匹配（原话/包含）。"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        c.execute("SELECT content FROM desires WHERE agent_name=? AND done=0 AND given_up=0",
                  (self.agent_name,))
        active = [r[0] for r in c.fetchall()]
        target = None
        for ex in active:
            if content == ex or content in ex or ex in content:
                target = ex
                break
        if target:
            c.execute("UPDATE desires SET obsession=1 WHERE agent_name=? AND content=?",
                      (self.agent_name, target))
        conn.commit()
        conn.close()
        return target is not None

    def give_up(self, content):
        """主动放下某条惦记（反思触发）。执念不会被放下；返回是否真的放下了。"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        c.execute("SELECT content,obsession FROM desires WHERE agent_name=? AND done=0 AND given_up=0",
                  (self.agent_name,))
        active = c.fetchall()
        target = None
        target_obs = 0
        for ex, obs in active:
            if content == ex or content in ex or ex in content:
                target = ex
                target_obs = obs
                break
        acted = False
        if target and not target_obs:
            c.execute("UPDATE desires SET given_up=1 WHERE agent_name=? AND content=?",
                      (self.agent_name, target))
            acted = True
        conn.commit()
        conn.close()
        return acted

    # ---------- 读取 ----------
    def get_active(self, limit=4):
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        c.execute(
            "SELECT id,content,COALESCE(weight,strength) AS weight,strength,life_anchor,obsession "
            "FROM desires WHERE agent_name=? AND done=0 AND given_up=0 "
            "ORDER BY weight DESC, strength DESC LIMIT ?",
            (self.agent_name, limit),
        )
        rows = c.fetchall()
        conn.close()
        return [{"id": r[0], "content": r[1], "weight": r[2], "strength": r[3],
                 "life_anchor": r[4], "obsession": bool(r[5])} for r in rows]

    def get_prioritized(self, limit=4):
        """今天先顾的（最要紧）。"""
        return self.get_active(limit)

    def get_sacrificed(self, limit=4):
        """先放一放 / 已搁置一阵的（轻重靠后、或很久没进展）。"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        c.execute(
            "SELECT id,content,COALESCE(weight,strength) AS weight,strength,life_anchor,obsession,"
            "since_progress FROM desires WHERE agent_name=? AND done=0 AND given_up=0 "
            "ORDER BY weight ASC, since_progress DESC LIMIT ?",
            (self.agent_name, limit),
        )
        rows = c.fetchall()
        conn.close()
        return [{"id": r[0], "content": r[1], "weight": r[2], "strength": r[3],
                 "life_anchor": r[4], "obsession": bool(r[5]), "since_progress": r[6]} for r in rows]

    def get_obsessions(self, limit=4):
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        c.execute(
            "SELECT id,content,COALESCE(weight,strength) AS weight,strength,life_anchor "
            "FROM desires WHERE agent_name=? AND done=0 AND given_up=0 AND obsession=1 "
            "ORDER BY weight DESC LIMIT ?",
            (self.agent_name, limit),
        )
        rows = c.fetchall()
        conn.close()
        return [{"id": r[0], "content": r[1], "weight": r[2], "strength": r[3],
                 "life_anchor": r[4]} for r in rows]

    def count_active(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM desires WHERE agent_name=? AND done=0 AND given_up=0",
                  (self.agent_name,))
        n = c.fetchone()[0]
        conn.close()
        return n

    def count_given_up(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM desires WHERE agent_name=? AND given_up=1",
                  (self.agent_name,))
        n = c.fetchone()[0]
        conn.close()
        return n

    # ---------- 进度与每轮演化 ----------
    @staticmethod
    def _search_key(content):
        """从惦记里取一个用于匹配行动文本的关键片段。"""
        c = (content or "").strip()
        c = re.sub(r'^(想|要|希望|打算|计划|准备|想跟|想让|想给|想约|想确认|想搞清楚|想拉|想考|想把|想对|想和|想与|想见|想请|想叫)',
                  '', c)
        return c[:6] if len(c) >= 3 else ""

    def note_progress_from_text(self, text):
        """根据本轮行动文本，判断角色是否朝某条惦记迈了一步；是则回写进度。"""
        text = text or ""
        for d in self.get_active(20):
            key = self._search_key(d["content"])
            if key and key in text:
                self._bump(d["id"])

    def _bump(self, did):
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        c.execute(
            "UPDATE desires SET since_progress=0, failures=0, attempts=attempts+1, "
            "strength=MIN(1.0, strength+0.05) WHERE id=?",
            (did,),
        )
        conn.commit()
        conn.close()

    def tick(self, dt_minutes=60):
        """推进'搁置时长'，处理衰减 / 放弃 / 酿成执念。返回变动说明列表。
        dt_minutes：距上次推进经过的模拟分钟数（默认 60 = 原每轮语义）。
        所有演化量按 dt_minutes/60 缩放，连续时间运行时传真实间隔即可，
        回合制(run_step)传 60 时行为与原版完全一致。"""
        hrs = max(0.0, dt_minutes) / 60.0
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        rows = c.execute(
            "SELECT id,content,COALESCE(weight,strength) AS weight,obsession,since_progress,strength "
            "FROM desires WHERE agent_name=? AND done=0 AND given_up=0",
            (self.agent_name,),
        ).fetchall()
        changes = []
        for did, content, weight, obsession, sp, strength in rows:
            new_sp = sp + hrs
            if obsession:
                # 执念：放不下，强度不衰减，反而因憋着更顽固
                new_strength = min(1.0, strength + 0.01 * hrs)
                c.execute("UPDATE desires SET since_progress=?,strength=? WHERE id=?",
                          (new_sp, new_strength, did))
                continue
            new_strength = max(0.05, strength - DECAY * hrs)
            # 一直没成，越要紧越可能酿成执念
            if OBSESSION_ENABLED and weight >= OBSESSION_WEIGHT and new_sp >= OBSESSION_ROUNDS:
                c.execute("UPDATE desires SET obsession=1, since_progress=? WHERE id=?", (new_sp, did))
                changes.append(f"惦记酿成执念：{content}")
                continue
            # 一直没成，也许就放弃了
            if GIVEUP_ENABLED and new_sp >= GIVEUP_ROUNDS:
                c.execute("UPDATE desires SET given_up=1 WHERE id=?", (did,))
                changes.append(f"放弃了：{content}")
                continue
            c.execute("UPDATE desires SET since_progress=?,strength=? WHERE id=?",
                      (new_sp, new_strength, did))
        conn.commit()
        conn.close()
        return changes
