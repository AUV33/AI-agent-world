# -*- coding: utf-8 -*-
"""记忆取用纪律回归守卫（纯本地、零 API、不碰生产 memory.db）。

守两件事
  ① 背景记忆去重：角色每次构造都会重写同一段背景，不去重就随运行次数线性叠加。
  ② 取用纪律：15 个名额里【不许出现同内容重复】，且背景/设定类最多占 1/3，给经历留位置。
     历史缺陷（实测）：AUV 的 15 条取用结果去重后只剩 2 条，全是同一两段背景的副本，
     经历（行动/思考/反思）一条都进不去。

判据为什么能红
  末尾用【无纪律的老做法】取用同一批数据，必须出现重复且背景超额；
  若老做法也满足判据，说明判据恒绿 = 等于没检查。

跑法
  python tools/test_memory_retrieval.py
"""
import os
import sys
import shutil
import sqlite3

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)

import enhanced_engine as ee
from enhanced_memory import EnhancedMemory, BG_CATEGORIES

_TMP = os.path.join(PROJ, "_scratch", "mem_guard_%d" % os.getpid())
shutil.rmtree(_TMP, ignore_errors=True)
os.makedirs(_TMP, exist_ok=True)
DB = os.path.join(_TMP, "memory.db")

# ——— 沙箱：别让守卫写进仓库的 memory.db / 思考日志 ———
_RealMemory = ee.EnhancedMemory
_RealLife = ee.LifeState
_RealEmotion = ee.EmotionSystem
_RealDesire = ee.DesireSystem


class _NullLogger(object):
    def __init__(self, *a, **k):
        pass

    def log(self, *a, **k):
        return None


ee.EnhancedMemory = lambda name, db_path=None, **kw: _RealMemory(name, db_path=DB, **kw)
ee.LifeState = lambda name, state_file=None, routine=None: _RealLife(
    name, state_file=os.path.join(_TMP, "life_%s.json" % name), routine=routine)
ee.EmotionSystem = lambda name, state_file=None: _RealEmotion(
    name, state_file=os.path.join(_TMP, "emotion_%s.json" % name))
ee.DesireSystem = lambda name, db_path=None: _RealDesire(name, db_path=DB)
ee.ThinkingLogger = _NullLogger
ee.PSYCH_STATE_DIR = _TMP


def _rows(agent, category=None):
    c = sqlite3.connect(DB)
    if category:
        r = c.execute("SELECT count(*) FROM memories WHERE agent_name=? AND category=?",
                      (agent, category)).fetchone()[0]
    else:
        r = c.execute("SELECT count(*) FROM memories WHERE agent_name=?", (agent,)).fetchone()[0]
    c.close()
    return r


def _raw_insert(agent, content, category, importance):
    c = sqlite3.connect(DB)
    c.execute("INSERT INTO memories (agent_name,content,category,importance,created_at,warmth,reflected) "
              "VALUES (?,?,?,?,0,0.5,0)", (agent, content, category, importance))
    c.commit()
    c.close()


def _old_top(scored, max_items):
    """无纪律的老做法：直接按分数取前 N（用于自检判据能红）。"""
    return scored[:max_items]


def main():
    try:
        # ① 插入去重：dedup=True 第二次应跳过；默认 dedup=False 保持旧行为（向后兼容）
        m = EnhancedMemory("去重测试", db_path=DB)
        assert m.add_fact("同一段背景", category="background", dedup=True) is True
        assert m.add_fact("同一段背景", category="background", dedup=True) is False, \
            "dedup=True 第二次仍写入 ⇒ 背景会随运行次数叠加"
        assert _rows("去重测试", "background") == 1
        m.add_fact("同一句话", category="action")
        m.add_fact("同一句话", category="action")
        assert _rows("去重测试", "action") == 2, "默认行为应保持旧语义（经历类允许重复）"
        print("[OK] 插入去重：dedup=True ⇒ background 1 条；默认 dedup=False ⇒ 经历类仍可重复")

        # ② 历史重复清理：老库里已有的 background 副本要收敛（经历类重复不动）
        AG = "历史库测试"
        for _ in range(8):
            _raw_insert(AG, "旧背景", "background", 0.7)
        for _ in range(3):
            _raw_insert(AG, "同一句经历", "action", 0.4)
        assert _rows(AG, "background") == 8
        EnhancedMemory(AG, db_path=DB)          # 构造即触发迁移
        assert _rows(AG, "background") == 1, "历史 background 重复没被清理：%d 条" % _rows(AG, "background")
        assert _rows(AG, "action") == 3, "经历类重复是真实发生过的，不该被删"
        print("[OK] 历史清理：background 8→1 条，action 3 条原样保留")

        # ③ 取用纪律：构造"背景重复且权重高、经历分散"的库，看 15 个名额怎么分
        A2 = "取用测试"
        c = sqlite3.connect(DB)
        rows = []
        for i in range(10):
            rows.append((A2, "背景甲", "background", 0.7))
        for i in range(10):
            rows.append((A2, "背景乙", "background", 0.7))
        for i in range(2):
            rows.append((A2, "反思%d" % i, "reflection", 0.85))
        for i in range(12):
            rows.append((A2, "行动%d" % i, "action", 0.4))
        for i in range(6):
            rows.append((A2, "思考%d" % i, "thought", 0.3))
        c.executemany("INSERT INTO memories (agent_name,content,category,importance,created_at,warmth,reflected) "
                      "VALUES (?,?,?,?,0,0.5,0)", rows)
        c.commit()
        c.close()

        m2 = EnhancedMemory(A2, db_path=DB)
        ctx = m2.get_context(max_items=15)
        lines = [l for l in ctx.split("\n") if l.strip()]
        bg = sum(1 for l in lines if "背景" in l)
        exp = sum(1 for l in lines if ("行动" in l or "思考" in l or "反思" in l))
        print("   取用结果：共 %d 条 ｜ 去重后 %d 条 ｜ 背景 %d 条 ｜ 经历 %d 条"
              % (len(lines), len(set(lines)), bg, exp))
        assert len(lines) == 15, "名额没用满：%d 条" % len(lines)
        assert len(set(lines)) == len(lines), \
            "取用结果里仍有同内容重复：%d 条里只有 %d 条不同" % (len(lines), len(set(lines)))
        assert bg <= max(1, 15 // 3), "背景类占了 %d 条，超过 1/3 限流" % bg
        assert exp >= 10, "经历只拿到 %d 条名额，背景仍在挤占" % exp
        print("[OK] 取用纪律：15 条全不重复，背景 %d 条（限流 ≤5），经历拿到 %d 条" % (bg, exp))

        # ④ 名额不浪费：经历很少时，被限流的背景要补回来
        A3 = "补齐测试"
        m3 = EnhancedMemory(A3, db_path=DB)
        m3.add_fact("唯一背景", category="background", dedup=True)
        m3.add_fact("唯一经历", category="action")
        lines3 = [l for l in m3.get_context(max_items=15).split("\n") if l.strip()]
        assert len(lines3) == 2, "只有 2 条记忆时不该凭空少给：%d" % len(lines3)
        print("[OK] 名额补齐：库里只有 2 条时输出 2 条（限流不导致名额浪费）")

        # ⑤ 能红自检：用无纪律的老做法取同一批数据，必须重复且背景超额
        now = 0.0
        scored = []
        for i in range(2):
            scored.append((0.85, 100 + i, "反思%d" % i, "reflection"))
        for i in range(10):
            scored.append((0.7, i, "背景甲", "background"))
        for i in range(10):
            scored.append((0.7, 10 + i, "背景乙", "background"))
        for i in range(12):
            scored.append((0.4, 20 + i, "行动%d" % i, "action"))
        for i in range(6):
            scored.append((0.3, 32 + i, "思考%d" % i, "thought"))
        old = _old_top(scored, 15)
        old_lines = [x[2] for x in old]
        old_bg = sum(1 for x in old if x[3] in BG_CATEGORIES)
        assert len(set(old_lines)) < len(old_lines), "老做法竟然也没重复 ⇒ 判据区分不了修没修"
        assert old_bg > max(1, 15 // 3), "老做法背景没超额 ⇒ 限流判据恒绿"
        print("[OK] 尺子自检：老做法取 15 条 → 去重后仅 %d 条、背景 %d 条 ⇒ 与修复后可区分"
              % (len(set(old_lines)), old_bg))

        # ⑥ 真实入口：构造两次 EnhancedAgent，背景记忆不得增加
        ee.agents.clear()
        ee.envs.env.clear()
        ee.msgCenter.paddingMsgList.clear()
        ee.PSYCHOLOGY_ENABLED = False
        ee.EnhancedAgent(name="端到端测试", persona="p", envName="咖啡馆", memory="同一段角色背景")
        ee.EnhancedAgent(name="端到端测试", persona="p", envName="咖啡馆", memory="同一段角色背景")
        assert _rows("端到端测试", "background") == 1, \
            "构造两次后 background=%d 条 ⇒ 又会随运行次数叠加" % _rows("端到端测试", "background")
        print("[OK] 真实入口：EnhancedAgent 构造两次，background 仍为 1 条")

        print("ALL PASS")
        return 0
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
