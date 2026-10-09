# Kanban

需求和任务的看板管理。支持三种卡片类型，按生命周期流转。

```
issue ──孵化──→ task ──归属──→ feature
  │               │               │
  └──孵化────────→ feature ──────┘
```

| 类型 | 含义 | 约束 |
| ---- | ---- | ---- |
| `issue` | 线上反馈驱动的轻量问题 | 头部 + 背景 + 分析即可，成功指标/验证方案可选 |
| `task` | 原子工程任务 | 推荐写成功指标和验证方案 |
| `feature` | 大功能模块，可含多个 task | 必须有成功指标和验证方案 |

状态流转：

```
planning → active → done
     ↘                  ↗
       ───→ archived ←──
```

- `planning`：刚创建，还在思考/讨论
- `active`：正在做
- `done`：按预期完成
- `archived`：不管什么原因关闭（完成归档/放弃/不再需要），正文注明原因

## 目录结构

```
kanban/
├── issues/     问题（Issues）      - 线上反馈驱动，轻量，可孵化到 feature/task
├── features/   功能需求（Features） - 较大的功能模块或能力提升
└── tasks/      任务（Tasks）       - 具体的工程任务、优化、治理
```

## 文档规范

每个卡片为一个 markdown 文件，命名格式：`<简短描述>.md`。

### 文件结构

### 通用模板（feature / task）

每个卡片为 Markdown 文件，无 YAML frontmatter，使用纯 Markdown 表格做头部。

```markdown
# {标题}

| 属性 | 值 |
| ---- | --- |
| ID | <kebab-case> |
| 类型 | feature / task |
| 优先级 | high / medium / low |
| 状态 | planning / active / done / archived |
| 创建日期 | 2026-01-01 |
| 更新日期 | 2026-01-01 |

## 概述
一句话说清做什么。

## 背景
为什么做，解决什么问题。

## 范围
**在范围内：**

- 明确包含的内容

**不在范围内：**

- 明确排除的内容

## 成功指标
| 指标 | 基线 | 目标 | 评价方法 |
| ---- | ---- | ---- | -------- |
| ...  | ...  | ...  | ...      |

## 验证方案
### 评价方法
如何客观测量成功指标（数据集、脚本、指标阈值）。

### 测试计划
- [ ] 具体可验证的测试项

## 需求详情
（可选，复杂功能用）

## 用户故事
（可选，有明确用户时用）

- 作为 <角色>，我希望 <功能>，以便 <价值>

## 关联
- 孵化自 [issue-xxx](../issues/xxx.md)
- 归属 [feature-xxx](../features/xxx.md)
- 关联文档（标注指南、API 文档等）

## 迭代记录
### Iteration YYYYMMDD.HHMM

<本轮目标或背景>

<执行记录或决策结论>
```

### Issue 模板（轻量）

```markdown
# {标题}

| 属性 | 值 |
| ---- | --- |
| ID | <kebab-case> |
| 类型 | issue |
| 优先级 | high / medium / low |
| 状态 | planning / active / done / archived |
| 来源 | 线上反馈 / 内部发现 / 用户投诉 |
| 创建日期 | 2026-01-01 |
| 更新日期 | 2026-01-01 |

## 概述
一句话描述现象或问题。

## 背景
现象、影响范围、复现条件。

## 分析
根因初步判断、是否需要进一步排查。

## 关联
- 孵化到 [feature-xxx](../features/xxx.md)
- 孵化到 [task-xxx](../tasks/xxx.md)

## 迭代记录
### Iteration YYYYMMDD.HHMM
```

### 字段说明

| 字段 | 必须 | 约束 | 说明 |
| ---- | :--: | ---- | ---- |
| 标题 | ✅ | | 一句话描述 |
| ID | ✅ | kebab-case | 唯一标识，不可变 |
| 类型 | ✅ | `issue` / `feature` / `task` | issue 可孵化到 feature 或 task |
| 优先级 | ✅ | `high` / `medium` / `low` | |
| 状态 | ✅ | `planning` → `active` → `done` / `archived` | `archived` 表示完结（含放弃/不再需要） |
| 来源 | issue 必须 | `线上反馈` / `内部发现` / `用户投诉` | 仅 issue 有此字段 |
| 创建日期 | ✅ | ISO 日期 `YYYY-MM-DD` | |
| 更新日期 | ✅ | ISO 日期 `YYYY-MM-DD` | 每次迭代后更新 |
| 概述 | ✅ | 一句话 | 让读者秒懂 |
| 背景 | 推荐 | | issue 写现象和影响；feature/task 写动机 |
| 分析 | issue 推荐 | | 根因判断，是否需排查 |
| 范围 | feature/task 推荐 | 正反列表 | issue 不需要 |
| 成功指标 | feature/task 推荐 | 基线+目标+评价方法 | issue 不需要 |
| 验证方案 | feature/task 推荐 | 评价方法+测试计划 | issue 不需要 |
| 迭代记录 | ✅ | 追加式，不修改历史 | 每次对话结束后追加 |

### 关联关系

| 关联方向 | 写法 | 含义 |
| -------- | ---- | ---- |
| 孵化自 | `孵化自 [issue-xxx](../issues/xxx.md)` | issue 驱动了此 feature/task |
| 孵化到 | `孵化到 [feature-xxx](../features/xxx.md)` | issue 孵化为此 feature/task |
| 归属 | `归属 [feature-xxx](../features/xxx.md)` | task 是此 feature 的一部分 |
| 分解为 | `分解为 [task-xxx](../tasks/xxx.md)` | feature 拆解为这些 task |

## 当前看板

### Issues

（暂无，待创建）

### Features

- [CR 定位可视化前端](features/CR%20定位可视化前端.md)
- [Cooper 平台接入](features/Cooper%20平台接入.md)
- [Excel 导出功能模块](features/Excel%20导出功能模块.md)
- [GPU 并发模型推理](features/GPU%20并发模型推理.md)
- [LLM 聚合代理服务](features/LLM%20聚合代理服务.md)
- [VL Embedding 模型探索](features/VL%20Embedding%20模型探索.md)
- [大模型 CR 定位](features/大模型%20CR%20定位.md)

### Tasks

- [Agent Tooling 模块重构](tasks/Agent%20Tooling%20模块重构.md)
- [CR 定位传统 CV 方法探索](tasks/CR%20定位传统%20CV%20方法探索.md)
- [CR 定位聚合算法优化](tasks/CR%20定位聚合算法优化.md)
- [Human In Loop Testing Setup](tasks/Human%20In%20Loop%20Testing%20Setup.md)
- [文档治理](tasks/文档治理.md)
- [Logging Tracing Observibility](tasks/Logging%20Tracing%20Observibility.md)
- [SOTA 模型调研](tasks/SOTA%20模型调研.md)
- [Vibe Coding 体验优化](tasks/Vibe%20Coding%20体验优化.md)
- [测试更新](tasks/测试更新.md)
