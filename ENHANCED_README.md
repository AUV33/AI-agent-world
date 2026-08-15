# 🎭 致敬传奇AI项目 - 增强版架构说明

参考"智能体水濑祈"的运行原理，为项目增加了以下核心系统。

---

## 📦 新增系统

### 1. 增强版记忆系统 (`enhanced_memory.py`)

**特性：**
- SQLite 持久化存储
- 记忆压缩机制（避免上下文过长）
- 会话级记忆隔离
- 长期事实存储
- 内心想法记录
- 人际关系印象

**使用示例：**
```python
from enhanced_memory import EnhancedMemory

memory = EnhancedMemory("陈子墨", db_path="memory.db")

# 添加记忆
memory.add_message("今天考试考得不错")
memory.add_fact("成绩在年级前五", category="background")
memory.add_thought("其实压力很大，但不想让别人看出来")
memory.update_impression("林阳", "开朗的家伙，有点羡慕他的洒脱", 60)

# 获取上下文
context = memory.get_context(max_tokens=500)
```

---

### 2. 情绪状态系统 (`emotion_system.py`)

**特性：**
- 多维度情绪跟踪（快乐/悲伤/愤怒/恐惧/惊讶/厌恶）
- 情绪衰减机制（随时间恢复中性）
- 情绪影响行为决策
- 情绪历史记录

**使用示例：**
```python
from emotion_system import EmotionSystem

emotion = EmotionSystem("陈子墨")

# 更新情绪
emotion.update("happy", 0.8, "考试考得好")
emotion.update("angry", 0.3, "被人嘲讽")

# 获取状态
print(emotion.get_label())          # "开心"
print(emotion.get_mood_modifier())  # 0.65 (积极)
print(emotion.get_context_string()) # "当前心情：开心（65%积极）"
```

---

### 3. 生活状态系统 (`life_state.py`)

**特性：**
- 高中生作息时间表
- 活动状态机（上课/吃饭/睡觉/自由活动）
- 跨天记忆
- 随机事件

**使用示例：**
```python
from life_state import LifeState

life = LifeState("陈子墨")

# 获取当前状态
state = life.get_current_state()
print(state)
# {'state': 'study', 'activity': '晚自习', 'location': '教学楼-高二(3)班', 'time_in_state': 1800}

# 获取上下文描述
print(life.get_context_string())
# "当前状态：晚自习（在教学楼-高二(3)班，30分钟前开始）"

# 检查状态
print(life.is_awake())    # True
print(life.is_in_class()) # False
print(life.is_free())     # False
```

---

### 4. 思考日志系统 (`thinking_logger.py`)

**特性：**
- 记录AI的内心思考过程
- 分离思考与回复
- 支持思考分析
- JSONL格式便于后续处理

**使用示例：**
```python
from thinking_logger import ThinkingLogger

logger = ThinkingLogger("陈子墨")

# 记录思考
logger.log(
    messages=["今天考试考得怎么样"],
    think="这次数学考得不好，有点难过，但不想让别人看出来...",
    reply="还行吧，就那样"
)

# 分析思考模式
analysis = logger.analyze()
print(analysis)
# {'total': 1, 'think_rate': 1.0, 'avg_think_length': 35, ...}

patterns = logger.get_think_patterns()
print(patterns)
# {'decision_making': 0, 'emotion_processing': 1, 'memory_recall': 0, ...}
```

---

### 5. 增强版引擎 (`enhanced_engine.py`)

**整合了所有新系统的完整引擎**

**特性：**
- Agent 自动整合记忆、情绪、生活状态
- 思考过程自动记录
- 情绪根据行动自动更新
- 生活状态根据时间自动变化

**使用示例：**
```python
from enhanced_engine import EnhancedAgent, EnhancedEnvironment, run_step

# 创建Agent
agent = EnhancedAgent(
    name="陈子墨",
    persona="18岁，高二(3)班学生...",
    envName="教学楼-高二(3)班",
    memory="成绩在年级前五",
    impressions={"林阳": "开朗的家伙"}
)

# 获取行动
action, old_env, new_env = agent.get_action(envInfo, "第1天 14:00")
```

---

## 📊 数据存储结构

```
D:\致敬传奇AI项目\
├─ memory.db                    ← SQLite记忆数据库
├─ emotion_陈子墨.json          ← 陈子墨的情绪状态
├─ emotion_林阳.json            ← 林阳的情绪状态
├─ life_陈子墨.json             ← 陈子墨的生活状态
├─ life_林阳.json               ← 林阳的生活状态
├─ thinking_陈子墨.jsonl        ← 陈子墨的思考日志
├─ thinking_林阳.jsonl          ← 林阳的思考日志
└─ ...
```

---

## 🔧 与原系统的对比

| 功能 | 原系统 | 增强版 |
|------|--------|--------|
| 记忆存储 | 内存字符串 | SQLite持久化 |
| 记忆压缩 | 截断到600字 | 智能压缩+摘要 |
| 情绪系统 | 无 | 多维度跟踪 |
| 生活状态 | 无 | 作息时间表 |
| 思考记录 | 无 | JSONL日志 |
| 人际关系 | 简单印象 | 结构化存储 |

---

## 🚀 快速开始

### 方式一：使用增强版引擎

```python
# 在 run_school.py 中使用
from enhanced_engine import EnhancedAgent, EnhancedEnvironment, run_step
```

### 方式二：单独使用某个系统

```python
# 只使用记忆系统
from enhanced_memory import EnhancedMemory
memory = EnhancedMemory("角色名")

# 只使用情绪系统
from emotion_system import EmotionSystem
emotion = EmotionSystem("角色名")

# 只使用生活状态
from life_state import LifeState
life = LifeState("角色名")
```

---

## 💡 设计理念

参考"智能体水濑祈"的核心理念：

1. **人设是活的**：不是一成不变的死规则，而是有弹性的底色
2. **情绪是真实的**：有开心、有难过、有愤怒，不是永远平静
3. **生活是有节奏的**：上课、吃饭、睡觉、自由活动
4. **思考是有深度的**：内心想法、决策过程、情绪处理

> **"圣人不存在，每个人都戴着面具生活"**
