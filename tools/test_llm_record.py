# -*- coding: utf-8 -*-
"""LLM 录放层回归守卫（纯本地、零 API、零联网）。

守什么
  ① off 模式完全不介入（行为与接入前一致）
  ② record：真调一次并落盘；同一 prompt 的第 N 次调用记成第 N 条
  ③ replay：只读落盘，**绝不联网**，且**不需要 API 密钥**
  ④ replay 未命中 ⇒ 抛错（拒绝偷偷联网）；要放行必须显式开 LLM_REPLAY_ALLOW_MISS
  ⑤ 键的稳定性：messages 里 dict 顺序不影响键；但换了端点（BASE_URL）必须换键
  ⑥ 配置了录制却没给目录 ⇒ 直接报错，不静默降级为 off

判据能红
  「replay 绝不联网」这条用一个"被调用即失败"的假网络来判：
  只要真发过一次请求就会抛 AssertionError，而不是静默通过。

跑法
  python tools/test_llm_record.py
"""
import os
import sys
import shutil

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)

import caller
import llm_record
from llm_record import Recorder, ReplayMiss

_TMP = os.path.join(PROJ, "_scratch", "rec_guard_%d" % os.getpid())
shutil.rmtree(_TMP, ignore_errors=True)
os.makedirs(_TMP, exist_ok=True)
LOG = os.path.join(_TMP, "llm_calls.jsonl")


class _FakeResp(object):
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._p


class _FakeNet(object):
    """假网络：按次序吐预设响应，并计数。"""

    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = 0

    def post(self, *a, **k):
        p = self.payloads[min(self.calls, len(self.payloads) - 1)]
        self.calls += 1
        return _FakeResp(p)


class _Bomb(object):
    """被调用即失败：用来证明 replay 绝不联网。"""

    def __init__(self):
        self.calls = 0

    def post(self, *a, **k):
        self.calls += 1
        raise AssertionError("replay 模式竟然联网了！")


def _resp(tag):
    return {"choices": [{"message": {"content": tag}}]}


def _ask(text, model="hy3"):
    return caller.call_model([{"role": "user", "content": text}], model=model)


def main():
    real_requests, real_key, real_retries = caller.requests, caller.API_KEY, caller.MAX_RETRIES
    caller.MAX_RETRIES = 1          # 守卫里不该有重试退避
    try:
        # ① off：完全不介入
        caller.RECORDER = Recorder(path=None, mode="off")
        caller.API_KEY = "test-key"
        caller.requests = _FakeNet([_resp("off-1")])
        out = _ask("off 模式")
        assert out["choices"][0]["message"]["content"] == "off-1"
        assert caller.requests.calls == 1, "off 模式应照常走网络"
        assert not os.path.exists(LOG), "off 模式不该写任何录放文件"
        assert caller.RECORDER.hits == 0 and caller.RECORDER.stored == 0
        print("[OK] off：不介入、不落盘（hits=0 stored=0）")

        # ② record：三次不同 prompt + 同一 prompt 两次（验次序）
        caller.RECORDER = Recorder(path=LOG, mode="record")
        caller.requests = _FakeNet([_resp("r-A"), _resp("r-B"), _resp("r-C1"), _resp("r-C2")])
        a = _ask("提示 A")
        b = _ask("提示 B")
        c1 = _ask("提示 C")
        c2 = _ask("提示 C")           # 同一 prompt，合法地得到不同回答
        assert [x["choices"][0]["message"]["content"] for x in (a, b, c1, c2)] == \
            ["r-A", "r-B", "r-C1", "r-C2"]
        assert caller.requests.calls == 4
        with open(LOG, encoding="utf-8") as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) == 4, "应落盘 4 条，实际 %d" % len(lines)
        print("[OK] record：4 次调用全部落盘（含同一 prompt 的两次）")

        # ③ replay：新进程语义（重新加载文件）、无密钥、假网络换成"炸弹"
        caller.RECORDER = Recorder(path=LOG, mode="replay")
        caller.API_KEY = ""            # ★ 证明 replay 不需要密钥
        bomb = _Bomb()
        caller.requests = bomb
        ra = _ask("提示 A")
        rb = _ask("提示 B")
        rc1 = _ask("提示 C")
        rc2 = _ask("提示 C")
        assert [x["choices"][0]["message"]["content"] for x in (ra, rb, rc1, rc2)] == \
            ["r-A", "r-B", "r-C1", "r-C2"], "回放结果与录制不一致（含同 prompt 的次序）"
        assert bomb.calls == 0, "replay 竟然联网了（%d 次）" % bomb.calls
        assert caller.RECORDER.hits == 4, "命中数应为 4，实际 %d" % caller.RECORDER.hits
        print("[OK] replay：无密钥、零联网，4 次全部命中且次序一致（炸弹 0 次）")

        # ④ 未命中 ⇒ 抛错
        try:
            _ask("没录过的提示")
            raise AssertionError("replay 未命中竟然没报错 ⇒ 会偷偷联网")
        except ReplayMiss as e:
            assert "未命中" in str(e)
        assert bomb.calls == 0, "未命中时就已经联网了"
        print("[OK] replay 未命中：抛 ReplayMiss（拒绝联网），炸弹仍为 0 次")

        # ④b 显式放行后才允许补录（auto 语义）
        caller.RECORDER = Recorder(path=LOG, mode="auto")
        caller.API_KEY = "test-key"
        caller.requests = _FakeNet([_resp("r-D")])
        d = _ask("提示 A")             # 命中
        e = _ask("提示 D")             # 未命中 ⇒ 联网补录
        assert d["choices"][0]["message"]["content"] == "r-A"
        assert e["choices"][0]["message"]["content"] == "r-D"
        assert caller.requests.calls == 1, "auto 模式命中时不该联网"
        with open(LOG, encoding="utf-8") as f:
            assert len([l for l in f if l.strip()]) == 5
        print("[OK] auto：命中走回放、未命中才联网并追加（网络只被调用 1 次）")

        # ⑤ 键的稳定性
        r = Recorder(path=LOG, mode="replay")
        base = {"model": "hy3", "temperature": 0.7, "stream": False,
                "messages": [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]}
        swapped = {"stream": False, "temperature": 0.7, "model": "hy3",
                   "messages": [{"content": "s", "role": "system"}, {"content": "u", "role": "user"}]}
        assert r.begin(base, extra="http://ep") == r.begin(swapped, extra="http://ep"), \
            "dict 顺序不该影响键"
        assert r.begin(base, extra="http://ep") != r.begin(base, extra="http://other"), \
            "换了端点必须换键（否则跨端点静默命中旧记录）"
        print("[OK] 键稳定性：dict 顺序无关，端点变化则键变化")

        # ⑥ 配置了录制却没给目录 ⇒ 报错，不静默降级
        try:
            Recorder.from_env({"LLM_RECORD_MODE": "record"})
            raise AssertionError("配置了 record 却没目录，竟然静默降级了")
        except RuntimeError as e:
            assert "LLM_RECORD_DIR" in str(e)
        assert Recorder.from_env({}).mode == "off", "没配置时应为 off"
        print("[OK] 配置守卫：record 缺目录即报错；未配置则为 off（不静默降级）")

        # ⑦ 坏行容错：半行/坏行不影响其余回放
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("{这不是合法 json\n")
        r2 = Recorder(path=LOG, mode="replay")
        caller.RECORDER = r2
        caller.requests = bomb
        assert _ask("提示 A")["choices"][0]["message"]["content"] == "r-A"
        assert bomb.calls == 0
        print("[OK] 坏行容错：文件里混入坏行，其余记录仍可正常回放")

        print("ALL PASS")
        return 0
    finally:
        caller.requests, caller.API_KEY, caller.MAX_RETRIES = real_requests, real_key, real_retries
        shutil.rmtree(_TMP, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
