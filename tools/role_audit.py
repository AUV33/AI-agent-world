# -*- coding: utf-8 -*-
"""role_audit.py - 逐角色审计：角色数据完整性 + 记忆取用 + 参数覆盖（只读，零 API）。

为什么要有这个工具
  「每个人都是主角」是硬要求，但缺字段的角色在日志里看不出来：
  persona_cognitive 为空时，内心脑提示里"你内里真实的样子：。"就是空的，双脑退化成单脑。
  这个工具把三件事摊平成一张表，让缺口和参数偏差一眼可见。

用法
  python tools/role_audit.py                        # 默认审 data/AuvAgents.json + memory.db
  python tools/role_audit.py --agents data/demo_agents.json
  python tools/role_audit.py --no-db                # 只看角色数据与参数，不碰记忆库

安全：所有 get_context 都在 memory.db 的【副本】上跑（它会更新 last_recalled），生产库不动。
"""
import os
import sys
import json
import shutil
import sqlite3
import argparse

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)

from core.psychology import DEFAULTS_PERSONA
from enhanced_memory import EnhancedMemory, BG_CATEGORIES
from enhanced_agent_factory import report_role_gaps

EXP_CATS = ("action", "thought", "reflection", "conversation", "memory_update")
PARAM_KEYS = ["k_sup", "k_cost", "kappa", "beta", "alpha", "theta0",
              "tau_F", "tau_scale", "tau_theta", "k_mood", "tau_mood"]
SWITCH_GROUPS = {
    "记忆": ["memory_warmth_enabled", "forget_lambda_base_days", "reflection_enabled",
             "reflection_interval_rounds", "reflection_batch_size", "longterm_memory_enabled",
             "interaction_history_limit", "interaction_context_pairs"],
    "欲望": ["desire_enabled", "desire_max_active", "desire_decay_rate",
             "desire_obsession_enabled", "desire_give_up_enabled"],
    "关系": ["bond_enabled", "bond_init_in_book", "bond_init_stranger", "bond_growth_per_im",
             "bond_growth_per_colocation", "bond_decay_per_day", "bond_context_pairs"],
    "社交": ["chitchat_enabled", "chitchat_prob", "gossip_enabled"],
    "出站": ["action_max_tokens", "humanity_rules_enabled"],
    "心理": ["psychology_enabled", "psychology_state_persist", "psychology_require_calibrated"],
}


def _picked_cats(db, name):
    """本轮真正拿到取用名额的条目类别（靠 last_recalled 痕迹，不按行数）。"""
    c = sqlite3.connect(db)
    ts = c.execute("select max(last_recalled) from memories where agent_name=?", (name,)).fetchone()[0]
    cats = [] if not ts else [r[0] for r in c.execute(
        "select category from memories where agent_name=? and last_recalled=?", (name, ts))]
    c.close()
    return cats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents", default=os.path.join(PROJ, "data", "AuvAgents.json"))
    ap.add_argument("--db", default=os.path.join(PROJ, "memory.db"))
    ap.add_argument("--no-db", action="store_true", help="不审记忆库（不碰 DB）")
    ap.add_argument("--max-items", type=int, default=15)
    a = ap.parse_args()

    data = json.load(open(a.agents, encoding="utf-8"))
    cfg = json.load(open(os.path.join(PROJ, "world_config.json"), encoding="utf-8"))
    routines = {}
    rp = os.path.join(PROJ, "data", "routines.json")
    if os.path.isfile(rp):
        routines = json.load(open(rp, encoding="utf-8"))

    print("=" * 100)
    print("一、角色数据完整性（--agents %s，%d 人）" % (os.path.basename(a.agents), len(data)))
    print("=" * 100)
    gaps = report_role_gaps(data)
    if not gaps:
        print("     ↑ 3 项字段全齐：persona_cognitive / life / memory")

    db = None
    if not a.no_db and os.path.isfile(a.db):
        scratch = os.path.join(PROJ, "_scratch")
        os.makedirs(scratch, exist_ok=True)
        db = os.path.join(scratch, "role_audit_copy.db")
        shutil.copyfile(a.db, db)

    if db:
        print()
        print("=" * 100)
        print("二、逐角色记忆与取用（在库副本上跑，生产库不动）")
        print("=" * 100)
        print("%-10s %-6s %-7s %5s %5s %6s %6s %6s" % (
            "角色", "psych", "routine", "记忆", "去重", "取用", "经历", "背景"))
        print("-" * 100)
        for d in data:
            n = d["name"]
            c = sqlite3.connect(db)
            total = c.execute("select count(*) from memories where agent_name=?", (n,)).fetchone()[0]
            dist = c.execute("select count(distinct content) from memories where agent_name=?", (n,)).fetchone()[0]
            c.close()
            m = EnhancedMemory(n, db_path=db, warmth_enabled=cfg.get("memory_warmth_enabled", False),
                               lambda_base=cfg.get("forget_lambda_base_days", 30))
            m.get_context(max_items=a.max_items)
            cats = _picked_cats(db, n)
            exp = sum(1 for x in cats if x in EXP_CATS)
            bg = sum(1 for x in cats if x in BG_CATEGORIES)
            print("%-10s %-6s %-7s %5d %5d %6d %6d %6d" % (
                n, "标定" if d.get("psych") else "默认",
                "有" if routines.get(n) else "无", total, dist, len(cats), exp, bg))
        print("取用=拿到 %d 个名额的条数；经历=其中 %s" % (a.max_items, "/".join(EXP_CATS)))
        os.remove(db)

    print()
    print("=" * 100)
    print("三、心理参数覆盖矩阵（* = 该角色显式覆盖）")
    print("=" * 100)
    print("%-10s %s" % ("参数", " ".join("%8s" % k for k in PARAM_KEYS)))
    print("%-10s %s" % ("默认", " ".join("%8s" % DEFAULTS_PERSONA[k] for k in PARAM_KEYS)))
    calib = [d for d in data if d.get("psych")]
    for d in calib:
        p = d["psych"]
        print("%-10s %s" % (d["name"], " ".join(
            "%7s%s" % (p.get(k, DEFAULTS_PERSONA[k]), "*" if k in p else " ") for k in PARAM_KEYS)))
    never = [k for k in PARAM_KEYS if not any(k in (d.get("psych") or {}) for d in calib)]
    print("已标定 %d/%d 人；从未被任何角色覆盖的参数：%s"
          % (len(calib), len(data), "、".join(never) if never else "(无)"))

    print()
    print("=" * 100)
    print("四、世界开关矩阵")
    print("=" * 100)
    for g, ks in SWITCH_GROUPS.items():
        print("[%s] %s" % (g, " ｜ ".join("%s=%s" % (k, cfg.get(k, "(缺)")) for k in ks)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
