# 在线演示设计：Web 模拟驾驶

> 返回 [总览](README.md) | 相关：[VLM → VLA](vlm-to-vla.md) · [RAG → Skill](rag-to-skill.md) · [Agent → OpenClaw](agent-to-openclaw.md)

---

## 一、设计理念

用一个 **Web 动画模拟驾驶** Demo，串联三个 Topic 的核心概念。观众通过同一个场景，体验从"人工操作"到"AI 自主驾驶"的完整演进。

```
人工控制 → VLM 识别 → VLA 闭环 → Tool Call 接入 → Skill 自学 → Agent 自主
   ↑          ↑          ↑           ↑              ↑           ↑
 基线      Topic 1    Topic 1     Topic 2        Topic 2     Topic 3
```

---

## 二、场景设计

### 2.1 游戏界面

```
┌─────────────────────────────────────────────────┐
│  🚗 Web 模拟驾驶                    目的地: 3.2km │
│                                     ETA: 8 min   │
│  ┌─────────────────────────────────────────────┐ │
│  │    ===       ===       ===       ===        │ │
│  │         [🚙]                                │ │
│  │    ---       ---       ---       ---        │ │
│  │              [🚗 我]                        │ │
│  │    ---       ---       ---       ---        │ │
│  │                              [🚛]           │ │
│  │    ===       ===       ===       ===        │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  [←左变道] [直行] [右变道→]  [加速] [减速]           │
│                                                   │
│  模式: [人工] [VLM] [VLA] [Tool Call] [Skill] [Agent]│
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │  日志面板                                     │ │
│  │  > VLM: "前方 30m 有蓝色轿车，正在变道..."      │ │
│  │  > Action: steer_left(angle=15°)            │ │
│  └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

### 2.2 游戏规则

- **三车道**道路，玩家在中间车道
- 其他车辆（NPC）随机出现，有不同的行驶模式
- **目标**：安全行驶到目的地
- 车道变化、障碍物需要躲避
- UI 显示目的地距离和预计到达时间（ETA）

---

## 三、各模式详细设计

### Mode 0：人工控制（基线）

```
人类 → 键盘/按钮 → 控车
```

- 玩家用方向键/按钮控制车辆
- 完全手动，展示任务本身的复杂性

### Mode 1：VLM 识别（开环）

```
游戏画面截图 → VLM → 文本描述（不操控车辆）
```

- VLM 分析当前画面，输出场景描述
- **开环**：只描述，不行动
- 日志面板显示 VLM 的文本输出：

```
VLM 输出:
"当前场景：三车道公路，我方车辆位于中间车道。
前方约 30 米处有一辆蓝色轿车正在从左侧车道向中间车道变道。
右侧车道有一辆红色卡车，速度较慢。
建议：向右变道避让前方变道车辆。"
```

**问题展示**：VLM 能看懂场景，但无法操控车辆。

### Mode 2：VLA 闭环

```
游戏画面 → VLA → 控制量 → 操控车辆
```

- VLA 直接输出控制信号：

```json
{
  "steering": -0.15,    // 方向盘（左负右正）
  "throttle": 0.6,      // 油门
  "brake": 0.0          // 刹车
}
```

- 车辆按控制量移动
- **闭环**：感知 → 决策 → 行动 → 感知 → ...
- 日志显示：原始控制量 + 执行效果

### Mode 3：Text Extract（反面教材）

```
游戏画面 → VLM → 文本 → 正则解析 → 控车
```

- 用 VLM 输出文本，然后用正则/规则解析出控制指令
- **演示问题**：
  - VLM 输出格式不稳定（有时用中文、有时用英文）
  - 正则解析经常失败
  - 解析错误导致错误操作

```
VLM: "建议向左转 15 度"  → 解析: steer = -15°  ✓
VLM: "应该稍微往左打方向" → 解析: ???            ✗
VLM: "左转！快！"        → 解析: ???             ✗
```

### Mode 4：Tool Call

```
游戏画面 → VLM → Tool Call → 精确控车
```

- 预定义工具 schema：

```python
tools = [{
    "name": "control_vehicle",
    "parameters": {
        "action": "enum: left_lane_change | right_lane_change | accelerate | decelerate | maintain",
        "intensity": "float: 0.0 - 1.0"
    }
}]
```

- 模型输出结构化工具调用：

```json
{"tool": "control_vehicle", "arguments": {"action": "left_lane_change", "intensity": 0.7}}
```

- 精确、可靠，但需要人工预定义所有可能的操作

### Mode 5：Skill + MCP

```
游戏画面 → 模型 → 发现/学习驾驶技能 → 控车
```

- 模型无需预制 schema
- 首次驾驶时：
  1. 观察场景 → 尝试操作 → 总结经验
  2. 创建驾驶技能 SKILL.md
  3. 后续自动使用该技能
- 工具校验机制：
  - 模型必须先通过 `observe_scene()` 工具获取场景信息
  - 然后才能调用 `control_vehicle()` 执行操作
  - 确保模型"看了再动"，减少幻觉驾驶

```
Skill: autonomous-driving
  Step 1: observe_scene() → 获取车辆位置、障碍物
  Step 2: analyze_risk() → 评估碰撞风险
  Step 3: plan_maneuver() → 规划变道/加减速
  Step 4: execute_control() → 执行控制
```

### Mode 6：Agent（OpenClaw 模式）

```
Agent 自主运行：持续驾驶 + 处理附加任务
```

- Agent 自主发现自己在"开车"
- UI 显示目的地距离/ETA
- Agent 不仅开车，还能同时处理别的任务

```
Main Agent: "我正在驾驶前往目的地，ETA 8 分钟"
  ├── Sub-agent (驾驶): 持续执行 Skill: autonomous-driving
  └── Sub-agent (咖啡): 
      → 搜索沿途咖啡店
      → 选择最近的一家
      → 下单一杯卡布奇诺
      → "已为您在前方 2km 处的咖啡店下单卡布奇诺 ☕"
```

---

## 四、技术实现方案

### 4.1 前端

- **框架**：Streamlit（复用项目已有模式）或 HTML5 Canvas + WebSocket
- **渲染**：CSS/Canvas 2D，简化的鸟瞰视角
- **交互**：键盘事件 + 按钮切换模式

### 4.2 后端

- **游戏引擎**：Python 实现的简单 2D 物理模拟
  - 车道模型（3 车道）
  - 车辆运动（速度、位置、碰撞检测）
  - NPC 行为（随机变道、加减速）
- **AI 接口**：各模式对应不同的 AI 调用
  - Mode 1-2：实际调用 VLM/VLA（可用 mock 代替演示）
  - Mode 3-5：调用 LLM + Tool
  - Mode 6：启动 Agent 循环

### 4.3 目录结构

```
apps/driving_demo/
├── main.py              # Streamlit/Web 入口
├── game_engine.py       # 2D 物理模拟
├── npc_behavior.py      # NPC 车辆行为
├── ai_controller.py     # AI 控制器（各模式）
├── tool_definitions.py  # Tool Call schema 定义
├── skills/              # 演示用技能目录
│   └── autonomous-driving/
│       └── SKILL.md
├── mcp_server.py        # 驾驶 MCP Server
└── static/
    ├── index.html       # 游戏 UI
    └── style.css        # 样式
```

---

## 五、演示流程编排

### 时间分配（假设穿插在各 Topic 讲解中）

| 时段 | 演示内容 | 对应 Topic |
|------|----------|------------|
| 第一讲中间 | Mode 0 (人工) → Mode 1 (VLM) → Mode 2 (VLA) | VLM → VLA |
| 第一讲结尾 | Mode 3 (Text Extract) 的失败对比 | VLM → VLA |
| 第二讲中间 | Mode 4 (Tool Call) → Mode 5 (Skill) | RAG → Skill |
| 第二讲结尾 | Skill 自主创建过程展示 | RAG → Skill |
| 第三讲结尾 | Mode 6 (Agent) 自主驾驶 + 点咖啡 | Agent → OpenClaw |

### 演讲稿要点

1. **Mode 0→1**："VLM 能看懂，但不能动手。这就是我们为什么需要 VLA。"
2. **Mode 1→2**："从开环到闭环——VLA 直接输出控制量，绕过语言瓶颈。"
3. **Mode 2→3**："如果用文本解析来提取控制指令？看看会发生什么（翻车演示）。"
4. **Mode 3→4**："Tool Call 给了模型精确的操作接口。但这些接口是我们手写的。"
5. **Mode 4→5**："如果模型能自己学会开车呢？Skill 系统让模型自主创建驾驶技能。"
6. **Mode 5→6**："最终形态——Agent 不仅能开车，还能同时帮你点杯咖啡。"

---

## 六、备选方案

如果实时 Demo 风险太高（网络、API 延迟等），准备以下备案：

1. **录屏视频**：提前录制各模式的演示视频
2. **模拟模式**：用预录的 AI 响应代替实时调用
3. **分离演示**：各 Topic 使用独立的小 Demo 而非统一场景

---

## 七、与 Skill Demo 的关系

驾驶 Demo 串联所有 Topic，但 [RAG → Skill](rag-to-skill.md) 的专属 Demo 使用 **Cooper 文档读取**场景，更贴近工作实际。

两个 Demo 互补：
- **驾驶 Demo**：直观、视觉冲击，适合展示模式切换
- **Cooper Demo**：真实、技术深入，适合展示 Skill 系统细节

建议在讲到 Skill Topic 时同时使用两个 Demo。
