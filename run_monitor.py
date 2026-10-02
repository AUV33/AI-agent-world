# -*- coding: utf-8 -*-
"""run_monitor.py - 连续运行监控插件（轻量、零依赖）。

在 continuous_runner.run() 主循环里挂一个 RunMonitor，逐轮记录：
  - 谁、何时（模拟时刻）、在哪个场景、干了什么、给谁发了 IM、真实耗时、是否异常
  - 事件总线事件（IM / f2f / 移动）
  - 全局反思成败
并把错误/异常落盘，便于后续排查问题（运行不会因单轮失败而整体崩，错误被记录）。

输出（默认 runs/，已在 .gitignore）：
  monitor_<run_id>.jsonl         每行一个事件/轮次记录（便于 grep / 聚合）
  monitor_<run_id>_summary.json 运行结束时的累计统计
"""
import os, time, json
from datetime import datetime

PROJ = os.path.dirname(os.path.abspath(__file__))


class RunMonitor:
    def __init__(self, run_id=None, out_dir=None):
        self.run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.out_dir = out_dir or os.path.join(PROJ, "runs")
        os.makedirs(self.out_dir, exist_ok=True)
        self.jsonl = os.path.join(self.out_dir, f"monitor_{self.run_id}.jsonl")
        self.summary_path = os.path.join(self.out_dir, f"monitor_{self.run_id}_summary.json")
        self.start_time = time.time()
        self.turn_count = 0
        self.error_count = 0
        self.im_count = 0
        self.f2f_count = 0
        self.move_count = 0
        self.total_turn_sec = 0.0
        self.per_agent = {}            # name -> {'turns','errors','ims'}
        self.errors = []               # 最近若干错误（含摘要）
        self._fh = open(self.jsonl, "a", encoding="utf-8")

    # ---------------- 记录接口 ----------------
    def _emit(self, rec):
        rec.setdefault("t", round(time.time() - self.start_time, 3))
        self._fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._fh.flush()

    def record_turn(self, name, time_label, scene, action, im_targets,
                    dt_real, dt_sim, ok=True, error=None):
        self.turn_count += 1
        self.total_turn_sec += dt_real
        a = self.per_agent.setdefault(name, {"turns": 0, "errors": 0, "ims": 0})
        a["turns"] += 1
        rec = {"type": "turn", "agent": name, "sim_time": time_label, "scene": scene,
               "action": (action or "")[:500], "im_targets": im_targets,
               "dt_real_s": round(dt_real, 3), "dt_sim_min": dt_sim, "ok": ok}
        if not ok:
            self.error_count += 1
            a["errors"] += 1
            self.errors.append({"agent": name, "sim_time": time_label, "error": str(error)[:300]})
            rec["error"] = str(error)[:300]
        for _t in im_targets:
            a["ims"] += 1
        self._emit(rec)

    def record_event(self, ev):
        """订阅 EventBus：记录 IM / f2f / 移动 事件。"""
        kind = ev.get("kind")
        if kind == "im":
            self.im_count += 1
        elif kind == "f2f":
            self.f2f_count += 1
        elif kind == "move":
            self.move_count += 1
        self._emit({"type": "event", "kind": kind,
                    "data": {k: v for k, v in ev.items() if k != "kind"}})

    def record_reflection(self, ok=True, error=None):
        rec = {"type": "reflection", "ok": ok}
        if not ok:
            self.error_count += 1
            self.errors.append({"phase": "reflection", "error": str(error)[:300]})
            rec["error"] = str(error)[:300]
        self._emit(rec)

    def record_error(self, phase, error):
        self.error_count += 1
        self.errors.append({"phase": phase, "error": str(error)[:300]})
        self._emit({"type": "error", "phase": phase, "error": str(error)[:300]})

    # ---------------- 汇总 ----------------
    def summary(self):
        elapsed = time.time() - self.start_time
        avg = (self.total_turn_sec / self.turn_count) if self.turn_count else 0
        return {
            "run_id": self.run_id,
            "elapsed_s": round(elapsed, 2),
            "turns": self.turn_count,
            "errors": self.error_count,
            "im": self.im_count,
            "f2f": self.f2f_count,
            "move": self.move_count,
            "avg_turn_s": round(avg, 3),
            "per_agent": self.per_agent,
            "recent_errors": self.errors[-10:],
        }

    def flush(self):
        try:
            self._fh.flush()
        except Exception:
            pass
        try:
            with open(self.summary_path, "w", encoding="utf-8") as f:
                json.dump(self.summary(), f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def close(self):
        try:
            self._fh.close()
        except Exception:
            pass

    def print_summary(self):
        s = self.summary()
        print("\n===== 运行监控摘要 =====")
        print(f"run_id={s['run_id']}  耗时={s['elapsed_s']}s  轮次={s['turns']}  "
              f"错误={s['errors']}  IM={s['im']}  f2f={s['f2f']}  移动={s['move']}  "
              f"平均轮耗时={s['avg_turn_s']}s")
        if s["recent_errors"]:
            print("最近错误：")
            for e in s["recent_errors"]:
                print("  -", e)
        print(f"详情见：{self.jsonl}")
        print("========================")
