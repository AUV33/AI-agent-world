# -*- coding: utf-8 -*-
"""event_bus.py - 轻量事件总线（对标 OASIS Information Channel）。

把 IM / 当面会话(f2f) / 场景移动 建模为"作用于世界的事件"，由总线统一发布。
同场景观察者经 World.perceive（含 get_joinable_context）看到相关事件并自行决策，
而非被直接拉钟——保证"环境中介"原则：agent 间只经环境传播。
"""
class EventBus:
    def __init__(self):
        # handlers: list of (predicate(event)->bool, handler(event))
        self._handlers = []
        self._log = []  # 已发布事件（便于调试/回放）

    def subscribe(self, predicate, handler):
        """注册处理器：当 predicate(event) 为真时调用 handler(event)。"""
        self._handlers.append((predicate, handler))

    def publish(self, event):
        """发布一个事件（dict，至少含 'kind' 字段），同步即时派发。"""
        self._log.append(event)
        for predicate, handler in self._handlers:
            try:
                if predicate(event):
                    handler(event)
            except Exception as e:  # 单处理器异常不影响整体
                print(f"[WARN] EventBus handler 失败：{type(e).__name__}: {e}")

    def events_of_kind(self, kind):
        return [e for e in self._log if e.get('kind') == kind]

    def clear(self):
        self._log.clear()
