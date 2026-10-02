# AI Agent World

一个由 LLM 驱动的多智能体（AI Agent）自主模拟社会。每个角色拥有「内心思考」与「对外措辞」**双脑**，在共享世界（场景 / 即时通讯 / 环境）中自主行动、社交、记忆、产生情绪与欲望，并随时间自然演化。

> 本分支（`dev`）在 GitHub 原版（`sg-first/AI-agent-world`）基础上，整合了本地迭代的「增强版」成果，并重新规整了目录与计划。

---

## 一、整体架构

```
┌─────────────────────────────────────────────────────────┐
│                      世界运行时 (world)                    │
│   World(environment) · TimeEngine · EventBus · EventLog   │
└─────────────────────────────────────────────────────────┘
                           ▲ 单一事实源 / 事件驱动
┌─────────────────────────────────────────────────────────┐
│                  双脑引擎 (enhanced_engine)                │
│   内心思考 inner_thought  ──私密──►  对外措辞 utterance     │
│   整合：记忆 / 情绪 / 欲望 / 羁绊 / 生活状态 / 思考日志      │
└─────────────────────────────────────────────────────────┘
                           ▲
┌─────────────────────────────────────────────────────────┐
│              共享基础设施 (engine + caller)                 │
│   Environment 场景 · IM 即时通讯 · agents 全局表 · LLM 调用  │
└─────────────────────────────────────────────────────────┘
```

### 1. 共享基础设施（根目录）
| 文件 | 职责 |
|------|------|
| `engine.py` | 场景管理 `Environment/envs`、即时通讯 `IM/msgCenter`、全局角色表 `agents`、`getContent` 响应解析。**原版 `Agent`/`run_step` 已废弃**，由增强引擎取代。 |
| `caller.py` | LLM 调用封装（腾讯 LKEAP `hy3`，支持 `max_tokens` 与失败重试）。 |

### 2. 增强层（双脑引擎 + 子系统，根目录）
| 文件 | 职责 |
|------|------|
| `enhanced_engine.py` | **核心**：双脑引擎。每个 `EnhancedAgent` 有 `inner_thought`（内心思考，私密）与 `utterance`（对外措辞）。统一编排记忆 / 情绪 / 欲望 / 羁绊 / 生活状态，由 `world_config.json` 开关控制。 |
| `enhanced_agent_factory.py` | 增强角色工厂，加载角色 JSON 并构造 `EnhancedAgent`。 |
| `enhanced_memory.py` | SQLite 持久化记忆：事实 / 印象 / 谣言种子 / 往来 / 反思，含艾宾浩斯遗忘曲线。 |
| `emotion_system.py` | 多维情绪（喜怒哀惧…）+ 自然衰减。 |
| `desire_system.py` | 欲望 / 惦记：执念 / 放弃 / 搁置三态演化。 |
| `bond_system.py` | 关系纽带：强度 + 叙事，IM 往来自动增长。 |
| `life_state.py` | 作息时间表，决定角色何时在线 / 离线。 |
| `thinking_logger.py` | 思考日志：把内心思考落盘，便于复盘。 |

### 3. 世界运行时（第二代重构，对标 OASIS）
| 文件 | 职责 |
|------|------|
| `environment.py` | `World` 单一事实源：整合 `agents/envs/msgCenter` + 羁绊 + 当面会谈 `FACE2FACE_TALKS`。 |
| `time_engine.py` | 每个角色独立时钟，交错调度（对标 OASIS `TimeEngine`）。 |
| `event_bus.py` | 轻量事件总线（对标 OASIS `Information Channel`）。 |
| `event_log.py` | 结构化事件记录：`events.jsonl` + 按场景 / 按人记录。 |

### 4. 运行入口（根目录）
| 文件 | 职责 |
|------|------|
| `enhanced_runner.py` | 回合制运行器：按轮次推进每个角色（持续运行）。 |
| `continuous_runner.py` | **连续时间运行器（方案 C）**：接入 `World/TimeEngine/EventBus/EventLog/RunMonitor`，支持断点续跑。 |
| `run_monitor.py` | 运行监控插件，被 `continuous_runner` 引用。 |

### 5. 目录
```
AI-agent-world/
├── engine.py / caller.py            # 共享基础设施
├── enhanced_*.py / *_system.py / thinking_logger.py   # 增强层
├── environment.py / time_engine.py / event_bus.py / event_log.py / world_config.json  # 世界运行时
├── enhanced_runner.py / continuous_runner.py / run_monitor.py  # 运行入口
├── data/        # 角色数据 JSON
├── tools/       # 有用工具（make_readable / compare_runs）
├── scripts/archive/  # 历史 / 批量 / 调试脚本（不保证可运行，仅供追溯）
└── docs/        # 运行记录文档
```

---

## 二、配置：`world_config.json`

开关矩阵（布尔），控制各子系统是否启用：

- `BOND_ENABLED` 关系纽带
- `EMOTION_ENABLED` 情绪系统
- `DESIRE_ENABLED` 欲望系统
- `MEMORY_ENABLED` 记忆系统
- `FACE2FACE_ENABLED` 当面会谈
- `THINKING_LOG` 思考日志落盘
- `LIFE_STATE_ENABLED` 作息时间表

关闭某开关即回退到「无该子系统」的轻量模拟，便于对照实验。

---

## 三、运行

```bash
# 回合制（持续运行）
python enhanced_runner.py

# 连续时间（推荐，支持断点续跑）
python continuous_runner.py
python continuous_runner.py --agents data/demo_agents.json --rounds 50
```

数据文件默认从 `data/` 读取；思考日志、记忆库（`*.db`）、事件日志（`*.jsonl`）为运行时产物，已被 `.gitignore` 忽略。

---

## 四、已实现功能（做到了什么）

- [x] **双脑引擎**：角色区分「内心思考」与「对外措辞」，思考私密、措辞对外。
- [x] **持久化记忆**：SQLite 存储事实 / 印象 / 谣言 / 往来 / 反思，带遗忘曲线。
- [x] **多维情绪 + 衰减**：情绪随交互变化并自然回落。
- [x] **欲望 / 惦记系统**：角色产生执念、放弃或搁置的目标。
- [x] **关系纽带**：IM 往来自动积累羁绊强度与叙事。
- [x] **作息 / 生活状态**：角色按时间表在线离线。
- [x] **思考日志**：内心思考可落盘复盘。
- [x] **结构化事件记录**：`events.jsonl` + 按场景 / 按人记录。
- [x] **第二代运行流（部分接入）**：`World / TimeEngine / EventBus` 已落地，`continuous_runner` 已接入；但 `enhanced_engine` 仍用全局变量方式，尚未完全迁移到 `World` 单一事实源。

---

## 五、计划 / 路线图（下一步）

1. **统一运行时**：把 `enhanced_engine` 的全局变量（`envs/agents/msgCenter/bonds`）完全迁移到 `World` 单一事实源，消除两套状态并存。
2. **羁绊叙事化**：关系纽带从「强度数值」升级为「可触发事件 / 可回忆叙事」。
3. **欲望闭环**：让欲望真正驱动行为（主动发起会话、行动），而非仅记录。
4. **记忆质量**：提升反思（reflection）质量与跨会话长期演化。
5. **实验框架**：多世界并行、参数对照、相似度分析（`tools/compare_runs.py`）。
6. **可视化 / 回放**：把 `events.jsonl` / 思考日志渲染为可回放界面。

---

## 六、数据 / 工具 / 归档

- **`data/`**：角色集。`AuvAgents/japanAgents/JecAgents/malayaAgents` 为原版；`all_auv_agents/demo_agents/focus_agents` 为扩展。
- **`tools/`**：`make_readable.py`（原始日志转剧情本）、`compare_runs.py`（对比运行相似度）。
- **`scripts/archive/`**：历史批量 / 调试脚本（`run_*`、`launch_*`、`*monitor`、`patch_*.py` 一次性补丁、`status.py` 临时调试）。**不保证可运行**，仅作迭代追溯。
- **`docs/`**：`剧情记录.md`、`实机演示文档.md`、`record_by_person.md`、`record_by_scene.md`。
