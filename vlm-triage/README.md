# vlm-triage

基于视觉-语言模型（VLM）的自动驾驶路测问题切面化排查与分析工具集。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Pixi](https://img.shields.io/badge/Pixi-Package%20Manager-orange)](https://pixi.sh/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-green)](https://fastapi.tiangolo.com/)

## 项目概述

vlm-triage 是一个面向自动驾驶领域的多模态数据分析平台，通过融合视觉-语言模型（VLM）、embedding 技术和智能代理系统，帮助工程师快速定位和分析路测中的问题场景。

### 核心问题

- **多模态数据难以统一分析**：图像、视频、日志、表格、自然语言等数据形态各异
- **复杂场景缺乏自动化分析**：传统规则方法无法覆盖复杂交互场景
- **仿真结果差异难定位**：仿真版本对比缺乏自动化归因手段

### 核心特性

- **工具化设计**：所有功能模块支持 ① 独立测试 ② RESTful API 调用 ③ Agent 工具调用
- **功能为中心**：不限于 LLM，综合运用工具、特征工程、embedding、LLM、Agent 等技术
- **多环境部署**：支持批处理（CLI）、服务化（FastAPI）、可视化（Streamlit）三种形态

## 架构设计

### 三层架构

```
┌─────────────────────────────────────────────────────────────┐
│                      应用系统层                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │   CLI    │  │ FastAPI  │  │Streamlit │                  │
│  │ 批处理   │  │ 服务化   │  │ 可视化   │                  │
│  └──────────┘  └──────────┘  └──────────┘                  │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Agent 系统层                            │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │   业务 Tools     │  │  多模态 Resource │                │
│  │  (Tool封装)      │  │  (存储抽象)      │                │
│  └──────────────────┘  └──────────────────┘                │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Model 系统层                            │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ 非标准模型接入   │  │  Embedding/特征  │                │
│  │ (OpenAI API兼容) │  │  (CLIP/DINOv2等) │                │
│  └──────────────────┘  └──────────────────┘                │
└─────────────────────────────────────────────────────────────┘
```

### 应用场景

| 应用场景 | 描述 |
|---------|------|
| **Issue 场景分析** | 对自然语言描述、结构化表格、图像、日志渲染动画进行多模态结构化分析，输出道路信息、自驾状态、接管动作、关键冲突对象等 |
| **仿真 Diff 分析** | 对比相同场景两个版本仿真动画，指出仿真车表现变化，通过 VLM Agent 在 30s 仿真场景上自主采样完成分析 |
| **仿真拐点定位** | 对仿真视频采样，抽取图像 embedding，通过相似度判断当前版本是 base feature 还是 outlier |

## 应用系统

### 1. Embedding API (`apps/embedding_api/`)

基于预训练视觉模型的图像 Embedding 提取服务。

**功能**：
- 图像 Embedding 提取（CLIP、DINOv2、SigLIP、AIMv2 等）
- 图像相似度计算

**端点**：
- `POST /embed` - 提取图像 embedding
- `POST /compute_similarity` - 计算图像相似度矩阵

**运行**：
```bash
pixi run -e vllm -- python apps/embedding_api/main.py
```

### 2. CV API (`apps/cv_api/`)

基于传统 CV 算法的图像相似度计算服务。

**功能**：
- 使用 SIFT 等算法计算图像相似度
- 对比基准图像和特征图像

**端点**：
- `POST /compute_similarity` - 计算图像相似度

**运行**：
```bash
pixi run -e opencv -- python apps/cv_api/main.py
```

### 3. Visual CR Locator API (`apps/visual_cr_locator_api/`)

关键冲突对象定位服务（主 API）。

**运行**：
```bash
pixi run fastapi dev apps/visual_cr_locator_api/main.py
```

### 4. Visual CR Locator Frontend (`apps/visual_cr_locator_fe/`)

Streamlit 可视化界面。

**运行**：
```bash
pixi run serve-fe
# 或
streamlit run apps/visual_cr_locator_fe/main.py
```

### 5. Voyager Proxy (`apps/voyager_proxy/`)

Voyager 平台代理服务。

### 6. Aurora Scenario Labeling (`apps/aurora_scenario_labeling/`)

场景标注工具。

## 快速开始

### 前置要求

- Python >= 3.10
- [Pixi](https://pixi.sh/) 包管理器
- GPU（用于模型推理，可选）

### 1. 安装 Pixi

```bash
# Linux
curl -fsSL https://pixi.sh/install.sh | sh

# macOS
brew install pixi
```

### 2. 配置环境变量

添加到 `~/.bashrc` 或 `~/.zshrc`：

```bash
export PIXI_HOME="${HOME}/.pixi"
export RATTLER_CACHE_DIR="${PIXI_HOME}/cache"
export RATTLER_AUTH_FILE="${PIXI_HOME}/credentials.json"
export CONDA_PREFIX="${PIXI_HOME}"
export CONDA_PKGS_DIRS="${RATTLER_CACHE_DIR}/pkgs"
export MAMBA_ROOT_PREFIX="${PIXI_HOME}"
export UV_CACHE_DIR="${RATTLER_CACHE_DIR}/uv-cache"
export PATH="${PIXI_HOME}/bin:${PATH}"

alias conda=micromamba
alias ta='tmux -u new -ADs'
```

### 3. 挂载云存储

```bash
sh scripts/ofs-mount.sh
```

### 4. 配置本地密钥

编辑 `scripts/activation/local.sh`（首次运行会自动生成模板）：

```bash
# 配置本地路径、密钥等信息
```

### 5. 运行应用

Pixi 会自动安装依赖：

```bash
# 运行测试
pixi run etest

# 启动 Embedding API
pixi run -e vllm -- python apps/embedding_api/main.py

# 启动 CV API
pixi run -e opencv -- python apps/cv_api/main.py

# 启动可视化前端
pixi run serve-fe
```

## 内置 CLI 工具

### S3 CLI (`lib/utils/s3_utils.py`)

通过 `pyproject.toml` 中的任务入口执行：

```bash
pixi run s3-cli --help
```

支持 `ls`、`put`、`get`、`sign`、`put-sign` 五个子命令；默认 bucket 为 `te-ds-autolabeling-dos-1`，可通过 `--bucket` 覆盖。当前只有 `ls` 支持 `--recursive`，其余四个命令都是单对象操作，不支持 batch/递归。

```bash
# 列出对象（可加 --recursive 递归）
pixi run s3-cli ls triage/data/

# 上传本地文件：参数顺序是 <object_name> <file_path>
pixi run s3-cli put demo/report.txt README.md

# 下载对象：参数顺序是 <object_name> <file_path>
pixi run s3-cli get demo/report.txt /tmp/report.txt

# 为已存在对象生成 presigned URL
pixi run s3-cli sign demo/report.txt --download-name report.txt

# 上传后直接拿 presigned URL
pixi run s3-cli put-sign demo/report.txt README.md
```

如需沿用项目里的分区命名规则，可在 `put` / `put-sign` 中显式传入 `--app-name` 与 `--prefix`，CLI 会将对象名解析为 `prefix/app_name/YYYYMM/object_name`：

```bash
pixi run s3-cli put reports/daily.xlsx README.md \
  --app-name visual-cr-locator-api \
  --prefix "$TRIAGE_DATA_PREFIX_IN_S3"
```

上传支持从 stdin 读取，下载支持写到 stdout，便于管道串联：

```bash
cat README.md | pixi run s3-cli put demo/stdin-readme.txt -
pixi run s3-cli get demo/stdin-readme.txt - > /tmp/stdin-readme.txt
```

## 目录结构

```
vlm-triage/
├── apps/                           # 应用入口
│   ├── aurora_scenario_labeling/   # 场景标注工具
│   ├── cv_api/                     # CV 图像相似度 API
│   ├── embedding_api/              # Embedding 提取 API
│   ├── visual_cr_locator_api/      # 关键帧定位 API
│   ├── visual_cr_locator_fe/       # Streamlit 可视化界面
│   └── voyager_proxy/              # Voyager 平台代理
│
├── lib/                            # 核心库
│   ├── algorithms/                 # 核心算法
│   │   ├── cr_locate.py            # 冲突对象定位
│   │   ├── cv_similarity.py        # CV 相似度计算
│   │   ├── embedding_extractor.py  # Embedding 提取
│   │   ├── embedding_metrics.py    # 相似度指标
│   │   └── max_coverage.py         # 最大覆盖采样
│   │
│   ├── platforms/                  # 第三方平台接入
│   │   ├── orion.py                # Orion 平台
│   │   ├── trail.py                # Trail 平台
│   │   └── voyager_proxy.py        # Voyager 代理
│   │
│   ├── services/                   # 业务服务层
│   │   ├── embedding_service.py    # Embedding 服务
│   │   └── model_offloading.py     # 模型卸载策略
│   │
│   ├── tools/                      # 工具封装
│   │   ├── resources/              # 多模态资源抽象
│   │   │   ├── image.py            # 图像资源
│   │   │   ├── video.py            # 视频资源
│   │   │   ├── table.py            # 表格资源
│   │   │   └── pydantic_ai.py      # Pydantic AI Tool 基类
│   │   └── session.py              # 会话管理
│   │
│   └── utils/                      # 通用工具
│       ├── s3_utils.py             # S3 工具
│       ├── async_utils.py          # 异步工具
│       ├── torch_utils.py          # PyTorch 工具
│       └── llm_utils.py            # LLM 工具
│
├── scripts/                        # 脚本集合
│   ├── activation/                 # 环境激活脚本
│   ├── model-serving/              # vLLM 模型服务脚本
│   ├── ofs-mount.sh                # 云存储挂载
│   └── utils.sh                    # 工具函数
│
├── tests/                          # 单元测试
├── models/                         # 非标准模型接入（预留）
├── pyproject.toml                  # Pixi 配置和依赖
└── litellm.yaml                    # LiteLLM 模型路由配置
```

## 环境管理

### 可用环境

| 环境 | 用途 | 命令 |
|------|------|------|
| `default` | 默认开发环境 | `pixi shell` |
| `vllm` | VLLM 推理环境 | `pixi shell -e vllm` |
| `voyager` | Voyager 平台环境 | `pixi shell -e voyager` |
| `opencv` | OpenCV 图像处理 | `pixi shell -e opencv` |
| `litellm` | 模型路由服务 | `pixi shell -e litellm` |

### 常用命令

```bash
# 安装所有环境
pixi install

# 运行特定环境的命令
pixi run -e vllm -- python script.py

# 进入特定环境 shell
pixi shell -e vllm

# 运行测试
pixi run etest

# 代码格式化
pixi run format

# 代码检查
pixi run lint-ruff

# 启动模型路由
pixi run model-router
```

## 模型服务

项目包含多种模型服务启动脚本；以 `scripts/model-serving/` 当前实际存在的脚本为准：

```bash
# Qwen 系列
sh scripts/model-serving/vllm-serve-qwen3_32b.sh
sh scripts/model-serving/vllm-serve-qwen3_vl_30b_a3b.sh
# Qwen3-Omni 当前在仓库里按 image-only / text-output 的受限 serve 使用；
# 本地 precompiled wheel 还可能在 Marlin 路径报 PTX toolchain mismatch
sh scripts/model-serving/vllm-serve-qwen3_omni_30b.sh

# Meta / Llama 系列
# 当前 generic transformers multimodal backend 仍不稳定，暂不作为稳定 serve 正例
sh scripts/model-serving/vllm-serve-llama_3.2_11b_vision.sh

# Moonshot / Kimi 系列
sh scripts/model-serving/vllm-serve-kimi_vl_a3b.sh

# Keye 系列
sh scripts/model-serving/vllm-serve-keye_vl_1.5_8b.sh

# Gemma 系列
sh scripts/model-serving/vllm-serve-gemma_4_26b_a4b.sh
sh scripts/model-serving/vllm-serve-gemma_4_31b.sh
sh scripts/model-serving/vllm-serve-gemma_4_e4b.sh

# ERNIE 系列
# PT 卡未明确声明 vLLM backend support；参考 models/inference_ernie_45_vl.py

# Valley 系列
# 当前仓库环境下 vLLM 会报 `model type valley` 未识别；参考 models/inference_valley_eagle_7b.py

# GLM 系列
sh scripts/model-serving/vllm-serve-glm_4.6v.sh

# LLaVA 系列
sh scripts/model-serving/vllm-serve-llava_next_34b.sh
sh scripts/model-serving/vllm-serve-llava_next_72b.sh

# InternVL 系列
# InternVL3.5-38B-Flash 当前在仓库两套 vLLM 环境下都不作为稳定 serve 入口：
# raw video 输入不稳，Flash 权重加载还会遇到 mlp2 结构不匹配
```

## 测试

```bash
# 运行所有测试
pixi run etest

# 运行特定测试
pixi run -e test -- pytest tests/cr_locate_test.py

# 带覆盖率报告
pixi run cov
```

## 开发规范

参见 [CONTRIBUTING.md](CONTRIBUTING.md)

### 关键规范

- **包管理**：使用 Pixi，禁止编写 `requirements.txt`
- **代码风格**：使用 Ruff 进行格式化和检查
- **测试**：必须包含 doctest 和 pytest 测试
- **依赖**：显式声明所有 `import` 的依赖

## 技术栈

- **后端**：FastAPI、Uvicorn
- **前端**：Streamlit
- **模型框架**：PyTorch、Transformers、vLLM
- **数据处理**：Apache Arrow、Pandas、NumPy
- **环境管理**：Pixi + Micromamba
- **可观测性**：OpenTelemetry、Logfire

## 许可证

[LICENSE](LICENSE)

## 贡献

欢迎提交 Issue 和 Pull Request！

请确保：
1. 代码通过 Ruff 检查
2. 添加必要的测试
3. 更新相关文档

---

## Vibe Watcher（脚本：scripts/vibe-watcher.sh）

- 用途：在 Vibe Coding 会话期间作为后台守护进程，定时将变更 `git add`/`commit`/`push`，并在会话结束时提供 squash-merge 指南或自动合并。
- 脚本路径：`scripts/vibe-watcher.sh`

### 支持的命令

- `start [-i|--interval N] [-p|--branch-prefix PREFIX] [-f|--fork]`：启动后台 checkpoint（默认间隔 300s）。
- `stop`：停止后台 watcher。
- `status`：查看 watcher 状态与最近 checkpoint。
- `finish [-a|--auto-merge] [-o|--origin ORIGIN_BRANCH] [-- <git-commit-args>]`：停止并生成合并建议，使用 `-a` 可自动 squash-merge 回原分支，`--` 后的参数会透传给 `git commit`（例如 `-- -m "msg"`）。

### 环境变量

- `VIBE_WATCHER_INTERVAL`：覆盖默认间隔（秒），默认 `300`。
- `VIBE_WATCHER_PREFIX`：覆盖分支前缀，默认 `agent/vibe`。
- `VIBE_WATCHER_LOG`：覆盖日志文件路径（建议放在仓库外或加入 `.gitignore`）。

### 注意事项

- 日志文件默认位置为 `<repo-root>/logs/vibe-watcher.log`，建议将该路径加入 `.gitignore` 或修改为仓库外路径，避免被意外提交。
- `finish` 命令会先停止后台 watcher，再进行最终 checkpoint；若 session 状态丢失，请使用 `--origin` 指定源分支以便自动合并。
- 将要传递给 `git commit` 的参数必须通过 `--` 隔开并正确引用（shell 引号）。

### 测试与验证

- 已在隔离临时仓库完成端到端测试（start/status/finish --auto-merge），验证自动 checkpoint、push 以及 auto-merge 流程。
- 测试示例：

```bash
./scripts/vibe-watcher.sh start -i 60 -p agent/vibe -f
./scripts/vibe-watcher.sh status
./scripts/vibe-watcher.sh finish --auto-merge --origin main -- -m "feat: merged"
```

更多细节见任务文档：[docs/kanban/tasks/Vibe%20Coding%20体验优化.md](docs/kanban/tasks/Vibe%20Coding%20体验优化.md)

**维护者**：Nairui Luo <luonairui@didiglobal.com>
