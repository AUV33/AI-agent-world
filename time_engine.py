# -*- coding: utf-8 -*-
"""time_engine.py - 独立时间引擎（对标 OASIS Time Engine + Generative Agents 中心循环）。

职责单一：只管"推进模拟时间 + 派发下一个最早该行动的角色"，不含任何业务
（日志/反思/IM/闲聊/场景更新都在 continuous_runner 主循环里）。每个角色拥有
独立时钟，调度天然交错，避免"你动一下我动一下"的固定轮次。
"""
import random
import time
from datetime import timedelta


class TimeEngine:
    def __init__(self, agent_names, base_dt, speed, max_wait_real=2.0, start_jitter=(0, 10)):
        self.speed = speed                  # 每模拟分钟 = speed 真实秒
        self.max_wait_real = max_wait_real  # 单次真实等待上限（便于及时响应停止信号）
        self.base_dt = base_dt
        self.sim_now = base_dt
        # 每个角色独立时钟：下次行动时刻（起步错开，避免一哄而上）
        self.clocks = {name: base_dt + timedelta(minutes=random.uniform(*start_jitter))
                       for name in agent_names}

    def next(self):
        """返回 (name, due_dt)：当前最早该行动的角色，不推进 sim_now。"""
        name = min(self.clocks, key=lambda n: self.clocks[n])
        return name, self.clocks[name]

    def advance_to(self, due):
        """按速度缩放真实等待，并把 sim_now 推进到 due（单次不超过上限）。"""
        wait_real = (due - self.sim_now).total_seconds() / 60.0 * self.speed
        if wait_real > 0:
            time.sleep(min(wait_real, self.max_wait_real))
        self.sim_now = due

    def reschedule(self, name, dt_minutes):
        """排定该角色下一次行动（间隔随作息变化）。"""
        self.clocks[name] = self.sim_now + timedelta(minutes=dt_minutes)

    def elapsed_hours(self):
        """自基准时刻起经过的模拟小时数。"""
        return (self.sim_now - self.base_dt).total_seconds() / 3600.0
