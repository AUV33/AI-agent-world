# -*- coding: utf-8 -*-
"""llm_record.py - LLM 调用的录制 / 回放层（零新依赖，纯标准库）

为什么要有这一层
  对照实验必须能「改判据、重放同一批回答」，也必须能在断网 / 零 API 下复跑。
  参考 VCR.py 的 cassette + record mode（once / new_episodes / none），其中
  最关键的语义是：**没录过的新请求直接报错**、**replay 保证不发任何新请求** ——
  这正是防「跑着跑着偷偷联网、接口换了还静默通过」的那道闸。

四种模式（环境变量 LLM_RECORD_MODE，或 set_mode() 显式设）
  off    完全不介入（默认；行为与接入前逐字节一致）
  record 真调一次并落盘（append-only jsonl）
  replay 只读落盘；**未命中即抛错，绝不联网**（要放行需显式 LLM_REPLAY_ALLOW_MISS=1）
  auto   命中则回放，未命中则真调并追加（= VCR 的 new_episodes）

键怎么算
  key = sha256(规范化 JSON(model/messages/temperature/stream/max_tokens))
  · 用 sort_keys ⇒ dict 顺序不影响键；
  · 同一个 prompt 的第 N 次调用取第 N 条记录 —— 因为同一 prompt 允许合法地产生不同回答，
    按出现次序回放才能真正逐字节复现。

⚠ 已知前提（别把它误当成 bug）
  回放命中的前提是 **prompt 逐字节相同**。而 prompt 由记忆 / 羁绊 / 心理状态拼出来，
  这些状态目前是跨运行累积的（DB 路径写死、World.reset 只清内存）⇒
  第二次运行往往会因为状态不同而「合法地」未命中。
  要真正可复跑，还必须同时做「一次运行一个 run_dir / 独立状态」。

配置
  LLM_RECORD_MODE = off | record | replay | auto
  LLM_RECORD_DIR  = 落盘目录（非 off 模式必填；缺了直接报错，不静默降级为 off）
  LLM_RECORD_FILE = 文件名（默认 llm_calls.jsonl）
"""
import io
import os
import json
import time
import hashlib

MODES = ("off", "record", "replay", "auto")
DEFAULT_FILE = "llm_calls.jsonl"


class ReplayMiss(RuntimeError):
    """replay 模式下没录到这一条 —— 默认直接失败，绝不联网。"""


def _key_of(data, extra=None):
    """规范化后取哈希：dict 顺序不影响结果。extra 用来把端点等环境也纳入键。"""
    payload = {
        "model": data.get("model"),
        "messages": data.get("messages"),
        "temperature": data.get("temperature"),
        "stream": data.get("stream"),
        "max_tokens": data.get("max_tokens"),
    }
    if extra:
        payload["_extra"] = extra
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _preview(data):
    """给未命中时排错用的一小段指纹（只存前 80 字）。"""
    try:
        msgs = data.get("messages") or []
        last = msgs[-1].get("content", "") if msgs else ""
        return (last or "")[:80].replace("\n", " ")
    except Exception:
        return ""


class Recorder(object):
    def __init__(self, path=None, mode="off"):
        if mode not in MODES:
            raise ValueError("未知录放模式 %r（可选 %s）" % (mode, "/".join(MODES)))
        if mode != "off" and not path:
            raise RuntimeError(
                "LLM_RECORD_MODE=%s 但没给 LLM_RECORD_DIR —— 拒绝静默降级为 off。" % mode)
        self.mode = mode
        self.path = path
        self._records = {}      # key -> [response, ...]
        self._cursor = {}       # key -> 已被回放到第几条
        self.hits = 0
        self.misses = 0
        self.stored = 0
        self.allow_miss = os.environ.get("LLM_REPLAY_ALLOW_MISS", "") in ("1", "true", "True")
        if self.mode != "off":
            self._load()

    # ——— 构造 ———
    @classmethod
    def from_env(cls, env=None):
        env = env if env is not None else os.environ
        mode = (env.get("LLM_RECORD_MODE") or "off").strip().lower()
        d = env.get("LLM_RECORD_DIR")
        fname = env.get("LLM_RECORD_FILE") or DEFAULT_FILE
        if mode == "off":
            return cls(path=None, mode="off")
        if not d:
            raise RuntimeError(
                "LLM_RECORD_MODE=%s 但未设置 LLM_RECORD_DIR —— 拒绝静默降级为 off。" % mode)
        os.makedirs(d, exist_ok=True)
        return cls(path=os.path.join(d, fname), mode=mode)

    def set_mode(self, mode, path=None):
        """运行中切换（测试与 CLI 用）。"""
        if mode not in MODES:
            raise ValueError("未知录放模式 %r" % mode)
        if mode != "off" and not (path or self.path):
            raise RuntimeError("切到 %s 需要 path" % mode)
        if path:
            self.path = path
        self.mode = mode
        if mode != "off":
            self._records, self._cursor = {}, {}
            self._load()
        return self

    @property
    def enabled(self):
        return self.mode != "off"

    # ——— 落盘 ———
    def _load(self):
        if not self.path or not os.path.isfile(self.path):
            return
        with io.open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue        # 半行/坏行跳过，不影响其余回放
                k = rec.get("key")
                if k:
                    self._records.setdefault(k, []).append(rec.get("response"))

    def _append(self, rec):
        with io.open(self.path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ——— 主流程 ———
    def begin(self, data, extra=None):
        """返回本条调用的 key；off 模式返回 None（完全不介入）。

        extra 用于把「端点」等环境信息纳入键：换了接口就不该静默命中旧记录。
        """
        return _key_of(data, extra=extra) if self.enabled else None

    def lookup(self, key):
        """命中则返回录下的响应并前进游标；未命中的返回 None。"""
        lst = self._records.get(key)
        i = self._cursor.get(key, 0)
        if lst and i < len(lst):
            self._cursor[key] = i + 1
            self.hits += 1
            return lst[i]
        self.misses += 1
        return None

    def on_miss(self, key, data):
        """replay 模式下的未命中处理：默认抛错（拒绝联网）。"""
        if self.mode == "replay" and not self.allow_miss:
            raise ReplayMiss(
                "录放层未命中（replay 模式拒绝联网）：key=%s… model=%s\n"
                "  该 prompt 前 80 字：%s\n"
                "  录放文件：%s\n"
                "  若确实要联网补录，请显式设 LLM_REPLAY_ALLOW_MISS=1（不建议在对照实验里开）。"
                % (key[:12], data.get("model"), _preview(data), self.path))

    def store(self, key, data, response):
        if not self.enabled:
            return
        lst = self._records.setdefault(key, [])
        lst.append(response)
        self._cursor[key] = len(lst)       # 同进程内下一次同 prompt 取新录的这条
        self.stored += 1
        try:
            total_chars = sum(len(m.get("content") or "") for m in (data.get("messages") or []))
        except Exception:
            total_chars = 0
        self._append({
            "seq": self.stored, "key": key, "model": data.get("model"),
            "temperature": data.get("temperature"), "max_tokens": data.get("max_tokens"),
            "n_msgs": len(data.get("messages") or []), "chars": total_chars,
            "preview": _preview(data), "ts": round(time.time(), 3),
            "response": response,
        })

    def stats(self):
        return {"mode": self.mode, "path": self.path, "hits": self.hits,
                "misses": self.misses, "stored": self.stored,
                "keys": len(self._records)}


# 全局单例：caller.call_model 直接用它
RECORDER = Recorder.from_env()
