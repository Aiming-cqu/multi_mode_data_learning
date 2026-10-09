# Agent → OpenClaw：大模型的操作系统化

> **时长**：30 分钟 | **关键词**：Agent, 上下文管理, 记忆, Pi Agent, Sub-agent, OpenClaw, Claude Code
>
> 返回 [总览](README.md) | 相关：[VLM → VLA](vlm-to-vla.md) · [RAG → Skill](rag-to-skill.md) · [在线演示](online-demo.md)

---

## 一、动机：从单轮响应到持续自主

### 1.1 大模型的原始能力

```
用户输入  →  模型推理  →  输出
   ↑                       ↓
   └───── 一轮对话结束 ──────┘
```

每次对话都是独立的。模型没有记忆、没有目标、没有自我驱动力。

### 1.2 Agent 要解决的核心问题

Agent = LLM + **持续运行的基础设施**

| 问题 | 描述 | 类比 |
|------|------|------|
| **记忆** | 跨会话保持重要信息 | RAM + 硬盘 |
| **上下文管理** | 在有限窗口内高效利用信息 | CPU 缓存管理 |
| **任务分解** | 将复杂任务拆解为可执行步骤 | 进程调度 |
| **自主决策** | 在无人干预下持续推进任务 | 后台服务 |

---

## 二、操作系统类比

### 2.1 CPU 缓存 vs 上下文窗口

这个类比揭示了 Agent 系统工程的本质：

```
操作系统                         Agent 系统
─────────                       ──────────
CPU 缓存 (L1/L2/L3)     ←→     上下文窗口 (128K tokens)
    ↑ 有限但极快                     ↑ 有限但模型直接使用
    
RAM (内存)               ←→     工作记忆 (Session State)
    ↑ 较大，需要加载到缓存            ↑ 较大，需要注入上下文
    
硬盘 (持久存储)           ←→     长期记忆 (Knowledge Base)
    ↑ 无限但慢                       ↑ 无限但需要检索

进程调度器               ←→     任务规划器 (Planner)
文件系统                 ←→     资源管理器 (Tool/Skill Registry)
驱动程序                 ←→     工具/MCP Server
系统调用                 ←→     Tool Call / API
```

### 2.2 关键洞察

> **Agent 系统工程的核心，就是在有限的上下文窗口内，通过一系列基础设施实现无限的信息管理能力。**

就像操作系统用有限的 CPU 缓存面对无限的硬件、IO 地址空间和软件事件，Agent 需要：

- **上下文调度器**：决定什么信息进入上下文窗口
- **记忆管理**：跨会话持久化和检索重要信息
- **任务调度**：分解和编排子任务执行顺序
- **权限控制**：限制 Agent 的行动范围

---

## 三、Agent 架构的演进

### 3.1 第一代：ReAct 模式（2022-2023）

```
思考 (Thought) → 行动 (Action) → 观察 (Observation) → 循环
```

代表：LangChain Agent, AutoGPT

问题：
- 循环容易发散或陷入死循环
- 错误累积，无恢复机制
- 上下文随循环增长，很快超出窗口

### 3.2 第二代：规划 + 执行（2023-2024）

```
总规划 → 子任务 1 → 子任务 2 → ... → 汇总
                ↓           ↓
          各自独立的上下文
```

代表：MetaGPT, CrewAI, AutoGen

改进：
- 任务拆分减少单次上下文压力
- 子任务并行执行
- 但规划质量依赖模型能力

### 3.3 第三代：极简工具 + 强大模型（2025）

```
System Prompt + Bash + File System = Everything
```

代表：**Claude Code**, GitHub Copilot CLI

核心突破：**不再堆砌框架，而是给模型最基本的工具（终端、文件系统），让模型自己决定如何使用。**

---

## 四、Claude Code：为什么极简设计如此有效

### 4.1 架构分析

Claude Code（以及本 CLI 工具）的架构极其简单：

```
┌──────────────────────────────────┐
│  System Prompt                    │
│  ┌────────────────────────────┐  │
│  │ 你是一个终端助手。           │  │
│  │ 你可以使用以下工具：         │  │
│  │ - bash: 执行命令           │  │
│  │ - view: 查看文件           │  │
│  │ - edit: 编辑文件           │  │
│  │ - grep: 搜索代码           │  │
│  │ ...                       │  │
│  └────────────────────────────┘  │
│                                   │
│  + 项目上下文                     │
│  + 编码规范                       │
│  + Skills (SKILL.md 文件)         │
│                                   │
│  → 一切能力都来自这些基本工具       │
└──────────────────────────────────┘
```

### 4.2 为什么这么简单却有效

| 原因 | 解释 |
|------|------|
| **模型足够强** | Claude Sonnet/Opus 级别的模型本身就能规划和推理 |
| **bash 是万能工具** | 通过 bash 可以做任何事——编译、测试、网络请求、文件操作 |
| **文件系统即记忆** | 不需要专门的记忆模块，文件就是持久化存储 |
| **对话历史即上下文** | 不需要复杂的上下文管理，对话本身就是工作记忆 |
| **系统提示即人设** | 不需要复杂的 Agent 框架，System Prompt 定义一切 |

### 4.3 这种设计的局限

| 问题 | 描述 |
|------|------|
| **可越狱** | 完全通过 System Prompt 定义行为，存在 Prompt Injection 风险 |
| **上下文耗尽** | 长任务中上下文窗口会被历史对话填满 |
| **无多任务** | 单线程执行，无法同时处理多个独立任务 |
| **无持久记忆** | 会话结束后所有上下文丢失（除非写入文件） |

---

## 五、Pi Agent：极简主义的编程 Agent

### 5.1 背景

当 libGDX 游戏框架创造者 **Mario Zechner** 对 Claude Code 日益增长的复杂性感到不满时，他构建了一个信奉 **"删减比添加更重要"** 的编程 Agent——**Pi**。Pi 是 OpenClaw 的核心引擎，也是极简 Agent 设计哲学的最佳实践。

> 📦 仓库：[`badlogic/pi-mono`](https://github.com/nicepkg/pi-agent) — TypeScript monorepo，npm workspaces

### 5.2 三层架构

```
┌─────────────────────────────────────────┐
│ Applications                            │
│ pi-coding-agent, pi-tui, pi-mom, ...    │
├─────────────────────────────────────────┤
│ Core                                    │
│ pi-agent-core  (~1000 行)               │
├─────────────────────────────────────────┤
│ Foundation                              │
│ pi-ai  (300+ 模型定义, 4 种 LLM 协议)    │
└─────────────────────────────────────────┘
```

**基础包零内部依赖。核心包仅依赖基础层。构建系统强制执行此约束。**

#### pi-ai：LLM 抽象层

Pi 识别出所有 LLM 供应商本质上只说 **四种通信协议**：

| 协议 | 端点 | 供应商 |
|------|------|--------|
| OpenAI Completions | `/v1/chat/completions` | OpenAI, Groq, Together, ... |
| OpenAI Responses | `/v1/responses` | OpenAI (新版) |
| Anthropic Messages | `/v1/messages` | Anthropic |
| Google Generative AI | `/v1beta/models/{model}:generateContent` | Google |

围绕这四种协议规范化后，**调用 300+ 模型看起来完全一样**：

```typescript
const model = getModel('anthropic', 'claude-sonnet-4-20250514');
for await (const event of stream(model, context)) {
  if (event.type === 'text_delta') process.stdout.write(event.delta);
}
```

#### pi-agent-core：执行引擎

核心循环极其简单——没有最大步数限制、没有计划模式、没有内置待办跟踪：

```typescript
async function* agentLoop(model, context, tools, options) {
  while (true) {
    const response = await streamCompletion(model, { ...context, tools });
    yield { type: 'assistant_message', content: response.content };
    if (!response.toolCalls?.length) break;  // 模型说完成就完成
    for (const call of response.toolCalls) {
      const result = await executeToolCall(call, context);
      // 将结果追加到上下文，继续循环
    }
  }
}
```

Mario 的论点：*"循环运行直到 Agent 说它完成了"*、*"把计划写入文件——完全可观察"*、*"待办列表通常让模型更困惑而不是帮助"*。

### 5.3 四个内置工具

Pi 只提供 **4 个工具**，这是其极简哲学的核心体现：

| 工具 | 功能 | 设计要点 |
|------|------|----------|
| `read` | 读取文件和图片 | 支持批量路径、行范围选择 |
| `write` | 创建/覆写文件 | 只需 path + content |
| `edit` | 精确文本替换 | **要求精确字符串匹配**，无正则无模糊，迫使模型先读再改 |
| `bash` | 执行 shell 命令 | 同步执行，需要后台进程则用 tmux |

> **为什么不需要更多工具？** *"所有前沿模型都经过了大量 RL 训练，天生理解什么是编程 Agent。模型知道 bash 是什么。给它 bash，它可以调用任何 CLI 工具。添加专门工具只是给系统提示词增加 token 而不增加能力。"* —— Mario Zechner

### 5.4 系统提示词：不到 1000 token

对比 Claude Code 数千 token 的系统提示词：

```
You are Pi, a coding assistant.

You have access to these tools:
- read: Read files and images
- write: Create/overwrite files
- edit: Make surgical edits to files
- bash: Run shell commands

Work directly in the user's project. Read files to understand context
before making changes. Use bash to run tests, linters, and other tools.
Think step by step. If you're unsure, read more files or ask the user.
```

其余项目上下文通过 **AGENTS.md 文件**按需加载（类似本项目的 `.github/copilot-instructions.md`）。

### 5.5 关键创新

#### 创新 1：上下文可移植性

Context 对象完全可序列化，**可跨供应商移植**：

```
用 Claude 写代码 → 保存会话 → 加载后用 GPT-4 继续
Thinking 跟踪在跨供应商时自动降级为标记文本
```

#### 创新 2：仅追加 DAG 会话格式

会话持久化为 `.jsonl`，每个条目有 `id` + `parentId`，形成**有向无环图**：

```
┌── entry1 ── entry2 ── entry3 (main branch)
│                  └── entry4 (branched)
└── entry5 ── entry6 (another branch)
```

分支只是移动"叶指针"，不创建新文件。整个历史永远保留。

#### 创新 3：Steering 机制

用户可在 Agent 运行中**实时打断**：每个工具执行完后检查 steering 队列，发现新消息则跳过剩余工具，将消息注入上下文。这与 "FollowUp"（停止后续接）形成互补。

#### 创新 4：渐进式披露的技能系统

```
Skills ≫ MCP (token 效率)

MCP: Playwright 服务器每个会话转储 21 个工具 + 13,700 token (7-9% 上下文窗口)
Skill: 只有 description 永久存在于上下文中，完整内容在触发器匹配时按需加载
```

### 5.6 Pi Agent 给 Agent 构建者的启示

| 要点 | 解释 |
|------|------|
| **上下文是真正的瓶颈** | 系统提示词中每个 token 都是性能税 |
| **更少的工具可能更好** | bash 可以调用任何 CLI 工具，不需要专门包装 |
| **渐进式披露胜过预加载** | 按需加载文档，而非每次会话全量注入 |
| **会话可移植性很重要** | 能在对话中切换模型和分支 |
| **验证错误作为工具结果** | 模型在同一轮内自我纠正，而非崩溃退出 |

---

## 六、OpenClaw：消息平台上的自主 Agent

### 6.1 背景

OpenClaw（原名 Clawdbot → Moltbot）由奥地利开发者 Peter Steinberger 于 2025 年 11 月创建，是首个在消息平台上运行的开源自主 AI Agent。

- GitHub Stars：247,000+（截至 2026 年 3 月）
- 创始人于 2026 年 2 月加入 OpenAI，项目交由非营利基金会管理
- 中国开发者将其适配到 DeepSeek + 微信等平台

### 6.2 核心创新

#### 创新 1：Channel（消息通道即交互界面）

```
传统 Agent：
  用户 → CLI/Web UI → Agent → 执行结果 → 用户

OpenClaw：
  用户 → Signal/Telegram/Discord/WhatsApp → OpenClaw → 执行结果 → 用户
              ↑
        已有的消息平台，无需安装新应用
        自然对话界面，像和真人聊天一样
```

**为什么 Channel 是创新**：

1. **零安装成本**：用户不需要学习新的 UI，直接在日常使用的消息 App 中操作
2. **异步交互**：Agent 可以在后台持续工作，完成后通过消息通知用户
3. **多设备同步**：消息平台本身的多端同步能力，Agent 状态自动跨设备
4. **机器人交互感**：用户感觉在和一个"有生命"的助手对话，而非使用冰冷的工具

#### 创新 2：Skill 系统

OpenClaw 的 Skill 系统与我们项目的 `docs/skills/` 高度相似：

```
skills/
├── reading-cooper-documents/
│   └── SKILL.md
├── web-search/
│   └── SKILL.md
└── calendar-management/
    └── SKILL.md
```

技能是 **Markdown 文件**，不是代码。Agent 通过阅读理解 SKILL.md 来学习如何执行任务。

核心优势：
- 模型可以自主创建新技能
- 技能用自然语言描述，人类可以审计和修改
- 技能文件可以像文档一样共享和版本控制

#### 创新 3：Sub-agent（子智能体）

```
用户: "开车到目的地，途中帮我点一杯卡布奇诺"

Main Agent:
  ├── 驾驶任务（持续执行）
  │   └── Sub-agent: 导航 + 控车
  │
  └── 点咖啡任务（异步执行）
      └── Sub-agent: 搜索咖啡店 → 下单 → 确认
```

Sub-agent 本质上解决的是**上下文隔离**问题：
- 每个 Sub-agent 有独立的上下文窗口
- 互不干扰，专注各自任务
- 通过消息通道汇报结果给 Main Agent

### 6.3 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    OpenClaw 架构                          │
│                                                          │
│  消息平台 (Signal/Telegram/...)                           │
│      ↕ (Channel)                                         │
│  ┌──────────────────────────────────────────────────┐    │
│  │  OpenClaw Runtime (本地运行)                       │    │
│  │                                                    │    │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  │    │
│  │  │ LLM Client │  │ Skill Mgr  │  │ Memory     │  │    │
│  │  │ (Claude/   │  │ (SKILL.md  │  │ (本地持久化) │  │    │
│  │  │  GPT/DS)   │  │  发现/匹配) │  │            │  │    │
│  │  └────────────┘  └────────────┘  └────────────┘  │    │
│  │                                                    │    │
│  │  ┌────────────┐  ┌────────────┐                   │    │
│  │  │ Sub-agent  │  │ Sub-agent  │  ...              │    │
│  │  │ Manager    │  │ Manager    │                   │    │
│  │  └────────────┘  └────────────┘                   │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  配置和历史存储在本地                                       │
└─────────────────────────────────────────────────────────┘
```

### 6.4 安全问题

OpenClaw 的开放性也带来了严重的安全挑战：

| 风险 | 描述 |
|------|------|
| **Prompt Injection** | 恶意指令嵌入在数据中，被 Agent 当作合法指令执行 |
| **权限过大** | Agent 可以访问邮箱、日历、消息等敏感服务 |
| **第三方技能** | 社区提交的 Skill 可能包含恶意行为（Cisco 已验证） |
| **自主行动** | Agent 可能执行用户未明确授权的操作（MoltMatch 事件） |

> ⚠️ OpenClaw 维护者警告："如果你不理解命令行操作，这个项目对你来说太危险了。"

---

## 七、从 Claude Code 到 Pi Agent 到 OpenClaw：设计哲学对比

| 维度 | Claude Code / Copilot CLI | Pi Agent | OpenClaw |
|------|--------------------------|----------|----------|
| 系统提示词 | 数千 token | < 1000 token | 继承 Pi |
| 内置工具 | 10+ | **4 个** | 4 + 扩展 |
| 界面 | 终端 (CLI) | 终端 (TUI) | 消息平台 |
| 用户群 | 开发者 | 开发者 | 所有人 |
| 会话格式 | 线性 | **仅追加 DAG** | 继承 Pi |
| 上下文管理 | 预加载 | 渐进式披露 | 继承 Pi |
| 扩展性 | 有限 | 20+ 生命周期钩子 | 钩子 + 插件 |
| 技能 | SKILL.md（项目级） | SKILL.md（按需加载） | ClawHub 市场 |
| 安全模型 | 用户确认关键操作 | 扩展拦截 | 自主执行，有风险 |
| 核心理念 | 增强开发者能力 | 极简主义 | 替代日常任务 |

### 共同点

三者都验证了同一个设计原则：

> **System Prompt + 基本工具 + 技能系统 = 足够强大的 Agent**
>
> 不需要复杂的框架，只需要：
> 1. 足够好的基础模型
> 2. 足够基本的工具（bash、文件系统、网络）
> 3. 可扩展的技能文档（SKILL.md）

---

## 八、系统工程：Agent 的质量保障（Harness）

Agent 不仅需要"跑起来"，更需要**可评测、可回放、可对比**。这属于系统工程范畴。

### 8.1 Agent Harness 的核心能力

```
┌────────────────────────────────────────────────┐
│                Agent Harness                    │
│                                                 │
│  录制：捕获 Agent 的完整执行轨迹                    │
│    → 工具调用序列、模型输入输出、决策节点             │
│                                                 │
│  回放：离线重现 Agent 行为                          │
│    → 不需要真实 API，用录制数据驱动                  │
│                                                 │
│  评测：自动化评分                                   │
│    → 任务完成率、工具调用准确率、成本、延迟           │
│                                                 │
│  对比：A/B 测试不同模型/策略                        │
│    → GPT-4o vs Claude vs DeepSeek 在同一任务上     │
└────────────────────────────────────────────────┘
```

### 8.2 为什么 Harness 很重要

| 问题 | 没有 Harness | 有 Harness |
|------|-------------|-----------|
| 回归测试 | "改了 prompt 不知道有没有变好" | 自动化对比前后版本 |
| 成本控制 | "不知道一次任务花了多少 token" | 精确统计每步开销 |
| 可复现性 | "上次能跑通这次不行了" | 录制回放，确定性复现 |
| 模型选择 | "感觉 Claude 比 GPT 好" | 数据驱动的定量对比 |

> 💡 这与传统软件工程的"CI/CD + 测试覆盖率"异曲同工——Agent 时代的"测试"就是 Harness。

---

## 九、未来趋势

### 9.1 Agent 安全

- 形式化验证 Agent 行为边界
- 基于权限模型的细粒度访问控制（类似 OAuth Scopes）
- Agent 行为审计和可追溯性

### 9.2 多 Agent 协作

- 标准化的 Agent 间通信协议（类似 A2A）
- Agent 组织结构（层级、对等、市场化）
- 集体智能涌现

### 9.3 Agent 与物理世界

- VLA + Agent = 自主物理智能体
- 从软件 Agent 到具身 Agent
- 三条技术路线的融合：VLA 感知行动 + Skill 自主学习 + Agent 持续运行

---

## 十、参考资料

### 项目

| 项目 | 说明 | 链接 |
|------|------|------|
| Pi Agent (pi-mono) | 极简编程 Agent，OpenClaw 核心引擎 | [github.com/badlogic/pi-mono](https://github.com/badlogic/pi-mono) |
| OpenClaw | 开源自主 AI Agent | [github.com/openclaw/openclaw](https://github.com/openclaw/openclaw) |
| Claude Code | Anthropic CLI Agent | [docs.anthropic.com/claude-code](https://docs.anthropic.com/en/docs/claude-code) |
| MetaGPT | 多 Agent 框架 | [github.com/geekan/MetaGPT](https://github.com/geekan/MetaGPT) |
| AutoGen | Microsoft 多 Agent | [github.com/microsoft/autogen](https://github.com/microsoft/autogen) |

### 文章

| 标题 | 来源 | 日期 |
|------|------|------|
| [Agent Pi 解剖 —— 驱动 OpenClaw 的极简编程 Agent](https://openclaw.deeptoai.com/zh-CN/docs/pi-agent-anatomy) | OpenClaw 文档 | 2026 |
| [Agentic AI: Pi — Anatomy of a Minimal Coding Agent Powering OpenClaw](https://shivamagarwal7.medium.com/agentic-ai-pi-anatomy-of-a-minimal-coding-agent-powering-openclaw-5ecd4dd6b440) | Medium | 2026 |
| [Everything about Clawdbot (now OpenClaw)](https://techcrunch.com/2026/01/27/everything-you-need-to-know-about-viral-personal-ai-assistant-clawdbot-now-moltbot/) | TechCrunch | 2026.01 |
| [From Clawdbot to OpenClaw: The AI agent generating buzz and fear](https://www.cnbc.com/2026/02/02/openclaw-open-source-ai-agent-rise-controversy-clawdbot-moltbot-moltbook.html) | CNBC | 2026.02 |
| [OpenClaw 的安全风险分析](https://www.wired.com/story/i-infiltrated-moltbook-ai-only-social-network/) | Wired | 2026.02 |

### 概念论文

| 论文 | 主题 | 年份 |
|------|------|------|
| [ReAct: Synergizing Reasoning and Acting](https://arxiv.org/abs/2210.03629) | ReAct 范式 | 2022 |
| [Voyager: An Open-Ended Embodied Agent](https://arxiv.org/abs/2305.16291) | 技能自主学习 | 2023 |
| [Cognitive Architectures for Language Agents](https://arxiv.org/abs/2309.02427) | Agent 架构综述 | 2023 |
