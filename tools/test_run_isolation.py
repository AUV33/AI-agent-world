# -*- coding: utf-8 -*-
"""run_dir 实验隔离守卫（纯本地、零 API：全程 dry-run 桩）。

守什么
  ① 一次运行一个 run_dir：记忆/欲望/羁绊库、per-agent 状态、事件流、监控全落在里面，
     仓库根目录不被写入
  ② 同 seed 同配置跑两遍 ⇒ 两个 run_dir 的事件流【逐字节相同】、库行数相同（可复现）
  ③ 已存在且非空的 run_dir 再跑 ⇒ 直接报错（除非 resume）——防"以为在跑新实验，其实在续旧的"
  ④ resume 续跑 ⇒ 状态继续累积，且【历史事件不被抹掉】、原始 manifest 不被覆盖

判据能红
  ④ 的两条都是对照出来的：续跑后事件条数必须【大于】续跑前（不是相等、不是变小），
  且原始 manifest 的 created 必须还在 —— 若 event_log 回读失效，条数会比原来还少。

跑法
  python tools/test_run_isolation.py
"""
import os
import sys
import json
import shutil
import sqlite3

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)

from continuous_runner import run

AGENTS = os.path.join(PROJ, "data", "demo_agents.json")
ROOT = os.path.join(PROJ, "_scratch", "iso_guard_%d" % os.getpid())
TABLES = ("memories", "impressions", "rumors", "interactions", "bonds", "desires")


def _counts(db):
    c = sqlite3.connect(db)
    out = {}
    for t in TABLES:
        try:
            out[t] = c.execute("SELECT count(*) FROM " + t).fetchone()[0]
        except Exception:
            out[t] = None
    c.close()
    return out


def _lines(path):
    with open(path, encoding="utf-8") as f:
        return [l for l in f if l.strip()]


def _proj_agent_files():
    """仓库根目录下的 per-agent 状态文件（隔离后不该增加）。"""
    names = []
    for n in os.listdir(PROJ):
        if n.startswith(("life_", "emotion_", "thinking_", "psych_")) and n.endswith((".json", ".jsonl")):
            names.append(n)
    return set(names)


def _life_events(run_dir):
    """run_dir 里所有 life_*.json 的事件总数（dry-run 下唯一会写的 per-agent 状态）。"""
    total = 0
    for n in os.listdir(run_dir):
        if n.startswith("life_") and n.endswith(".json"):
            try:
                total += len(json.load(open(os.path.join(run_dir, n), encoding="utf-8")).get("events") or [])
            except Exception:
                pass
    return total


def main():
    try:
        shutil.rmtree(ROOT, ignore_errors=True)
        os.makedirs(ROOT)
        A = os.path.join(ROOT, "A")
        B = os.path.join(ROOT, "B")
        cfg = dict(base_time="2026-09-29 12:00", speed=0.0, max_turns=6,
                   dry_run=True, seed=7, reset_state=True)

        proj_before = _proj_agent_files()

        # ① 两次独立运行
        run(AGENTS, run_dir=A, **cfg)
        run(AGENTS, run_dir=B, **cfg)
        for d in (A, B):
            for f in ("memory.db", "events.jsonl", "manifest.json",
                      "record_by_scene.md", "record_by_person.md"):
                assert os.path.isfile(os.path.join(d, f)), "%s 里缺少 %s" % (d, f)
            assert any(n.startswith("monitor_") for n in os.listdir(d)), "%s 缺监控日志" % d
        assert _proj_agent_files() == proj_before, \
            "隔离没生效：仓库根目录多出了 per-agent 状态文件 %s" % (_proj_agent_files() - proj_before)
        print("[OK] 隔离：两次运行的产物全在各自 run_dir，仓库根目录零新增")

        # ② 可复现：同 seed 同配置 ⇒ 事件流逐字节相同、库行数相同
        ea, eb = _lines(os.path.join(A, "events.jsonl")), _lines(os.path.join(B, "events.jsonl"))
        assert ea, "事件流是空的，判据没意义"
        assert ea == eb, "同 seed 同配置的事件流不一致（%d 行 vs %d 行）" % (len(ea), len(eb))
        ca, cb = _counts(os.path.join(A, "memory.db")), _counts(os.path.join(B, "memory.db"))
        assert ca == cb, "两次运行的库行数不一致：%s vs %s" % (ca, cb)
        ma = json.load(open(os.path.join(A, "manifest.json"), encoding="utf-8"))
        assert ma["seed"] == 7 and ma["agents_sha256"], ma
        print("[OK] 可复现：%d 行事件逐字节相同；库行数一致 %s" % (len(ea), ca))

        # ③ 非空 run_dir 再跑 ⇒ 报错
        try:
            run(AGENTS, run_dir=A, **cfg)
            raise AssertionError("非空 run_dir 竟然允许直接再跑 ⇒ 会把旧实验当新实验")
        except RuntimeError as e:
            assert "已存在且非空" in str(e)
        print("[OK] 防误续：非空 run_dir 直接再跑会报错（除非 resume）")

        # ④ resume：状态继续累积 + 历史事件不被抹掉 + 原始 manifest 不被覆盖
        n_before = len(ea)
        first_before = ea[0]
        created_before = ma["created"]
        life_before = _life_events(A)
        assert life_before > 0, "run_dir 里没有 per-agent 状态（life_*.json）⇒ 隔离不完整"
        # 续跑到当天深夜：作息位置变了 ⇒ 必然写 per-agent 状态（dry-run 下也会写）
        run(AGENTS, run_dir=A, resume=True, base_time="2026-09-29 23:30", speed=0.0,
            max_turns=3, dry_run=True, seed=7, reset_state=True)
        ea2 = _lines(os.path.join(A, "events.jsonl"))
        ca2 = _counts(os.path.join(A, "memory.db"))
        life_after = _life_events(A)
        assert len(ea2) > n_before, \
            "续跑后事件条数没有增加（%d → %d）⇒ 历史被覆盖或没接着写" % (n_before, len(ea2))
        assert ea2[0] == first_before, "续跑把历史事件流的第一条改掉了 ⇒ 历史被抹"
        assert life_after > life_before, \
            "续跑后 per-agent 状态没在延续（life 事件 %d → %d）" % (life_before, life_after)
        assert ca2["memories"] >= ca["memories"], \
            "续跑把记忆库清空了（%d → %d）" % (ca["memories"], ca2["memories"])
        ma2 = json.load(open(os.path.join(A, "manifest.json"), encoding="utf-8"))
        assert ma2["created"] == created_before, "续跑把原始 manifest 覆盖了"
        assert ma2.get("resumes") and len(ma2["resumes"]) == 1, ma2.get("resumes")
        print("[OK] 续跑：事件 %d→%d 行（历史首条未变）、per-agent 状态 %d→%d、manifest 追加 resumes 1 条"
              % (n_before, len(ea2), life_before, life_after))

        print("ALL PASS")
        return 0
    finally:
        shutil.rmtree(ROOT, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
