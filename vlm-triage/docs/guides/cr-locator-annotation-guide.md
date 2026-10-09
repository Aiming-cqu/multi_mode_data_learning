# CR 定位标注手册

标注前端入口：**http://10.152.24.170:8085/?task=%F0%9F%8F%B7%EF%B8%8F+CR+%E6%A0%87%E6%B3%A8**

---

## 1. 任务背景

### 1.1 什么是 CR 定位？

在自动驾驶仿真回归测试中，Base 版本和 Feature 版本之间有多个代码提交（CR）。当仿真指标发生变化时，需要找出是哪个 CR 引入了行为变化——这个 CR 被称为**拐点 CR**。

**大模型 CR 定位**通过采集各 CR 版本的仿真动画截图，利用视觉特征相似度或 VLM 理解判断行为拐点。

详细算法原理见：[大模型 CR 定位](../../kanban/features/大模型%20CR%20定位.md)

### 1.2 为什么需要人工标注？

自动定位算法存在局限：
- 单调假设可能不成立（变化可能是非线性的）
- 视觉特征模型可能无法捕捉特定行为差异
- 采样窗口可能未覆盖关键变化时刻

人工标注的目标：**为算法提供真值数据，量化评估和改进定位准确率。**

---

## 2. 标注工具说明

### 2.1 入口与导航

访问标注前端，选择任务「🏷️ CR 标注」：
- 在顶部输入框粘贴一个或多个 **Locator ID**（空格/换行分隔）
- 每个 Locator ID 对应一个定位任务，分 tab 展示

### 2.2 页面结构

```
左侧边栏
├── 参数配置（采样窗口数、采样分辨率等）
└── Report 反馈按钮

主区域
├── 元信息（locator_id, diff_type, base/feat task_id, 场景链接）
└── 各场景网格
    ├── 按时间窗口（W01, W02...）分 tab
    └── 每行一个 CR，每列一个采样点
        ├── 图像缩略图
        ├── diff_type 下拉（变化类型）
        └── rank 下拉（召回必要性/判定清晰度）
```

### 2.3 标注数据来源

| 数据集 | 来源 |
|--------|------|
| 0313 collision | [Cooper 表格](https://cooper.didichuxing.com/docs2/sheet/2207120954333?sheetId=MODOC) — G列/crlocator_id，过滤：I列=有效 & AC列=不一致 |
| 0327 collision | [Cooper 表格](https://cooper.didichuxing.com/docs2/sheet/2207258701214?sheetId=Q0BBF) — F列/crlocator_id，过滤：H列=有效 & U列=不一致 |

也可从 DOS 下载已有 Excel 报告：[te-ds-autolabeling-dos-1/luonairui/data/visual-cr-locator-api/](https://base.xiaojukeji.com/odin/guigu/#/gift/ofs/detail/voyager-te-ds/nmgpu/te-ds-autolabeling-dos-1/file/luonairui/data/visual-cr-locator-api/)

---

## 3. 标注字段说明

### 3.1 Cell 级标注

每个可标注的 cell（CR × 窗口 × 采样点）有两个字段：

#### diff_type（变化类型）

该 cell 的图像相对 Base 和 Feature 的行为变化方向：

| 选项 | 全称 | 含义 |
|------|------|------|
| `P2F` | Pass→Fail | 该 CR 开始出现不通过行为（回退方向变化） |
| `F2P` | Fail→Pass | 该 CR 开始恢复通过行为（改进方向变化） |
| `P2P` | Pass→Pass | 两个版本都通过，变化体现在驾驶质量 |
| `F2F` | Fail→Fail | 两个版本都不通过，行为变化不影响通过率 |
| *(空)* | | 无明显变化，或无法判断 |

#### rank（召回必要性）

标识该 cell 的拐点重要性。**置空（默认）表示关键拐点**——只标注 diff_type 不填 rank，即隐含该 CR 是最高优先级拐点。

| 选项 | 含义 |
|------|------|
| *(空，默认)* | **关键**：如果只输出一个拐点就是它；多次 F2P/P2F 反复时每个临界点都是关键拐点 |
| `次要` | 有行为变化但不影响核心指标（如避免了纵向碰撞但出现横向变道） |
| `轻微` | 噪声级别，从动画难以看出差别 |

### 3.2 场景级标注

每个场景底部可选填：

| 字段 | 说明 |
|------|------|
| **场景无效** | 选择该场景为无效的原因（端到端无效 / 非链路拐点 / 链路需展开 / 采样问题 / 其他） |
| **场景备注** | 自由文本，记录观察到的特殊情况或疑问 |

---

## 4. 标注步骤

### 步骤 1：理解场景背景

1. 查看元信息行：`diff_type`（场景整体变化方向）、`metrics`（触发指标）
2. 点击「Diff」链接，在 Voyager 中对比 Base vs Feature 完整动画
3. 明确**端到端关键差异**：车辆轨迹？决策时机？速度曲线？ **是否端到端有效**

### 步骤 2：对比 Base 和 Feature 行

- `cr_index = -1`（标注为 Base）行：Base 版本表现
- `cr_index = -2`（标注为 Feature）行：Feature 版本表现
- 判定 Base 到 Feature 的变化是否与端到端一致 **采样是否准确**

### 步骤 3：逐 CR 观察拐点

从第 1 个 CR 逐行向下观察：
- **何时**图像从「像 Base」变为「像 Feature」？
- 变化是否**单调**（逐步累积），还是存在反复？

### 步骤 4：标注 diff_type 和 rank

对每个有显著变化的 cell：
1. 选择 `diff_type`：该 CR 在该样本点上的变化方向
2. 选择 `rank`（可选）：如果行为变化属于次要或轻微，显式标注；否则留空（默认=关键拐点）

**推荐策略**：
- 只标注拐点附近的 CR（不需要标注所有 cell）
- 关键拐点 → 填 `diff_type`，不填 `rank`（置空即为关键）
- 次要/轻微变化 → 填 `diff_type` + 对应 `rank`

### 步骤 5：保存标注

点击「💾 保存标注」按钮，标注文件自动保存到服务器。

---

## 5. 标注示例

### 示例 A：理想单一拐点

场景：车辆从急刹（Base）到绕行（Feature），CR3 是拐点。

| CR | W01 diff_type | W01 rank |
|----|---------------|----------|
| Base (-1) | — | — |
| CR1 | | |
| CR2 | | |
| **CR3** | `F2P` | *(空，关键)* |
| CR4 | `F2P` | `次要` |
| Feature (-2) | — | — |

### 示例 B：次要/轻微变化

场景：CR5 导致了行为变化，但属于次要行为（横向变道，不影响核心碰撞指标）；CR4 几乎无法从图像分辨。

| CR | W01 diff_type | W01 rank |
|----|---------------|----------|
| CR4 | `F2P` | `轻微` |
| CR5 | `F2P` | `次要` |

### 示例 C：场景无效

Base 和 Feature 的图像本身就相似，场景在端到端视角无意义。
→ 填写「场景无效 = 端到端无效」，跳过 cell 级标注。

---

## 6. 常见问题

**Q：Base 和 Feature 行不可标注，为什么？**
A：`cr_index = -1, -2` 是参照行，不需要标注变化方向。

**Q：只能看图像，判断不了？**
A：点击元信息区的「Diff」链接查看完整仿真动画，或在备注中记录无法判断的原因。

**Q：多个 CR 都像拐点怎么处理？**
A：每个反复的临界点都标注为关键（留空 rank），各自填对应的 `diff_type`。

**Q：标注文件保存到哪里？**
A：保存至服务器 `TRIAGE_DATA_DIR/visual-cr-locator-fe/` 目录，自动以 `locator_id + scenario_id + config_hash` 命名。

**Q：为什么再次加载时不再重新走图片 API？**
A：若本地已存在标注 JSON，前端会优先读取其中的 `image_prefix`，并从该前缀恢复当前 `locator_id` 的全部图片，避免重复请求图片接口。

---

## 7. 标注输出格式

标注结果为 JSON 文件，结构如下：

```json
{
  "locator_id": 4769141,
  "scenario_id": "21353094",
  "base_task_id": 3699917500000009,
  "feat_task_id": 3699917900000010,
  "diff_type": "F2P",
  "metrics": ["dpe_collision"],
  "locator_url": "...",
  "diff_url": "...",
  "image_prefix": "data/visual-cr-locator-api/202604/2c08d64898f3",
  "comment": "可选备注",
  "scene_invalid": "端到端无效（可选）",
  "annotations": [
    {
      "cr_index": 11,
      "cr_desc": "3702162700000004 / 3c3602fe...",
      "window_index": "01",
      "window_desc": "W01 @ 5601ms",
      "sample_index": "05",
      "sample_desc": "S05 @ +490ms",
      "image_url": "data/visual-cr-locator-api/202604/2c08d64898f3/locator_id=4769141-scenario_id=21353094-...",
      "diff_type": "F2P"
      // rank 字段未设置 → 隐含关键拐点
    },
    {
      "cr_index": 12,
      "cr_desc": "3702163000000001 / a4b2c3...",
      "window_index": "01",
      "window_desc": "W01 @ 5601ms",
      "sample_index": "05",
      "sample_desc": "S05 @ +490ms",
      "image_url": "data/visual-cr-locator-api/202604/2c08d64898f3/locator_id=4769141-scenario_id=21353094-...",
      "diff_type": "F2P",
      "rank": "次要"
    }
  ]
}
```

**字段说明：**
- 只保存**有 diff_type 标注**的 cell（空 diff_type 不写入）
- `rank` 仅在显式降级时写入（`次要` / `轻微`）；**缺少 rank 字段 = 关键拐点**
- `image_prefix` 为当前批次图片所在目录；老标注在读取时会自动补齐
- `image_url` 持久化为 `data/...` 对象路径，避免使用会过期的签名 URL
- `scene_invalid` / `comment` 为场景级可选字段
