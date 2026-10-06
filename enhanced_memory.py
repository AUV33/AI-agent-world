# -*- coding: utf-8 -*-
"""enhanced_memory.py - Enhanced Memory System (SQLite persistent)"""
import sqlite3, os, time, re, math
from datetime import datetime

# 谣言种子模型阈值：belief∈[0,1]
RUMOR_PROMOTE = 0.6   # 跨过此线 → 长成真实印象（晋升进 impressions）
RUMOR_DEAD = 0.12     # 跌破此线 → 枯萎（不再提及）
RUMOR_DECAY = 0.96    # 每轮自然衰减（无人强化就慢慢淡）

# ★ 取用纪律用：背景/设定类。这类记忆重要度固定偏高（0.7），
#   若不加限流会把 15 个取用名额全占了，经历（行动 0.4 / 思考 0.3）一条都进不去。
BG_CATEGORIES = ("background", "fact")


class EnhancedMemory:
    def __init__(self, agent_name, db_path="memory.db", warmth_enabled=False, lambda_base=30, reflection_batch=8):
        self.agent_name = agent_name
        self.db_path = db_path
        self.warmth_enabled = warmth_enabled
        self.lambda_base = lambda_base
        self.reflection_batch = reflection_batch
        self._init_db()
        self._migrate()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        c.execute(
            "CREATE TABLE IF NOT EXISTS memories ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "agent_name TEXT NOT NULL, content TEXT NOT NULL, "
            "category TEXT DEFAULT 'general', importance REAL DEFAULT 0.5, "
            "created_at REAL, created_str TEXT, "
            "access_count INTEGER DEFAULT 0, last_accessed REAL, "
            "warmth REAL DEFAULT 0.5, reflected INTEGER DEFAULT 0, last_recalled REAL)"
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS impressions ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "agent_name TEXT NOT NULL, target_name TEXT NOT NULL, "
            "impression TEXT NOT NULL, updated_at REAL, updated_str TEXT)"
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS rumors ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "agent_name TEXT NOT NULL, source TEXT NOT NULL, subject TEXT NOT NULL, "
            "content TEXT NOT NULL, belief REAL DEFAULT 0.0, "
            "created_at REAL, created_str TEXT, last_recalled REAL, "
            "warmth REAL DEFAULT 0.5, status TEXT DEFAULT 'seed')"
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS interactions ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "agent_name TEXT NOT NULL, partner TEXT NOT NULL, "
            "direction TEXT NOT NULL, content TEXT NOT NULL, "
            "time_label TEXT, created_at REAL)"
        )
        conn.commit()
        conn.close()

    def _migrate(self):
        """为已存在的 memory.db 补上新增列（旧库兼容）。"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        c.execute("PRAGMA table_info(memories)")
        cols = {r[1] for r in c.fetchall()}
        for col, typ in (("warmth", "REAL DEFAULT 0.5"),
                         ("reflected", "INTEGER DEFAULT 0"),
                         ("last_recalled", "REAL")):
            if col not in cols:
                c.execute(f"ALTER TABLE memories ADD COLUMN {col} {typ}")
        # ★ 清历史遗留：background 类的重复行（只这一类——经历类出现重复是真实发生过的事，不动）
        dup = c.execute("SELECT count(*) - count(DISTINCT content) FROM memories "
                        "WHERE category='background' AND agent_name=?",
                        (self.agent_name,)).fetchone()[0]
        if dup:
            c.execute("DELETE FROM memories WHERE category='background' AND agent_name=? AND id NOT IN "
                      "(SELECT MIN(id) FROM memories WHERE category='background' AND agent_name=? "
                      "GROUP BY content)", (self.agent_name, self.agent_name))
            print("[记忆迁移] %s：清理 background 重复行 %d 条" % (self.agent_name, dup))
        conn.commit()
        conn.close()

    def add_fact(self, content, category="fact", importance=0.7, reflected=0, dedup=False):
        """写一条记忆；返回 True=写入了，False=因去重跳过。

        dedup=True 时，同角色 + 同类别 + 同内容已存在就跳过。
        ★ 背景设定类【必须】开：角色每次构造都会重写同一段背景，
          不去重会随运行次数线性叠加（实测 sagi 41 条 / 去重后 2 条），
          再叠加"取用即升温"就会永久霸占取用名额。
        """
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        if dedup:
            row = c.execute(
                "SELECT 1 FROM memories WHERE agent_name=? AND category=? AND content=? LIMIT 1",
                (self.agent_name, category, content)).fetchone()
            if row:
                conn.close()
                return False
        now = time.time()
        sql = ("INSERT INTO memories (agent_name,content,category,importance,created_at,created_str,last_accessed,warmth,reflected,last_recalled) "
               "VALUES (?,?,?,?,?,?,?,?,?,?)")
        c.execute(sql, (self.agent_name, content, category, importance, now,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), now, 0.5, reflected, now))
        conn.commit()
        conn.close()
        return True

    def add_message(self, content, msg_type="conversation"):
        self.add_fact(content, category=msg_type, importance=0.4)

    def add_thought(self, content, context=""):
        fc = f"[{context}] {content}" if context else content
        self.add_fact(fc, category="thought", importance=0.3)

    def update_impression(self, target_name, impression):
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        now = time.time()
        c.execute("SELECT id FROM impressions WHERE agent_name=? AND target_name=?", (self.agent_name, target_name))
        row = c.fetchone()
        if row:
            c.execute("UPDATE impressions SET impression=?,updated_at=?,updated_str=? WHERE id=?",
                      (impression, now, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), row[0]))
        else:
            c.execute("INSERT INTO impressions (agent_name,target_name,impression,updated_at,updated_str) VALUES (?,?,?,?,?)",
                      (self.agent_name, target_name, impression, now, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()

    def get_impressions(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        c.execute("SELECT target_name,impression,updated_str FROM impressions WHERE agent_name=? ORDER BY updated_at DESC", (self.agent_name,))
        r = {row[0]: {"impression": row[1], "updated_str": row[2]} for row in c.fetchall()}
        conn.close()
        return r

    def seed_impression(self, target_name, impression):
        """仅首次播种：若已存在对该 target 的印象（跨轮持久化所得），不覆盖。
        用于角色初始化，避免每次加载都用 JSON 初始印象抹掉之前轮次积累的关系记忆。"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        c.execute("SELECT id FROM impressions WHERE agent_name=? AND target_name=?", (self.agent_name, target_name))
        if c.fetchone() is None:
            c.execute("INSERT INTO impressions (agent_name,target_name,impression,updated_at,updated_str) VALUES (?,?,?,?,?)",
                      (self.agent_name, target_name, impression, time.time(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()

    def log_interaction(self, partner, direction, content, time_label=""):
        """记录一次往来（跨轮持久化）：direction 为 'sent' 或 'received'。"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        c.execute("INSERT INTO interactions (agent_name,partner,direction,content,time_label,created_at) VALUES (?,?,?,?,?,?)",
                  (self.agent_name, partner, direction, content, time_label, time.time()))
        conn.commit()
        conn.close()

    def get_interaction_history_with(self, partner, limit=4):
        """取与某人的近期往来（跨轮），用于让角色'记起上次'。"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        c.execute("SELECT direction,content,time_label FROM interactions WHERE agent_name=? AND partner=? ORDER BY created_at DESC LIMIT ?",
                  (self.agent_name, partner, limit))
        r = [{"direction": row[0], "content": row[1], "time_label": row[2]} for row in c.fetchall()]
        conn.close()
        return r

    def get_reputation(self):
        """别人眼中的自己：反查所有把本 agent 当作 target 的印象记录。"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        c.execute("SELECT agent_name,impression,updated_str FROM impressions WHERE target_name=? ORDER BY updated_at DESC", (self.agent_name,))
        r = {row[0]: {"impression": row[1], "updated_str": row[2]} for row in c.fetchall()}
        conn.close()
        return r

    # ---------- 谣言种子模型 ----------
    def add_rumor(self, source, subject, content, belief):
        """种下一颗闲话种子。belief 为听者当前采信度[0,1]。同 说者-被说者-内容 的已有种子取较高 belief 合并。
        若采信度已跨过晋升线（铁关系说的），直接长成真实印象；否则作为会衰减的种子落下。"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        now = time.time()
        c.execute("SELECT id,belief FROM rumors WHERE agent_name=? AND source=? AND subject=? AND content=? AND status='seed'",
                  (self.agent_name, source, subject, content))
        row = c.fetchone()
        if row:
            belief = max(row[1], belief)
            c.execute("UPDATE rumors SET belief=?,last_recalled=? WHERE id=?", (belief, now, row[0]))
            rid = row[0]
        else:
            c.execute(
                "INSERT INTO rumors (agent_name,source,subject,content,belief,created_at,created_str,last_recalled,warmth,status) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (self.agent_name, source, subject, content, belief, now,
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"), now, max(0.3, belief), 'seed'))
            rid = c.lastrowid
        conn.commit()
        conn.close()
        if belief >= RUMOR_PROMOTE:
            self.update_impression(subject, content)
            self._set_rumor_status(rid, 'promoted')
        return rid

    def _set_rumor_status(self, rid, status):
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        c.execute("UPDATE rumors SET status=? WHERE id=?", (status, rid))
        conn.commit()
        conn.close()

    def get_active_rumors(self, subject=None):
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        if subject:
            c.execute("SELECT id,source,subject,content,belief FROM rumors WHERE agent_name=? AND subject=? AND status='seed'",
                      (self.agent_name, subject))
        else:
            c.execute("SELECT id,source,subject,content,belief FROM rumors WHERE agent_name=? AND status='seed' ORDER BY belief DESC",
                      (self.agent_name,))
        r = [{"id": x[0], "source": x[1], "subject": x[2], "content": x[3], "belief": x[4]} for x in c.fetchall()]
        conn.close()
        return r

    def tick_rumors(self):
        """每轮演化：自然衰减；够信则长成真实印象，不够信则枯萎。返回本轮回晋升成印象的(被说者,内容)列表。"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        c.execute("SELECT id,source,subject,content,belief FROM rumors WHERE agent_name=? AND status='seed'", (self.agent_name,))
        rows = c.fetchall()
        now = time.time()
        promoted = []
        for id_, src, subj, content, belief in rows:
            belief = belief * RUMOR_DECAY
            if belief >= RUMOR_PROMOTE:
                c.execute("UPDATE rumors SET belief=?,status='promoted',last_recalled=? WHERE id=?", (belief, now, id_))
                promoted.append((subj, content))
            elif belief <= RUMOR_DEAD:
                c.execute("UPDATE rumors SET belief=?,status='dead',last_recalled=? WHERE id=?", (belief, now, id_))
            else:
                c.execute("UPDATE rumors SET belief=?,last_recalled=? WHERE id=?", (belief, now, id_))
        conn.commit()
        conn.close()
        for subj, content in promoted:
            self.update_impression(subj, content)
        return promoted

    def get_context(self, max_items=15):
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        c.execute("SELECT id,content,category,importance,warmth,last_recalled,created_at FROM memories WHERE agent_name=?", (self.agent_name,))
        rows = c.fetchall()
        conn.close()
        if not rows:
            return "(暂无记忆)"
        now = time.time()
        scored = []
        for id_, content, cat, imp, warmth, last_rec, created in rows:
            if self.warmth_enabled:
                base = last_rec or created or now
                days = max(0.0, (now - base) / 86400.0)
                lam = max(1.0, self.lambda_base * (0.5 + (warmth or 0.5)))
                # 艾宾浩斯式保留率：重温延缓遗忘；地板 0.15 保证不会彻底消失
                retention = 0.15 + 0.85 * math.exp(-days / lam)
                score = (imp or 0.5) * retention
            else:
                score = imp or 0.5
            scored.append((score, id_, content, cat))
        scored.sort(key=lambda x: -x[0])
        # ★ 取用纪律（两条，缺一不可）：
        #   ① 同内容只给一个名额——重复副本会挤占名额，且"取用即升温"会让它永久霸占；
        #   ② 背景/设定类限流（≤1/3 名额），给经历（行动/思考/反思）留位置。
        #   历史缺陷：15 个名额全被同一两段背景的重复副本占满，经历一条都进不去。
        bg_cap = max(1, max_items // 3)
        seen, top, bg_used, deferred = set(), [], 0, []
        for item in scored:
            content, cat = item[2], item[3]
            if content in seen:
                continue
            if cat in BG_CATEGORIES and bg_used >= bg_cap:
                deferred.append(item)          # 先让位给经历；名额没用满再补回来
                continue
            seen.add(content)
            if cat in BG_CATEGORIES:
                bg_used += 1
            top.append(item)
            if len(top) >= max_items:
                break
        for item in deferred:                   # 经历太少时补齐，不浪费名额
            if len(top) >= max_items:
                break
            if item[2] in seen:
                continue
            seen.add(item[2])
            top.append(item)
        # 重温即升温：把被取用的记忆最后接触时间刷新
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        c.executemany("UPDATE memories SET last_recalled=? WHERE id=?", [(now, r[1]) for r in top])
        conn.commit()
        conn.close()
        parts = []
        for score, id_, content, cat in top:
            if cat == "fact":
                parts.append(f"[事实] {content}")
            elif cat == "thought":
                parts.append(f"[思考] {content}")
            elif cat == "action":
                parts.append(f"[行动] {content}")
            elif cat == "reflection":
                parts.append(f"[反思] {content}")
            else:
                parts.append(content)
        return "\n".join(parts)

    def search(self, keyword, limit=10):
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        c.execute("SELECT content,category,created_str FROM memories WHERE agent_name=? AND content LIKE ? ORDER BY created_at DESC LIMIT ?",
                  (self.agent_name, "%" + keyword + "%", limit))
        r = [{"content": x[0], "category": x[1], "time": x[2]} for x in c.fetchall()]
        conn.close()
        return r

    def get_recent(self, limit=10):
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        c.execute("SELECT content,category,created_str FROM memories WHERE agent_name=? ORDER BY created_at DESC LIMIT ?", (self.agent_name, limit))
        r = [{"content": x[0], "category": x[1], "time": x[2]} for x in c.fetchall()]
        conn.close()
        return r

    def _content(self, rsp):
        try:
            return rsp['choices'][0]['message']['content'] or ''
        except Exception:
            return ''

    def run_reflection(self, desire_context=""):
        """周期性反思（参考水濑祈 reflections）：
        把近期未反思的经历提炼成一条反思，可能生成新的惦记(欲望)，
        并对照当前惦记诚实地判断『执念』(越想越放不下)与『放下』(认清没戏/懒得再想)。"""
        from caller import call_model
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        c.execute(
            "SELECT id,content,category FROM memories WHERE agent_name=? AND reflected=0 AND category!='reflection' "
            "ORDER BY created_at DESC LIMIT ?",
            (self.agent_name, self.reflection_batch),
        )
        rows = c.fetchall()
        conn.close()
        if len(rows) < 3:
            return None
        batch = "\n".join(f"- ({cat}) {content}" for _, content, cat in rows)
        desire_block = ""
        if desire_context:
            desire_block = (
                f"\n另外，你目前心里还惦记着这些（从你的人生里割舍出来的）：\n{desire_context}\n"
            )
        prompt = (
            f"你是{self.agent_name}。以下是你近期经历的一些事（可能是思考/行动/事实）：\n{batch}\n"
            f"{desire_block}\n"
            "请做四件事：\n"
            "1. 用一两句话提炼一条『反思』（你从中确认或学到了关于自己、他人或世界的什么，带一点情绪体温）。\n"
            "2. 列出你因此『新惦记/想要做的事』（0~2 条，具体可执行）。\n"
            "3. 对照你现在的惦记，诚实地判断『执念』：哪几样你越想越放不下、哪怕一直没成也不打算罢手"
            "（可写已有惦记的原话，或新的一句；没有就写 无）。\n"
            "4. 对照你现在的惦记，诚实地判断『放下』：哪几样你其实已经懒得再想、或认清了没戏，决定不再惦记"
            "（写已有惦记的原话；没有就写 无）。\n"
            "严格按以下格式输出，不要多余内容：\n"
            "反思：【你的反思】\n"
            "惦记：【事情一；事情二】  （没有写 惦记：【无】）\n"
            "执念：【原话一；原话二】  （没有写 执念：【无】）\n"
            "放下：【原话一；原话二】  （没有写 放下：【无】）"
        )
        text = self._content(call_model([{"role": "user", "content": prompt}], max_tokens=600))
        ref_m = re.search(r'反思\S*【(.+?)】', text, re.S)
        des_m = re.search(r'惦记\S*【(.+?)】', text, re.S)
        obs_m = re.search(r'执念\S*【(.+?)】', text, re.S)
        let_m = re.search(r'放下\S*【(.+?)】', text, re.S)
        reflection = ref_m.group(1).strip() if ref_m else ''
        desires_raw = des_m.group(1).strip() if des_m else ''
        obs_raw = obs_m.group(1).strip() if obs_m else ''
        let_raw = let_m.group(1).strip() if let_m else ''
        new_desires = []
        if desires_raw and desires_raw != '无':
            for line in re.split(r'[；;\n]', desires_raw):
                line = line.strip().lstrip('0123456789.、 -')
                if line:
                    new_desires.append(line)
        obsessions = []
        if obs_raw and obs_raw != '无':
            for line in re.split(r'[；;\n]', obs_raw):
                line = line.strip().lstrip('0123456789.、 -')
                if line:
                    obsessions.append(line)
        let_go = []
        if let_raw and let_raw != '无':
            for line in re.split(r'[；;\n]', let_raw):
                line = line.strip().lstrip('0123456789.、 -')
                if line:
                    let_go.append(line)
        conn = sqlite3.connect(self.db_path, timeout=10)
        c = conn.cursor()
        c.executemany("UPDATE memories SET reflected=1 WHERE id=?", [(r[0],) for r in rows])
        conn.commit()
        conn.close()
        # 关闭上一条连接后再开新连接，避免同时持有两连接触发 database is locked
        if reflection:
            self.add_fact(f"[反思] {reflection}", category="reflection", importance=0.85, reflected=1)
        return {"reflection": reflection, "desires": new_desires,
                "obsessions": obsessions, "let_go": let_go}