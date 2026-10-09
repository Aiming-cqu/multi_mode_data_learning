## Quick orientation (what this repo is)

IMPORTANT NOTE:

> **📋 每次迭代必须先查阅看板！** 项目看板位于 `docs/kanban/`，包含所有 feature 和 task 的当前状态（进行中/待开始/完成）。开发前务必先看板确认当前优先级和进展。
> 用户发起 feature / task 的 iteration，务必把本轮对话的结论添加到相应的看板文档（`docs/kanban/features/<名称>.md` 或 `docs/kanban/tasks/<名称>.md`）中，如果任务方向有变化，则还要更新文档中的相关部分，保持看板的时效性和准确性。
> 开发前务必阅读 [coding-guidelines](../rules/coding-guidelines.md)，严格按照规范编码
> 无论遭遇任何问题或者顺利完成，最后都要用 `ask_user` 向我确认下一步行动（如：是否需要我 review 改动），务必带上自由输入的选项。

This repository contains tooling and example agents for visual-language model (VLM) based triage of autonomous driving issues. It combines agents, multi-modal resources, and model inference to analyze road test scenarios, simulation diffs, and simulation anomalies.

Key components:
- `apps/*/` — application entries: CLI, FastAPI servers, and Streamlit frontends for use cases like scenario analysis, simulation diff analysis, and anomaly detection
- `lib/algorithms/` — core algorithms: embedding extraction, CV similarity, conflict locator, max-coverage sampling
- `lib/tools/resources/` — resource and storage abstractions (`Image`, `Video`, `Table`, `FileStorage`, `HTTPStorage`) and pydantic_ai toolsets
- `lib/tools/data_providers/` — converters from issue/trip IDs to `Resource` objects (if present)
- `lib/utils/llm_utils.py` — model selection and provider setup helpers
- `lib/services/` — business services (embedding service, model offloading strategies)
- `lib/platforms/` — integrations with Orion, Trail, Voyager platforms

## Build, test, and lint commands

All commands use Pixi for environment management. These are defined in `pyproject.toml` under `[tool.pixi.tasks]` and feature-specific `[tool.pixi.feature.*.tasks]`.

### Running tests
- `pixi run etest` — Run all tests with correct environment per file (reads shebang). Includes coverage. **Use this for full test suite.**
- `pixi run test` — Run pytest in current environment with coverage
- `pixi run testp -- <path>` — Run pytest on specific Python module by file path (auto-converts to module name)
- `pixi run testm -- <module>` — Run pytest on specific module by module name
- `pixi run pdbtest` — Run pytest with IPython debugger, stops at failures
- `pixi run -e test -- pytest tests/some_test.py::TestClass::test_method` — Run single test in test environment

### Code quality
- `pixi run format` — Format code with Ruff
- `pixi run lint-ruff` — Lint with Ruff (checks)
- `pixi run lint-dcl` — Lint with DCL (internal tool)
- `pixi run lint-ty` — Type check with Ty

### Coverage reports
- `pixi run cov` — Full coverage pipeline: erase, run etest, combine, report. **Use for coverage reports.**
- `pixi run coverase` — Erase previous coverage data
- `pixi run covcombine` — Combine coverage from multiple runs
- `pixi run covreport` — Display coverage report

## Multi-environment setup

The project uses multiple specialized Pixi environments for different use cases. Understanding which environment to use prevents dependency conflicts.

### Core environments

| Environment | Purpose | Activate | Use when |
|-------------|---------|----------|----------|
| `default` | General development | `pixi shell` | Default development, running most scripts |
| `dev` | Development tools (ruff, type checking) | `pixi shell -e dev` | Linting, formatting, debugging |
| `test` | Testing (pytest, coverage) | `pixi shell -e test` | Running tests with coverage |
| `prod` | Production dependencies | - | Deployment (not typically used locally) |

### Specialized environments

| Environment | Purpose | Activate | Use when |
|-------------|---------|----------|----------|
| `vllm` | VLLM model inference | `pixi shell -e vllm` | Running large language models locally (Qwen, GLM, LLaVA) |
| `vllm-build` | Building VLLM from source | - | Custom VLLM builds (rare) |
| `opencv` | OpenCV image processing | `pixi shell -e opencv` | Running CV similarity API, image processing algorithms |
| `voyager` | Voyager platform integration | `pixi shell -e voyager` | Working with Voyager APIs and data providers |
| `litellm` | LiteLLM model routing service | `pixi shell -e litellm` | Running model router (multi-model endpoint) |
| `notebook` | Jupyter notebooks | `pixi shell -e notebook` | Interactive data exploration, prototyping |

### Environment activation scripts

Each environment runs activation scripts in order:
1. `scripts/activation/pre-pixi.sh` — Setup before Pixi
2. `scripts/activation/local.sh` — Local machine-specific config (auto-generated; edit this for secrets, local paths)
3. Feature-specific script (e.g., `scripts/activation/default.sh` for default environment)

### Running commands in specific environments
```bash
# One-off command in vllm environment
pixi run -e vllm -- python apps/embedding_api/main.py

# Interactive shell in opencv environment
pixi shell -e opencv

# Run test in vllm environment (for tests that need vllm)
pixi run -e vllm -- pytest tests/embedding_test.py
```

### vLLM / Pixi 排障止损规则（避免重复踩坑）

- **`vllm` / `vllm-base` 安装或环境更新超时**：同一命令最多重试 2 次（且参数不变时不应无限重试）。仍失败则立即记录“命令 + 错误 + 时间点 + 当前网络/缓存状态”为 blocker，并切换到不依赖该环境的工作（代码/文档/测试）。
- **vLLM 启动显存失败（如 free memory 不足）**：先快速确认 `nvidia-smi` 空闲显存，再降低 `gpu_memory_utilization`、并发或模型规模；若仍无法启动，直接标记“当前机器资源不足”，不要反复拉起同配置。
- **模型兼容性失败（CLIP / SigLIP / DINO 等）**：出现 `get_input_embeddings` 缺失、架构不支持、模型初始化被拦截等报错时，按“模型不兼容 vLLM 当前能力”处理，记录报错并停止硬试，改走 HF/Transformers 路径或更换模型。
- **阻塞升级标准**：命中“环境超时 / 显存不足 / 架构不支持”任一类问题且无新变量可尝试时，必须早停并上报，不做无效重复安装。
- **命令习惯（减少浪费）**：优先 `pixi run -e vllm -- <cmd>` 做一次性验证；仅在需要多次执行时再 `pixi shell -e vllm`。实验命令优先用现有 `pyproject.toml` tasks，避免现场拼长命令导致参数漂移。

### 实验工具约定（experiments）

- `lib/utils/experiments.py` 以 `PROJECT_ROOT` 环境变量为项目根目录来源；缺失时才回退到路径推断。
- 一次实验统一使用多候选模式：`baseline + candidates`（即便只对比一个候选，也放在 candidates 下）。
- 建议统一通过 `pixi run exp -- <subcommand>` 调用实验管理 CLI，避免维护多套入口。

## Agent development

Agents use `pydantic_ai` with `Agent`, `Deps`, and `RunContext` pattern. See [coding-guidelines.md](../rules/coding-guidelines.md) for detailed examples.

Key concepts:
- **Deps dataclass** — Declares dependencies (session_id, model clients, services)
- **Tools** — Use `@wrap_transformer` decorator with `FunctionToolset` pattern
- **Error handling** — Use `ModelRetry` for transient failures
- **Instrumentation** — Use `logfire` for observability

## Resource and storage abstraction

Resources (Image, Video, Table) with storage abstractions for local files, HTTP URLs, cloud storage.

Key patterns:
- Always use `session_context(session=...)` when accessing resources
- Resource IDs are human-readable strings
- Resources expose methods like `get_url()`, frame extraction, etc.

See example applications: `apps/aurora_scenario_labeling/`, `apps/visual_cr_locator_api/`

## Application development

Three app types: CLI, FastAPI, Streamlit. Standard structure:
```
apps/my_app/
├── main.py      # Entry point
├── agent.py     # Agent definitions
├── deps.py      # Dependencies
├── tools.py     # Tool definitions
└── schemas.py   # I/O schemas
```

See [coding-guidelines.md](../rules/coding-guidelines.md) for examples and detailed patterns.

## Working Principles for Copilot (沟通、思考、执行、质量、任务管理)

### 沟通 (Communication)

- **全部使用中文回复** — All responses in Chinese to match project context
- **需求模糊时先澄清** — When requirements are unclear, clarify first instead of making assumptions

### 思考 (Thinking)

- **第一性原理** — Start from original requirements; never assume users know everything
- **目标不清先对论** — Stop and discuss when motivation and goals are unclear
- **路径不优主动建议** — Proactively suggest more efficient paths when discovered
- **多想少动** — Plan and think before acting; decide first, then move

### 执行 (Execution)

- **非平凡任务进计划模式** — Use plan mode for 3+ step tasks or those involving multiple architectural decisions
- **写代码前先描述方案** — Describe approach before coding; wait for approval
- **超3个文件先拆分** — Break down changes to 3+ files into smaller tasks with clear descriptions
- **使用子智能体** — Delegate complex tasks, research, and parallel analysis to sub-agents; keep main context clean
- **测试驱动修复** — For bugs: write a test that reproduces it first, then fix
- **自主 Bug 修复** — Fix bugs directly; don't require hand-holding

### 质量 (Quality)

- **不推崇兼容性代码** — Don't add compatibility shims unless explicitly required
- **不临时修复** — Always find and fix the root cause
- **追求优雅** — For non-trivial changes, ask: "Is there a more elegant way?" Avoid over-engineering simple fixes
- **完成即验证** — After completing work, ask: "Would a senior engineer approve this?"
- **列出边缘情况** — After writing code, identify and think through potential edge cases

### 任务管理 (Task Management)

- **📋 看板驱动** — `docs/kanban/README.md` 是项目任务总览，**每次开始工作前必须先查阅看板**，了解当前状态和优先级
- **更新看板** — 每次 iteration 结束后，必须向对应的看板卡片 `docs/kanban/features/<名称>.md` 或 `docs/kanban/tasks/<名称>.md` 追加本轮结论，保持状态同步
- **先计划** — Write to plan.md first with options (use [[PLAN]] mode)
- **验证计划** — Get confirmation before implementing
- **追踪进度** — Incrementally mark tasks complete
- **记录结果** — Add review section to plan.md after completion
- **记录教训** — Update lessons.md after implementing fixes

### 核心原则 (Core Principle)

**多想少动·知错即改·往正确的方向走**
*Think more, do less. Correct mistakes quickly. Move in the right direction.*

---

## Project-specific conventions & patterns

### Coding standards

- **Type hints**: Use `from __future__ import annotations` and full type hints for all functions
- **Docstrings**: Use doctest in docstrings for examples; pytest will run them as tests
- **Dependencies**: Explicitly declare all imports in `pyproject.toml`; use `pixi add <package>` to add dependencies
- **No requirements.txt**: Pixi manages all dependencies; never create requirements.txt files
- **Shebang**: Add `#!/usr/bin/env -S pixi run -- test` or `-- default` to Python files that should be executable to specify environment

### Logging and observability

- Use `logfire` for instrumentation: `logfire.instrument_pydantic_ai()`, `logfire.instrument_asyncio()`, etc.
- Use context managers: `with logfire.span("operation_name"):`
- Log important state transitions and decisions

### Resource IDs

Resource IDs are human-readable strings, not numeric:
- `issue_12345` — Issue identifier
- `image_scenario_001` — Image within scenario
- `video_simulation_diff_v1_v2` — Simulation diff video
- `table_metrics_batch_5` — Metrics table

This makes logs and traces easier to follow.

### Session scope

Always be explicit about which session owns a resource:
```python
# In multi-session environments (API servers), isolate by session
with session_context(session=request.session_id):
    resources = get_default_resource_repo()
```

## Integration points

See [coding-guidelines.md](../rules/coding-guidelines.md) and project guides for:
- Model provider setup
- Platform integrations (Voyager, Trail, Orion)
- Resource and storage abstractions
- Agent patterns with pydantic_ai

## Further reading

- **README.md** — Project overview and quick start
- **CONTRIBUTING.md** — Code layout and testing strategy
- **docs/rules/coding-guidelines.md** — Detailed coding standards and examples
- **docs/skills/** — Task automation workflows
- **litellm.yaml** — Model routing configuration
