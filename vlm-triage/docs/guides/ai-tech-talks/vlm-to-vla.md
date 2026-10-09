# VLM → VLA：从看图说话到物理交互

> **时长**：30 分钟 | **关键词**：VLM, VLA, Diffusion Policy, 物理 AI, 自动驾驶
>
> 返回 [总览](README.md) | 相关：[RAG → Skill](rag-to-skill.md) · [Agent → OpenClaw](agent-to-openclaw.md) · [在线演示](online-demo.md)

---

## 一、动机：VLM 的根本局限

### 1.1 VLM 做了什么

Vision-Language Model（VLM）实现了**视觉感知与语言理解的统一**：

```
图片/视频  →  Vision Encoder  →  视觉 Token  →  LLM  →  文本输出
                                    ↑
                              投影层 (Projection)
```

代表性模型：GPT-4V/4o、Claude 3.5 Sonnet、Qwen-VL、InternVL、LLaVA

### 1.2 VLM 的信息瓶颈

VLM 的所有输出都必须通过**语言表征**——这是一个严重的信息瓶颈：

```
视觉输入（连续、高维、空间）
    ↓
  语言输出（离散、低维、序列）  ← 信息瓶颈
    ↓
  "前方有一辆红色轿车，距离约 30 米，正在变道"
```

| 维度 | 视觉信号 | 语言描述 | 信息损失 |
|------|----------|----------|----------|
| 空间位置 | 像素级精确 | "前方约 30 米" | 精度从 cm 级退化到 m 级 |
| 速度/加速度 | 连续量 | "正在减速" | 丢失数值 |
| 姿态/朝向 | 3D 向量 | "面朝左侧" | 丢失角度 |
| 时序动态 | 逐帧变化 | "正在变道" | 丢失时间分辨率 |

### 1.3 VLM + Tool Call ≠ 真正的能力扩展

VLM 通过 Tool Call 与外部系统交互时，仍然受限于语言表征：

```
VLM 看到场景 → 文本描述场景 → 文本指令操作
                    ↑
              信息在这里丢失了
```

这等同于把视觉信息"share context to LLM"——模型并没有获得新的视觉推理能力，只是用语言转述了视觉内容。真正需要的是：**模型直接从视觉输入产生行动输出，绕过语言瓶颈。**

---

## 二、VLA：连接感知与行动

### 2.1 核心思路

VLA（Vision-Language-Action）的核心突破：**不再将所有输出都编码为文本 token，而是通过专门的 Action Head 直接输出连续控制量。**

```
┌──────────────────────────────────────────────────┐
│                    VLA 架构                        │
│                                                    │
│  视觉输入 ──→ Vision Encoder ──→ 视觉 Token         │
│                                     ↓              │
│  语言指令 ──→ Text Tokenizer ──→ 文本 Token         │
│                                     ↓              │
│                              ┌──────────┐          │
│                              │  LLM     │          │
│                              │ Backbone │          │
│                              └────┬─────┘          │
│                                   │                │
│                    ┌──────────────┼──────────────┐  │
│                    ↓              ↓              ↓  │
│              ┌──────────┐  ┌──────────┐  ┌────────┐│
│              │Text Head │  │Action Head│  │Value   ││
│              │(语言输出) │  │(控制输出)  │  │Head    ││
│              └──────────┘  └──────────┘  └────────┘│
│                               ↓                    │
│                    连续控制量：                       │
│                    [Δx, Δy, Δθ, v, ω, ...]         │
└──────────────────────────────────────────────────┘
```

### 2.2 Action Head 的实现方式

#### 方式 1：Diffusion Policy（扩散策略）

将动作生成建模为去噪扩散过程：

```
随机噪声 → 多步去噪 → 动作轨迹
                ↑
        条件：视觉特征 + 语言指令
```

优势：能建模多模态动作分布，适合复杂操作任务。

#### 方式 2：直接回归

LLM 最后一层 hidden state → MLP → 连续动作向量

```
hidden_state[-1]  →  Linear(d, action_dim)  →  [Δx, Δy, Δθ]
```

简单高效，但难以建模复杂的动作分布。

#### 方式 3：离散化 Token 预测

将连续动作空间离散化为 token（如 VQ-VAE），复用 LLM 的 next-token prediction：

```
动作空间 → VQ 量化 → 256 个离散 action token
LLM 预测：... [ACTION_032] [ACTION_187] [ACTION_005] ...
```

### 2.3 VLA vs VLM 对比

| 维度 | VLM | VLA |
|------|-----|-----|
| 输出 | 文本 | 文本 + **连续控制量** |
| 信息保留 | 视觉 → 语言（有损压缩） | 视觉 → 动作（直接映射） |
| 闭环能力 | ❌ 开环（描述但不行动） | ✅ 闭环（感知 → 决策 → 行动） |
| 实时性 | 语言生成延迟高 | 动作输出可优化到毫秒级 |
| 应用场景 | 问答、分析、报告 | 机器人控制、自动驾驶、GUI 操作 |

---

## 三、代表性工作

### 3.1 RT-2（Google DeepMind, 2023）

**Robotics Transformer 2** — VLA 概念的里程碑。

- 基础：PaLM-E（VLM）
- 创新：将机器人动作编码为文本 token（如 `[1, 128, 91, 241, ...]`），复用 LLM 的 token 预测
- 成果：在 700+ 真实机器人任务上验证，展示了 VLM 知识到机器人控制的迁移

> 📖 [RT-2: Vision-Language-Action Models Transfer Web Knowledge to Robotic Control](https://arxiv.org/abs/2307.15818)

### 3.2 OpenVLA（Stanford, 2024）

首个真正开源的 VLA 基础模型。

- 基础：Llama 2 + SigLIP Vision Encoder
- 训练数据：Open X-Embodiment（970K 机器人轨迹）
- 特点：7B 参数，可在消费级 GPU 上微调
- 开源：模型权重、训练代码、评估基准全部开放

> 📖 [OpenVLA: An Open-Source Vision-Language-Action Model](https://arxiv.org/abs/2406.09246)

### 3.3 π₀（Physical Intelligence, 2024）

通用机器人基础模型，展示了 VLA 的工程潜力。

- 架构：基于 PaliGemma（VLM） + Flow Matching Action Head
- 创新：Flow Matching 替代 Diffusion，训练更稳定
- 成果：单一模型覆盖折叠衣物、装盒、清理桌面等多种任务
- 意义：证明"一个模型搞定多种机器人任务"是可行的

> 📖 [π₀: A Vision-Language-Action Flow Model for General Robot Control](https://www.physicalintelligence.company/blog/pi0)

### 3.4 Cosmos-Reason1（NVIDIA, 2025）

Physical AI 推理模型——将物理常识和具身决策融入 VLM。

- 基础：Qwen2.5-VL（7B / 56B）
- 训练：Physical AI SFT + RL
- 核心能力：
  - **物理常识推理**：空间、时间、物理规律的层级本体
  - **具身决策**：在自然语言中生成下一步动作（如"向左转向 15°"）
  - **长链推理**：通过 Chain-of-Thought 推理物理世界的因果关系
- 数据：Cosmos-Reason1-SFT-Dataset + RL-Dataset
- 开源：[github.com/nvidia-cosmos/cosmos-reason1](https://github.com/nvidia-cosmos/cosmos-reason1)

> 📖 [Cosmos-Reason1: From Physical Common Sense To Embodied Reasoning](https://arxiv.org/abs/2503.15558)

### 3.5 Alpamayo（NVIDIA, 2025）

NVIDIA 专门面向自动驾驶的 Physical AI 模型系列。

- 版本：Alpamayo-R1-10B → Alpamayo-1.5-10B（已发布更新版）
- 训练数据：PhysicalAI-Autonomous-Vehicles, PhysicalAI-Autonomous-Vehicles-NuRec
- 特点：专注自动驾驶场景的物理推理和轨迹预测
- 输出：预测轨迹点序列，可直接用于路径规划

> 💡 Alpamayo 代表了 VLA 在自动驾驶领域的落地形态：模型不再只是"描述路况"，而是直接输出"行驶轨迹"。

### 3.6 VLA 的另一种形态：GUI Agent

VLA 的思想不限于物理机器人——GUI 交互也是一种"行动"：

```
视觉输入（屏幕截图）
    ↓
VLA 模型
    ↓
动作输出：click(x=320, y=480), type("hello"), scroll(dy=-100)
```

代表性工作：
- **CogAgent**（清华, 2024）：GUI 理解与操作
- **SeeClick**（上交, 2024）：视觉 grounding 到 GUI 元素
- **Design2Code**：输入界面参考图，生成 HTML 代码（VLA 思想的创意应用）

> 💡 Design2Code 是 VLA 范式在非机器人领域的精彩案例，详见[第五节](#五vla-的跨域应用design2code截图生成代码)。

---

## 四、自动驾驶场景中的 VLA

### 4.1 传统方案 vs VLA 方案

```
传统方案（模块化）：
  感知 → 检测 → 跟踪 → 预测 → 规划 → 控制
  ↑       ↑       ↑       ↑       ↑       ↑
  各自独立的模型和算法，误差逐级累积

VLA 方案（端到端）：
  视觉输入 → VLA 模型 → 轨迹/控制量
  一个模型搞定，端到端学习，无累积误差
```

### 4.2 典型数据流

```
多摄像头输入
    ↓
┌────────────────────────────────────┐
│  VLA for Autonomous Driving         │
│                                     │
│  Vision Encoder: 多视角图像编码       │
│      ↓                              │
│  Fusion: 多视角 + 时序融合            │
│      ↓                              │
│  LLM Backbone: 场景理解 + 推理       │
│      ↓                              │
│  Action Head: 轨迹预测               │
│      ↓                              │
│  输出: [(x₁,y₁,t₁), (x₂,y₂,t₂), ...] │
└────────────────────────────────────┘
    ↓
  车辆控制器执行
```

### 4.3 关键挑战

| 挑战 | 描述 | 当前进展 |
|------|------|----------|
| 安全性 | 必须保证 100% 安全，不容许"幻觉"导致事故 | RL + Safety Constraint |
| 实时性 | 控制频率 10-100 Hz，模型推理必须足够快 | 模型蒸馏 + 量化 |
| 可解释性 | 监管要求解释决策原因 | CoT 推理 + 注意力可视化 |
| 长尾场景 | 罕见场景（如施工区、事故现场）数据稀缺 | 仿真数据 + 迁移学习 |

---

## 五、VLA 的跨域应用：Design2Code（截图生成代码）

> VLA 的核心思想——**视觉输入 → 结构化输出，绕过自然语言瓶颈**——不止适用于机器人和自动驾驶。
> 在前端开发领域，Design2Code（截图 → HTML/CSS 代码）正是同一范式的精彩演绎。

### 5.1 任务定义：Image → Structured Code

```
输入：网页/UI 设计截图（像素级视觉信号）
  ↓
模型（VLM / MLLM）
  ↓
输出：可直接渲染的 HTML + CSS 代码（结构化动作）
```

这个任务的本质是：**模型从视觉输入中提取布局、颜色、文本、元素层级等信息，直接产生结构化代码**，而非先用自然语言描述"这是一个蓝色按钮在右上角"再让另一个系统去生成代码。

与 VLA 机器人控制的对比：

| 维度 | 机器人 VLA | Design2Code |
|------|-----------|-------------|
| 视觉输入 | 摄像头画面 / 场景图像 | UI 截图 / 设计稿 |
| 输出类型 | 连续控制量 `[Δx, Δy, Δθ, ...]` | 结构化代码 `<div class="...">` |
| 空间理解 | 3D 空间位置、物体姿态 | 2D 布局、元素层级、对齐关系 |
| 精度要求 | 厘米级定位 | 像素级还原 |
| 核心挑战 | 物理动力学 + 安全约束 | 布局重建 + 视觉元素召回 |
| 绕过语言 | ✅ 直接输出动作轨迹 | ✅ 直接输出代码（非"描述界面"） |

### 5.2 发展脉络：从 pix2code 到 GPT-4V

#### 🔹 pix2code（2017）— 开山之作

Tony Beltramelli 提出的首个端到端 GUI 截图 → 代码生成系统。

- **架构**：CNN（图像编码）+ LSTM（序列生成），encoder-decoder 范式
- **方法**：先生成 DSL（领域特定语言），再编译为目标平台代码
- **性能**：在 iOS / Android / Web 三平台达到 77% token 级准确率
- **局限**：仅支持简单 UI 组件，无法处理真实复杂网页
- **意义**：证明了**视觉 → 代码**的端到端学习是可行的

> 📖 [pix2code: Generating Code from a Graphical User Interface Screenshot](https://arxiv.org/abs/1705.07962) (2017)

#### 🔹 WebSight（HuggingFace, 2024）— 数据驱动的突破

HuggingFace 团队意识到缺乏高质量数据集是这一领域的核心瓶颈，因此构建了首个大规模合成数据集。

- **数据规模**：200 万对 HTML 代码 + 对应截图
- **生成流程**：
  - Mistral-7B 生成多样化网站概念（主题、行业、布局描述）
  - DeepSeek-Coder-33B 生成 HTML + Tailwind CSS 代码
  - Playwright 渲染并截图
- **模型**：Sightseer（8B 参数），基于 Mistral-7B + SigLIP 视觉编码器
- **创新**：选用 Tailwind CSS（内联样式，无需外部文件），降低学习复杂度
- **局限**：对复杂布局、大量文本的网页仍表现不佳；Tailwind CSS 在预训练数据中出现频率较低

> 📖 [Unlocking the conversion of Web Screenshots into HTML Code with the WebSight Dataset](https://arxiv.org/abs/2403.09029) (2024)

#### 🔹 Design2Code 基准（NAACL 2025）— 权威评测

Chenglei Si 等人构建了首个真实世界 Design2Code 基准，系统评估了前沿模型的能力。

- **数据集**：484 个精心筛选的真实网页测试用例
- **评估方法**：
  - 自动指标：视觉元素召回率、布局相似度、文本匹配、颜色准确度
  - 人工评估：标注者对比原始网页与生成网页
- **关键发现**：

| 模型 | 表现 | 说明 |
|------|------|------|
| **GPT-4V** | 🥇 最佳 | 49% 的生成网页可替代原始网页；64% 的情况被认为**优于**原始页面 |
| **GPT-4o** | 🥈 次佳 | 与 GPT-4V 接近 |
| **Gemini Pro Vision** | 一般 | 布局和元素召回弱于 GPT-4V |
| **Claude** | 一般 | 与 Gemini 水平相当 |
| **Design2Code-18B**（微调） | ≈ Gemini | 开源模型，在 WebSight 上微调后达到 Gemini 水平 |

- **核心差距**：
  - ⚠️ **视觉元素召回**：模型常遗漏输入网页中的元素
  - ⚠️ **布局设计**：多列布局、响应式设计等仍是难点
  - ✅ 文本内容和颜色：微调后可大幅改善

> 📖 [Design2Code: How Far Are We From Automating Front-End Engineering?](https://arxiv.org/abs/2403.03163) (NAACL 2025)

### 5.3 代表性工具和模型

#### Screenshot-to-Code（开源工具，⭐ 65k+）

最受欢迎的开源截图转代码工具（[github.com/abi/screenshot-to-code](https://github.com/abi/screenshot-to-code)）。

- **支持技术栈**：HTML+Tailwind / React+Tailwind / Vue+Tailwind / Bootstrap / Ionic / SVG
- **支持模型**：Gemini 3 Flash/Pro、Claude Opus 4.5、GPT-5.x 系列
- **特色功能**：
  - 支持**视频/屏幕录制 → 功能原型**（实验性）
  - 支持 Figma 设计稿输入
  - 迭代式优化：生成后可持续修改
- **架构**：React/Vite 前端 + FastAPI 后端，调用商业 VLM API

#### CogAgent（清华, CVPR 2024）

GUI 理解与导航的专用 VLM，与 Design2Code 紧密相关。

- **参数量**：18B
- **核心创新**：双编码器（低分辨率 + 高分辨率），支持 1120×1120 输入分辨率
- **能力**：识别微小页面元素和文本，在 GUI 导航任务（Mind2Web, AITW）上超越基于 HTML 的方法
- **意义**：**仅凭截图就能理解 GUI**，不需要访问 HTML DOM 树

> 📖 [CogAgent: A Visual Language Model for GUI Agents](https://arxiv.org/abs/2312.08914) (CVPR 2024)

#### SeeAct（OSU, 2024）

GPT-4V 作为通用 Web Agent 的探索。

- GPT-4V 在实时网站上可完成 **51.1%** 的任务（配合人工 grounding）
- 证明了 VLM 的视觉理解能力足以驱动 GUI 交互
- 瓶颈在于**视觉 grounding**：从理解到精确定位元素仍有差距

> 📖 [SeeAct: GPT-4V(ision) is a Generalist Web Agent](https://arxiv.org/abs/2401.01614)

### 5.4 与自动驾驶 VLA 的深层联系

Design2Code 和自动驾驶 VLA 共享同一个核心范式：

```
┌────────────────────────────────────────────────────────────┐
│               统一范式：视觉 → 结构化输出                      │
│                                                            │
│   ┌─────────────┐     ┌─────────────┐     ┌────────────┐  │
│   │  视觉输入    │ ──→ │  VLM 骨干    │ ──→ │ 结构化输出  │  │
│   └─────────────┘     └─────────────┘     └────────────┘  │
│                                                            │
│   自动驾驶：多摄像头    Qwen-VL / PaLM-E    轨迹点序列        │
│   Design2Code：截图    GPT-4V / Sightseer  HTML/CSS 代码    │
│   GUI Agent：屏幕      CogAgent            click(x,y)      │
│   机器人控制：相机      OpenVLA / π₀        关节角度          │
│                                                            │
│   共同点：                                                   │
│   1. 视觉输入直接映射到结构化输出，绕过自然语言瓶颈              │
│   2. 需要精确的空间理解（布局 / 位置 / 层级）                  │
│   3. 输出具有严格的格式约束（可执行代码 / 物理可行轨迹）        │
│   4. 同样面临"视觉元素召回"和"空间关系保持"的核心挑战          │
└────────────────────────────────────────────────────────────┘
```

**关键洞察**：

| 共性 | Design2Code | 自动驾驶 VLA |
|------|-------------|-------------|
| 空间精度 | 元素位置必须像素级精确 | 轨迹必须厘米级精确 |
| 结构化约束 | HTML 必须语法正确、可渲染 | 轨迹必须物理可行、安全 |
| 元素召回 | 不能遗漏页面中的按钮、图片 | 不能遗漏道路上的行人、车辆 |
| 长尾难题 | 复杂布局、罕见 UI 模式 | 施工区、事故现场 |
| 评估困难 | 视觉相似度 vs 像素完全匹配 | 安全性 vs 舒适性 |

这说明 **VLA 不是一个特定于机器人的技术概念，而是一种通用的 AI 架构思想**：只要任务的本质是"看 → 做"（而非"看 → 说"），就可以用 VLA 范式来思考和解决。

### 5.5 Design2Code 是 VLA 吗？——开环 vs 闭环的思考

严格来说，当前的 Design2Code 模型**尚不是完整的 VLA**，而更像是"视觉→结构化输出"的单向映射（开环）：

```
截图 → 模型 → HTML 代码    （开环：输出后不看效果）
```

但如果模型能**闭环**——看到代码渲染效果，再调整代码——这就真正成为了 VLA：

```
截图 → 模型 → HTML 代码 → 渲染 → 模型看到渲染结果
  ↑                                        ↓
  └────────────── 对比差异 → 修正代码 ←──────┘
                    （闭环迭代）
```

| 模式 | 类比 | 特点 |
|------|------|------|
| 当前 Design2Code（开环） | VLM 看图说话 | 一次生成，不验证效果 |
| 闭环 Design2Code（迭代） | VLA 机器人控制 | 感知→行动→感知→修正 |
| Screenshot-to-Code 工具 | 半闭环 | 用户看效果后手动迭代 |

**有趣的是，通过 MCP 操作浏览器可以天然实现这个闭环**：Agent 生成 HTML → 通过 Playwright MCP 渲染页面 → 截图对比 → 修正代码。这恰好连接了本次分享的三个主题：

```
VLA 思想（视觉→动作） + Tool Call/MCP（操作浏览器） + Agent（自主迭代）
     Topic 1                    Topic 2                  Topic 3
```

> 💡 这启示我们：**VLA 的本质不是特定的模型架构，而是一种闭环交互范式**。任何"感知→行动→验证→修正"的循环都是 VLA 思想的体现。

### 5.6 启示与展望

1. **数据是关键**：WebSight 证明了合成数据可以有效弥补真实数据的缺口——这对自动驾驶仿真数据训练同样有启发
2. **通用 VLM 已具备相当能力**：GPT-4V 在 64% 的情况下生成的网页被认为优于原始页面，说明大模型的视觉理解和代码生成能力已相当成熟
3. **专用微调仍有价值**：Design2Code-18B 通过微调达到了 Gemini 水平，证明在特定领域的微调仍是提升性能的有效路径
4. **跨域迁移**：GUI 理解（CogAgent）→ GUI 操作（SeeAct）→ GUI 代码生成（Design2Code）形成了完整的能力递进链，与自动驾驶中 场景理解 → 行为预测 → 轨迹规划 的链条高度同构

---

## 六、未来趋势

### 6.1 短期（2025-2026）

- **模型规模上升**：从 7B → 70B+，更强的物理推理能力
- **多模态融合**：视觉 + LiDAR + 语音 → 统一 VLA
- **开源生态**：OpenVLA → 更多领域专用 VLA

### 6.2 中期（2026-2027）

- **通用具身智能**：一个 VLA 模型跨机器人形态（车、人形、无人机）
- **仿真-真实迁移**：在仿真中训练，零样本迁移到真实世界
- **世界模型集成**：VLA + World Model → 想象未来 → 更好的规划

### 6.3 长期展望

- **物理 AGI**：模型不仅理解物理世界，还能在其中自主行动和学习
- **多 Agent 协同**：多个 VLA Agent 协调完成复杂任务（车队调度等）

---

## 七、参考资料

### 核心论文

| 论文 | 主题 | 年份 |
|------|------|------|
| [RT-2: Vision-Language-Action Models](https://arxiv.org/abs/2307.15818) | VLA 概念验证 | 2023 |
| [OpenVLA](https://arxiv.org/abs/2406.09246) | 开源 VLA 基础模型 | 2024 |
| [π₀: Flow Model for Robot Control](https://www.physicalintelligence.company/blog/pi0) | 通用机器人基础模型 | 2024 |
| [Cosmos-Reason1](https://arxiv.org/abs/2503.15558) | Physical AI 推理 | 2025 |
| [Diffusion Policy](https://arxiv.org/abs/2303.04137) | 扩散策略用于机器人控制 | 2023 |
| [BAGEL](https://arxiv.org/abs/2505.14683) | 统一多模态理解与生成 | 2025 |
| [Design2Code](https://arxiv.org/abs/2403.03163) | 截图→代码基准测试 (NAACL 2025) | 2024 |
| [pix2code](https://arxiv.org/abs/1705.07962) | GUI 截图→代码开山之作 | 2017 |
| [WebSight](https://arxiv.org/abs/2403.09029) | 200 万 HTML-截图合成数据集 | 2024 |
| [CogAgent](https://arxiv.org/abs/2312.08914) | GUI 理解 VLM (CVPR 2024) | 2023 |
| [SeeAct](https://arxiv.org/abs/2401.01614) | GPT-4V 通用 Web Agent | 2024 |

### 模型资源

| 模型 | 平台 | 链接 |
|------|------|------|
| Alpamayo-R1-10B | ModelScope | [nv-community/Alpamayo-R1-10B](https://modelscope.cn/models/nv-community/Alpamayo-R1-10B) |
| Alpamayo-1.5-10B | ModelScope | [nvidia/Alpamayo-1.5-10B](https://modelscope.cn/models/nvidia/Alpamayo-1.5-10B) |
| Cosmos-Reason1-7B | ModelScope | [nv-community/Cosmos-Reason1-7B](https://modelscope.cn/models/nv-community/Cosmos-Reason1-7B) |
| Screenshot-to-Code | GitHub | [abi/screenshot-to-code](https://github.com/abi/screenshot-to-code) (⭐ 65k+) |
| Design2Code-18B | HuggingFace | [SALT-NLP/Design2Code-18B-v0](https://huggingface.co/SALT-NLP/Design2Code-18B-v0) |
| WebSight 数据集 | HuggingFace | [HuggingFaceM4/WebSight](https://huggingface.co/datasets/HuggingFaceM4/WebSight) |
| Design2Code 基准 | HuggingFace | [SALT-NLP/Design2Code](https://huggingface.co/datasets/SALT-NLP/Design2Code) |
