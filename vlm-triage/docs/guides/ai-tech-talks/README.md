# Agents to Wild: VLA, Skills and OpenClaw

> **背景**：2026 年前沿 AI 技术分享，约 90 分钟（3 × 30 分钟），含在线演示。

## 主题概览

大模型"三件套"—— **模型、工具、上下文** —— 的系统工程正在经历一场深刻变革。三条演进路线分别回答了同一个根本问题：**如何让大模型从开环聊天走向自主行动？**

| 演进路线 | 核心问题 | 解决思路 | 关键词 |
|----------|----------|----------|--------|
| [VLM → VLA](vlm-to-vla.md) | 感知与行动之间的鸿沟 | 用连续控制量取代文本输出 | Diffusion Policy, 物理 AI |
| [RAG → Skill](rag-to-skill.md) | 单轮上下文的能力边界 | 从检索注入到技能自主学习 | Tool Call, MCP, Skill |
| [Agent → OpenClaw](agent-to-openclaw.md) | 长期任务的上下文管理 | OS 化的记忆与调度基础设施 | Memory, Sub-agent, Channel |

三条路线并非孤立，而是从不同维度共同推动 AI 系统向 AGI 靠近：

```
感知能力          ←  VLM → VLA        （看懂世界 → 操控世界）
知识获取能力      ←  RAG → Skill      （被动检索 → 主动学习）
任务执行能力      ←  Agent → OpenClaw  （单轮响应 → 持续自主）
```

<details>

- 这里的 framing 很强，但三条线分别落在**模型架构、工具/协议、Agent 系统工程**三个抽象层，建议后面补一个统一比较框架，否则容易被质疑“横向比较的不是同一类东西”。
- “共同推动 AI 系统向 AGI 靠近”这句气势很足，但技术听众会觉得过满；如果你想让场子更稳，可以改成“共同推动 AI 系统走向更强的自主性与可执行性”。

</details>

## 分享大纲

### 第一讲：VLM → VLA — 从看图说话到物理交互（30 min）

> 详见 [vlm-to-vla.md](vlm-to-vla.md)

1. VLM 的架构局限：语言表征的信息瓶颈
2. VLA 的突破：Diffusion Decoder 输出连续控制量
3. 代表性工作：RT-2、OpenVLA、pi0、Cosmos-Reason1、Alpamayo
4. 自动驾驶场景中的 VLA 落地
5. VLA 跨域应用：Design2Code（截图→代码，VLA 思想在前端领域的演绎）
6. 在线演示：Web 模拟驾驶 — VLM 开环 vs VLA 闭环

<details>

- “Diffusion Decoder 输出连续控制量”这个表述偏窄，容易被 RT-2 / OpenVLA 的离散 action token 路线反驳。更稳妥的说法是：**输出空间从纯文本扩展为可执行动作空间，具体实现既可能是连续控制，也可能是离散动作 token / 轨迹 token。**
- `Cosmos-Reason1` 更适合讲成 **Physical AI / reasoning backbone**，不太适合和 RT-2 / OpenVLA 并列成标准 VLA 成品。
- `Design2Code` 作为“VLA 思想在前端的演绎”很有启发性，但它是不是 VLA 本身会被当场追问；建议你显式把它降格为“类比案例”而不是“代表性工作”。

</details>

### 第二讲：RAG → Skill — 上下文工程的极致演进（30 min）

> 详见 [rag-to-skill.md](rag-to-skill.md) ⭐ **重点 Topic**

1. 从 Few-shot 到 RAG：检索增强生成的工程架构
2. Tool Call 的诞生：结构化提示与结构化解码
3. MCP 协议：工具调用的服务化与状态管理
4. Skill 系统：模型自主学习技能的新范式
5. 在线演示：Cooper 文档理解 — 5 阶段能力跃迁（总结/问答/提取行动项）

<details>

- `MCP = 工具调用的服务化与状态管理` 这个定义有点过窄；更安全的讲法是：**MCP 首先是工具 / 资源 / 提示词的标准化协议，长连接与状态管理是常见实现收益，而不是协议唯一价值。**
- “模型自主学习技能”也偏强，听众会问“到底是学到参数里，还是生成外部 artifact？” 更建议表述为：**模型发现、编排、复用外部技能。**
- 这一讲是你最有项目实战支撑的一讲，但如果你在正文里继续用当前 `rag-to-skill.md` 的 pydantic-ai 例子，技术听众会发现它和仓库里的 `CooperClient.export()` 实际接口不一致，这个点最好后面统一修掉。

</details>

### 第三讲：Agent → OpenClaw — 大模型的操作系统化（30 min）

> 详见 [agent-to-openclaw.md](agent-to-openclaw.md)

1. Agent 的核心挑战：记忆、上下文压缩、子任务分解
2. 操作系统类比：CPU 缓存 vs 上下文窗口
3. Claude Code 的极简设计：为什么 System Prompt + Bash 如此有效
4. Pi Agent：4 个工具、< 1000 token 系统提示词、仅追加 DAG 会话
5. OpenClaw：消息平台 × 自主智能体 × 技能系统
6. 在线演示：自主驾驶 + 点咖啡 — Agent 的多任务协调

<details>

- 这一讲最大的风险不是观点，而是**样本选择**：`OpenClaw` 对很多听众来说不是共识性样本，更像是一个强烈的案例。建议你把它定位成 **case study**，不要讲成 “Agent 演进的终点”。
- `Pi Agent` / `OpenClaw` / `Mario Zechner` 的关系一定要讲准，不然可信度会掉得很快；这块最好在 topic 正文中给一张关系图。
- “仅追加 DAG 会话”这种说法对没看过系统的人不够自解释，听众会卡在术语上，不如换成“分支/追加式会话树”之类更直观的说法。

</details>

### 在线演示

> 详见 [online-demo.md](online-demo.md)

一个 Web 模拟驾驶 Demo，串联三个 Topic 的核心概念。

<details>

- 这里和第二讲的 `Cooper 文档理解` demo 之间存在主线冲突：现在 README 一眼看上去像是**一个统一的 Web 驾驶 demo**，但第二讲又明显需要**另一套 Cooper/Skill demo** 才能讲透。
- 建议你明确成“两层 demo 结构”：**一个主线 demo（Web 驾驶）负责串联三讲，一个重点 demo（Cooper 文档能力跃迁）负责把第二讲讲透。** 否则听众会搞不清到底现场演哪一个。

</details>

## 目录结构

```
docs/guides/ai-tech-talks/
├── README.md              ← 本文件（总览）
├── vlm-to-vla.md          ← Topic 1
├── rag-to-skill.md        ← Topic 2（重点）
├── agent-to-openclaw.md   ← Topic 3
└── online-demo.md         ← 在线演示设计
```

## 参考仓库

| 项目 | 用途 | 链接 |
|------|------|------|
| Cosmos-Reason1 | NVIDIA Physical AI 推理模型 | [github.com/nvidia-cosmos/cosmos-reason1](https://github.com/nvidia-cosmos/cosmos-reason1) |
| OpenVLA | 开源 VLA 基础模型 | [github.com/openvla/openvla](https://github.com/openvla/openvla) |
| Physical Intelligence π₀ | 通用机器人基础模型 | [physicalintelligence.company](https://www.physicalintelligence.company/blog/pi0) |
| OpenClaw | 开源自主 AI Agent | [github.com/openclaw/openclaw](https://github.com/openclaw/openclaw) |
| pydantic-ai | Python AI Agent 框架 | [github.com/pydantic/pydantic-ai](https://github.com/pydantic/pydantic-ai) |
| MCP Protocol | Model Context Protocol | [modelcontextprotocol.io](https://modelcontextprotocol.io) |
| BAGEL | 统一多模态理解与生成模型 | [bagel-ai.org](https://bagel-ai.org/) |
