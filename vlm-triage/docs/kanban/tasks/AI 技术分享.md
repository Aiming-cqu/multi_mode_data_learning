# AI 技术分享

| 属性 | 值 |
| ---- | --- |
| ID | ai-tech-talk |
| 类型 | task |
| 优先级 | medium |
| 状态 | active |
| 创建日期 | 2026-04-07 |
| 更新日期 | 2026-05-17 |

## 概述

准备 2026 年前沿 AI 技术分享（约 90 分钟，3 × 30 分钟），涵盖 VLM→VLA、RAG→Skill、Agent→OpenClaw 三大主题，并配套在线演示。

## 背景

大模型三件套（模型、工具、上下文）的系统工程演进——如何让大模型从开环聊天走向自主行动。

## 范围

**在范围内：**

- 三个 Topic 的内容编写（动机、技术原理、代表性工作、趋势）
- 在线演示（Web 模拟驾驶 Demo + Skill Demo）
- PPT/幻灯片制作
- mkdocs 导航

**不在范围内：**

- 不涉及论文级别的原创工作（介绍型）
- 不录制正式视频

## 成功指标

| 指标 | 基线 | 目标 | 评价方法 |
| ---- | ---- | ---- | -------- |
| Topic 文档完成度 | 初稿 | 三个 Topic 终稿完成 | 文档审查 |
| Demo 可运行 | 无 | 两个 Demo App 可本地运行 | 现场演示 |
| 时间控制 | 无 | 3 × 30 分钟 ± 5 分钟 | 排练计时 |

## 三个 Topic

| Topic | 核心问题 | 详细文档 | 状态 |
|-------|----------|----------|------|
| VLM → VLA | 感知与行动的鸿沟 | [vlm-to-vla.md](../../guides/ai-tech-talks/vlm-to-vla.md) | 初稿 |
| RAG → Skill | 单轮上下文的能力边界 | [rag-to-skill.md](../../guides/ai-tech-talks/rag-to-skill.md) | ⭐ 重点，初稿 |
| Agent → OpenClaw | 长期任务的上下文管理 | [agent-to-openclaw.md](../../guides/ai-tech-talks/agent-to-openclaw.md) | 初稿 |

## 在线演示

- [在线演示设计文档](../../guides/ai-tech-talks/online-demo.md)
- Web 模拟驾驶 Demo，串联三个 Topic
- Skill Demo：Cooper 文档读取的 5 阶段跃迁

## TODO

- [x] 创建文档框架（总览 + 3 topic + 在线演示）
- [x] 编写 RAG → Skill 详细内容（重点 topic）
- [x] 编写 VLM → VLA 详细内容
- [x] 编写 Agent → OpenClaw 详细内容
- [x] 编写在线演示设计文档
- [x] 更新 mkdocs 导航
- [ ] 实现 Skill Demo App（`apps/skill_demo/`）
- [ ] 实现驾驶 Demo App（`apps/driving_demo/`）
- [ ] 制作演示用 PPT/幻灯片
- [ ] 排练和时间调整

## 原始思考笔记（存档）

背景：技术分享
话题：2026年最前沿的 AI 技术分享
从 VLM到 VLA，从 RAG 到 skill，从 agent 到 openclaw
大模型三件套：模型、工具、上下文系统工程是如何演进到如今
仿佛几乎快要迈入 AGI 时代
三种技术是如何让大模型从 开环/聊天问答，变成 自主探索/解决开放问题/真实世界交互的
我们要对这些话题进行分享
我希望对这三个话题进行展开介绍，平均每个30分钟，内容包括：
* 动机和需求
* 技术原理介绍
* 代表性工作介绍
* 未来发展趋势分析
* 在线演示

## VLM -> VLA
VLM 问题：看图说话，建模受架构限制，语言表征信息丢失严重
VLM 只通过文本 toolcall，无异于share context to llm，没有实质能力拓宽
VLA 方案：diffusion decode to analog control signals，建模连续控制量，保留更多视觉信息
代表性工作：DriveGPT、AutoPilotGPT、VLA-Drive
VLA 的另一种表现: gui2code，通过输入界面参考，生成网页 html 代码
（这种方案的闭环性容易被挑战，但是方便验证展示）
（https://modelscope.cn/models/nv-community/Alpamayo-R1-10B https://modelscope.cn/models/nv-community/Cosmos-Reason1-7B
英伟达 Alpamayo Cosmos 两个系列模型好像出到2了，可以代表 VLA的另一种形式
模型输出 预测轨迹，方便展示）

## RAG -> skill
实质是单轮对话上下文工程的极致扩展
原理 fewshot，解决特定任务能力拓展
模型本身只具备自身训练数据问答能力
超出范围产生幻觉
- 先引入 RAG，通过固定流程注入上下文，工程架构介绍。。。 embedding, vector db, retriever，reader，生成器
- RAG 的问题：流程复杂，检索到的上下文不稳定，多个模型协作，基于 特征空间，难以人类监督
- 随后引入 tool call
介绍 tool call 的起源， structure prompt, structure decoding 等，代表性工作。。。
- tool call 的问题：需要预定义 schema，缺乏灵活性，且仍然是单轮上下文注入
介绍 tool call 范式（openai api），通过 pydantic-ai 演示
- 然后是 mcp,将 tool call 服务化，因为存在 上下文存留的问题，所以 mcp 是有状态的
- 最后引入 skill + mcp，模型通过交互动态学习技能，无需预定义 schema，能够处理更复杂的任务和场景
- 介绍 skill 的格式，展示如何定义 skill 发现学习新的技能
代表性工作：AutoGPT、AgentGPT、MetaGPT 等
当下趋势：技能共享平台，技能自动化生成
- 展示模型自己创建技能并调用的过程，强调模型自主学习和适应能力

## agent -> openclaw
agent 是 上下文工程在长期任务中探索成果
相比工具调用，重点解决：
- 为了能超长期运行
- 记忆
- 上下文管理（压缩，插件）
- sub agent
- 本质都是将模型有限上下文，通过一些列基础设施进行无限改造
- 非常类似操作系统：cpu有限缓存，面对无限硬件、IO地址空间、软件事件等，需要调度器，文件系统，驱动程序等进行管理
- agent 的问题：复杂度高，安全风险大，成本高
- 完全通过 system prompt 定义 agent 人设，可越狱
- claude PI 等通过引入 bash 等工具，彻底解放大模型，代替人工操作系统
- 点评 PI 架构为什么好，为什么简单却有效
- openclaw 的提出，为什么火爆
- 核心创新。。。其中之一：channel，机器人交互感
- subagent 的概念，解决什么问题（本质还是上下文），展示 openclaw 的能力

## 关于在线演示
做一个 web 动画开车 的 demo，串联多个topic：
功能演示 人工开车，车道会变化，可以左右变道、有其他车辆需要躲避
vlm 识别，输出车辆在哪，环境如何，但是开环
vla 闭环，通过输出控制量真实操纵车辆达到目标车道/目的地
text extract 解析vlm输出，麻烦且出错
tool call：通过预定义范式接入模型精确控车
skill + mcp，模型无需预制 schema，动态学会开车
工具校验机制：看图也通过工具，必须看图才能做出控车决策：减少幻觉
使用 openclaw 开车，能自主发现自己持续开车（ui 显示目的地距离/eta）找到开车目标，不但能开车，还能调卡布基诺（通过 sub agent 完成别的任务）

以上是初步思考，请帮我查阅相关信息，整理到 guides/ai-tech-talks/ 下，一篇总文档 + 3篇 topic 文档 + 1篇在线演示文档，建立相互链接
要求
- 按可直接讲述分享到大纲拟稿
- 图文并貌，信息详实
- 我列的内容可能有误，请按查证实施撰写
- 我后面想到什么再补充

对了，我打算先做 skill 的分享
着重编写这个 topic
我打算用 咋们的 cooper 文档读取来做这个展示
帮我规划一下
从 plain tool call 到自创 skill 的过程，展示模型能力提升
是如何读取 cooper 文档，并通过 markitdown 解析，理解工作中的任务需求的
展示 模型 plain 输出、toolcall 输出、mcp 服务、skill 文件结构、skill 调用效果
每一个阶段都可以创建一个 app 来展示，app 里可以有交互式的输入输出，方便演示
docs/skills/reading-cooper-documents/SKILL.md 这个 skill的创建 是这个功能的最终形态

开始行动，无论遭遇难以解决的问题或者任务顺利完成，最后都要用 ask_question 向我确认下一步行动（如：是否需要我 review 改动），务必带上自由输入的选项。

## Iteration 20260416.2324

好的，PI 是另一个 著名的 agent 库，我把它列出来是因为它和 claude 一样也很有名，你要调研然后展开讲解
- 继续深化 RAG → Skill 文档内容
readme 反馈：
- VLA 用连续控制量取代文本输出 我想把那种通过图像生成网页的 任务介绍一下，也帮我调研

- 另外 我很喜欢 Agents to Wild: VLA, Skills and OpenClaw 这个标题，帮我保留
- 作为 skills 的最终演示产物，请检查 docs/skills/reading-cooper-documents/SKILL.md 是正确准确的skill文件，确保通过它能复现功能演示，测试文档链接（演示从此文件中总结） https://cooper.didichuxing.com/docs2/document/2207083647552
- 当然我更希望最终能演示多个工具组合，例如 cooper-cli export + cooper-cli normalize-docx + markitdown 拆解开来，得到最终的这个功能
- PI 的参考文献：https://openclaw.deeptoai.com/zh-CN/docs/pi-agent-anatomy  https://zhuanlan.zhihu.com/p/2009697625939658120

继续，我的反馈：

- 你觉得 UI2code 是一种 vla 吗？如果加上模型能闭环看到code渲染效果呢？
- 通过 mcp 操作浏览器是个 skill / agent 的好例子，咱们脑暴一下有什么好点子可以扣分享主题
- 分享时长有限，我们要去粗取精，抓听众爱听的，提醒我把控哈
- 本质问题：RAG 是一种”被动”的知识获取方式——模型无法控制检索什么、如何检索，只能被动接受流水线提供的上下文 我认为 RAG 是预置上下文的一种方案，将检索结果连同用户query放在一个对话中传入，模型就算有 困惑，也无法重新检索进行优化，大模型会收到 小 embedding 模型的制约，如果你认可这个观点，可以基于这个观点来展开 RAG 的问题，强调 tool call 和 skill 的优势
- 帮我读取 Cooper 文档 2207460511730" -》 改为 帮我总结/根据文档回答/at文档中提到的人，展示模型能力提升的过程，强调理解能力的提升，而不是单纯的读取能力
- 3.4 pydantic-ai 实现（本项目使用） 在这里可以介绍一下依赖注入/私钥隔离是如何防止大模型泄漏机密信息的（skill虽然开放，但是敏感信息不经过模型上下文）
- 精确性	近似匹配，可能检索无关内容	精确调用，获取确定性结果 其实我觉得tool 在检索上并不会比 RAG 精确，但是它与人对齐，人能够全文检索，skill也可以，这一点就更容易优化和友好
继续深化 rag-to-skill.md 内容

我的反馈：

- 工具调用不应该是一次性的函数调用，而应该是持久化的服务连接。 对！ 核心还是她妈的上下文！ 模型要上下文，工具也要上下文！openai api 要弃用 http 也是因为 http 无状态，发送上下文太累了，对吧！
- 为什么这个例子好： 1. 跨三个主题：VLA（视觉 → 操作浏览器）+ Skill（自主学习）+ Agent（多步骤推理） 2. 听众共鸣：每个人都有”在内网系统上反复点击”的痛点 3. 安全故事：凭据通过依赖注入，模型上下文中看不到密码——直接呼应 3.4 节 4. 可现场演示：Playwright MCP 已是成熟的开源项目 这块私下说（放到折叠区域）文档主体是直接向听众展示的
- 技能共享平台：类似 npm/PyPI 的技能注册中心，社区贡献和复用 这个有了，各种 skillhub，公司内就有 https://agentspace.intra.xiaojukeji.com/skills-plaza
- 跨 Agent 技能迁移：一个 Agent 学到的技能可以传递给另一个 我们是不是有 /create-skill 这个 skill了？我们可以展示 claude 创建 skill，GPT 使用哈！
- 开发 这5个应用 在线演示设计：Cooper 文档的 5 阶段能力跃迁
- todo RAG 方案 看能否用公司内的服务
- Tool Call 方案¶ 直接 pydantic-ai + python function
- 对了，还有 harness，这个放到 agent/openclaw里面讲，属于系统工程
- Playwright 原理讲一下，为什么能模拟人操作浏览器，为什么适合做 skill demo

继续深化 rag-to-skill.md 内容，给出预估分享时间（目标：30分钟）
开始行动，无论遭遇难以解决的问题或者任务顺利完成，最后都要用 ask_question 向我确认下一步行动（如：是否需要我 review 改动），务必带上自由输入的选项。

忽略前面的工作，现在处理 @docs/kanban/tasks/AI 技术分享.md，请先切换上下文到当前文件，分析当前文件的内容和结构，理解当前文件的作用和与其他文件的关系，再进行后续的解释、规划或者编码。

我在进行进行一次AI技术分享材料编写，文件入口 docs/guides/ai-tech-talks/README.md 帮我 review 我的分享内容检查其中是否有事实性谬误和缺失的部分，代入听众的身份，提出疑惑和进行批判

## Iteration 20260416.1515

- 文件关系已确认：`docs/kanban/tasks/AI 技术分享.md` 是任务/迭代记录，`docs/guides/ai-tech-talks/README.md` 才是对外讲述入口；README 负责总叙事，topic 文档负责展开细节
- 高风险事实点：
  - `VLM → VLA` 中“用连续控制量取代文本输出”表述过强，容易被 RT-2 / OpenVLA 这类离散 action token 路线反驳，应改成“输出空间从纯文本扩展到可执行动作空间”
  - `Cosmos-Reason1` 更像 Physical AI / reasoning VLM backbone，不宜直接与 RT-2 / OpenVLA 并列成标准 VLA 成品
  - `RAG → Skill` 中“模型自主学习技能”容易被追问成参数级学习；更稳妥的说法是“模型发现、编排、复用外部技能”
  - `MCP = 工具调用的服务化与状态管理` 过窄；MCP 首先是工具/资源/提示词的标准化协议，状态能力是常见实现形态，不是定义本身
  - `rag-to-skill.md` 里的 pydantic-ai 示例与仓库中的 `CooperClient.export()` 实际签名不一致，技术型听众容易当场指出
  - `agent-to-openclaw.md` 中 Pi / OpenClaw / Mario Zechner 的关系要更严谨，仓库链接与文本描述也需要统一
- 结构缺口：
  - README 一方面说一个 Web 驾驶 demo 串起 3 个 topic，另一方面又把 Cooper 文档 demo 作为第二讲主演示，主线 demo 与补充 demo 的关系还不够清楚
  - 三条“演进路线”分别落在模型架构、工具协议、Agent 产品/系统工程三个层级，建议补一个统一比较框架，否则会被质疑在横向比较不同抽象层
  - 缺少“哪些旧方案仍然有效”的 trade-off 视角；如果只讲替代关系，听众会觉得像技术宣传而不是技术分享

## Iteration 20260417.0042

思考：在咱们这个项目里，该如何践行 harness 方法论？如何驱动 agent 高质量、可观测、自驱动地开发

## Iteration 20260417.0055

- 按“只补 review comment、不直接改正文”的方式，已在 `docs/guides/ai-tech-talks/README.md` 的总览、三讲大纲和在线演示处补充 `Comment（Review）` 小节
- 当前 comment 重点提示了 4 类风险：抽象层混用、VLA / MCP / Skill 表述过强、Pi / OpenClaw 事实关系、主线 demo 与 Cooper demo 的叙事冲突

## Iteration 20260417.0108

- 继续按“只补 comment、不改正文”的方式 review `docs/guides/ai-tech-talks/rag-to-skill.md`
- 新增 comment 主要覆盖 6 类风险：
  - 把 `Few-shot → RAG → Tool Call → MCP → Skill` 讲成线性替代史的风险
  - 对 RAG 的批判过猛但缺少“为什么工业界仍大量使用”的 trade-off 说明
  - pydantic-ai / Cooper 示例和仓库真实接口不一致
  - “无法泄漏机密信息”“从根本上杜绝”这类安全表述过于绝对
  - MCP 被狭义讲成“状态化 Tool Call”的风险
  - Skill / BAGEL / 代表性工作部分存在概念跨层与样本选择问题

### demo case

```
我们重新排练一次哈：
使用 intranet-fetcher 工具
总结这篇 Cooper 文档 https://cooper.didichuxing.com/docs2/sheet/2207446242019?sheetId=MODOC
将 标注整体进展、按标注人员统计汇总
发送 到 vchannel_id=3745865090272085760 中 ，再 at 相关人员并 cc lishuna
```

补充 RAG，tool call mcp, skill 的演进过程中，上下文注入的策略/位置是如何变化的
绘图展示 RAG，tool call mcp, skill 的演进过程中，上下文注入的策略/位置是如何变化的
绘制 flashcard 形式，展示原理
生成简洁一点的，高亮 llm 处理请求的流程，三种技术中的 LLM用同一标识

标题 改下 RAG → Skill 这种还是改成 From RAG to Skill

生成 RAG 的流程图 flashcard，以介绍工作原理
文档建库（这里换用专业术语）+ retriver(检索+重排) + context builder 流程要分开

Retriever	检索策略（稀疏/稠密/混合）	BM25 + Dense, ColBERT
Reader/Reranker	精排 & 上下文压缩	BGE-Reranker, Cohere Rerank
的分工和原理是什么，能介绍一下嘛（放在文档 details中）

画 flashcard 图介绍 依赖注入、凭据分离是如何避免大模型访问到敏感信息同时又能处理数据/工具调用的
开始画图

画图flashcard mcp 配置解释，各字段含义
  "dchat-webhook-mcp": {
    "env": {
      "DCHAT_WEBHOOK_URL": "https://im-dichat.xiaojukeji.com/api/hooks/incoming/c7438dda-65d7-4fa7-a96a-949ef57a9903"
    },
    "args": [
      "-y",
      "--registry=http://npm.intra.xiaojukeji.com/",
      "@didi/dchat-webhook-mcp"
    ],
    "command": "npx"
  },


## Iteration 20260417.1512

fetch_cooper_markdown 换成 lib.platforms.ep.cooper 的 download + normalize实现
mcp 已安装，修复 stage 3

MCP 协议 使用这里面的server /Users/didi/.copilot/mcp-config.json，我希望 intranet-fetcher 获取文档

志伟：固定流程准备的数据是否是提示词

可以补充介绍一下 tool 和 skill 是如何一起打包介绍的，如 claude skill 的 scripts和 mcp服务是怎么写进skill的

增加一个 功能，在streamlit 上展示所有对话日志，包括 user, assistant, tool call 等，折叠在一个section
