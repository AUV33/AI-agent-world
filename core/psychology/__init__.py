# -*- coding: utf-8 -*-
r"""core/psychology · 本地心理引擎（移植自 D:\mizuse，去 person 耦合）。

提供：
  · event_parse.parse   —— 事件解释层（OCC 评价的输入闸门，防"把示好判成责备"）
  · appraisal.Appraisal —— OCC 评价 → 抑制池 S → 成本 C → 挫折 F → 阈限 θ → 爆发
                           纯本地、零 LLM、无随机源、完全可复现

设计原则（从 mizuse 搬来的准入门槛）：
  1. 框架零角色硬编码：性格差异来自角色 JSON 的 `psych` 字段，不写死在代码里。
  2. 决定性优于抽样：能用规则/数值算的，不用 LLM 抽样（可复现、可调试）。
  3. 先修尺子再谈效应：没有测量装置前，不声称"更真实"。

启用方式：在 enhanced_engine 每轮调用 Appraisal.on_message / on_express / render，
由开关 `PSYCHOLOGY_ENABLED` 控制（缺省关，逐字回退旧行为）。
"""
from .event_parse import parse as parse_event, has_any as event_has_any
from .appraisal import (
    Appraisal, appraise, emotion_from_appraisal, DEFAULTS_PERSONA,
    EMO_KIND_HOURS, set_input_lex, input_lex,
)

__all__ = [
    "parse_event", "event_has_any",
    "Appraisal", "appraise", "emotion_from_appraisal", "DEFAULTS_PERSONA",
    "EMO_KIND_HOURS", "set_input_lex", "input_lex",
]
