# 日志、跟踪、可观测性

| 属性 | 值 |
| ---- | --- |
| ID | logging-tracing-observability |
| 类型 | task |
| 优先级 | medium |
| 状态 | planning |
| 创建日期 | 2026-04-07 |
| 更新日期 | 2026-05-17 |

## 概述

完善 logfire 日志、链路追踪和可观测性体系，解决 HyperDX 部分功能不可用问题，建立可测试的可观测性基础设施。

## 背景

项目已引入 logfire，但 HyperDX 部分功能不可用，pytest 集成未充分利用，auto_tracing 需要做成 hook 以降低接入成本。

## 范围

**在范围内：**

- logfire pytest 集成（`[tool.pytest] logfire = true`）
- auto_tracing 做成 conftest hook
- capfire fixture 接入现有测试
- SpanKind / 链路语义梳理和文档化

**不在范围内：**

- 不替换 logfire 为其他 APM 方案
- 不修改生产环境部署配置

## 成功指标

| 指标 | 基线 | 目标 | 评价方法 |
| ---- | ---- | ---- | -------- |
| pytest 自动 tracing | 需手动调用 install_auto_tracing | conftest hook 自动生效 | 运行任意测试后 capfire 有 spans |
| capfire 接入数 | 0 | ≥ 3 个测试文件使用 capfire | grep capfire |
| HyperDX 可用性 | 部分不可用 | 核心功能可用 | 手动验证 |

## Iterations

### Iteration 20260407.01

解释

- SpanKind Internal 是什么意思？是logfire/otel枚举值吗？有哪些

	- 回答：SpanKind `Internal` 表示“进程内的本地操作”，即该 span 表示应用内部的一段工作（例如函数调用、内部计算、队列/任务处理等），不是网络请求边界上的客户端或服务端调用。

	- 回答：`SpanKind` 来自 OpenTelemetry（OTel）规范，`logfire` 在语义上沿用这套枚举。OTel 常见的 `SpanKind` 值有：

		- `Internal`：本地内部 span（用于进程内操作）
		- `Server`：服务端处理入站请求
		- `Client`：客户端发起出站请求
		- `Producer`：消息/事件的生产者（发消息）
		- `Consumer`：消息/事件的消费者（接收并处理消息）

- pytest-logfire 插件有什么能力，我需要手动 install_auto_tracing 吗

	- 回答：本仓库的依赖清单（`pyproject.toml`）只包含 `logfire`，并未安装名为 `pytest-logfire` 的 pytest 插件。因此当前项目里通过 `conftest.py` 显式调用 `logfire.install_auto_tracing(...)` 是必需的，用来在测试/运行时为指定包路径自动开启追踪（自动为被观测的函数/请求创建 spans）。`min_duration` 参数用于忽略短于阈值的 span，减少噪声。

	- 建议：保留 `conftest.py` 中的调用以确保测试期间能采集到追踪；如果你希望通过 pytest 插件自动完成，也可以自行实现一个简单的 pytest hook（例如在 `pytest_sessionstart` 中调用 `install_auto_tracing`），或在测试运行的入口脚本里做同样的初始化。

## Iteration 20260411.1154

不是 pytest-logfire 插件，是 logfire 的 pytest 集成，参见 https://logfire.dev/docs/instrumentation/pytest/ 和 [tool.pytest]

## Iteration 20260411.1245

- 把总结更新到当前文档
- 解释 capfire 是什么
- 把 auto_tracing 做成 hook

#### logfire 的 pytest 集成能力总结

- 只需在 `pyproject.toml` 的 `[tool.pytest]` 区块加 `logfire = true`，pytest 启动时会自动启用 logfire 的测试集成。
- 测试集成会自动配置 logfire 为测试友好模式（如关闭网络/控制台输出），并提供内存导出器，方便断言。
- 提供 `capfire` fixture（类型为 `CaptureLogfire`），可在测试函数中直接获取所有采集到的 spans、logs、metrics，便于断言和分析。
- 提供 `IncrementalIdGenerator`、`TimeGenerator` 等工具，生成可预测的 trace/span id 和时间戳，方便测试断言。
- 但不会自动为你的业务代码批量埋点，仍需在入口或 hook 里调用 `logfire.install_auto_tracing(...)`。

#### capfire 是什么

`capfire` 是 logfire pytest 集成自动注入的 fixture，类型为 `CaptureLogfire`，包含：

- `exporter`：可读取所有采集到的 span（链路追踪）
- `metrics_reader`：可读取所有采集到的 metrics（指标）
- `log_exporter`：可读取所有采集到的 log（日志）

常见用法：

```python
def test_something(capfire):
	... # 业务代码
	spans = capfire.exporter.get_finished_spans()
	logs = capfire.log_exporter.get_finished_logs()
	metrics = capfire.get_collected_metrics()
	assert ... # 断言内容
```

详见 logfire.testing 源码和官方文档。

#### auto_tracing 做成 hook

推荐在 `conftest.py` 里实现如下 hook，自动为所有测试 session 安装 auto_tracing：

```python
def pytest_sessionstart(session):
	import logfire
	logfire.install_auto_tracing([
		'apps', 'lib', 'models', 'tests'
	], min_duration=float(os.getenv("LOGFIRE_AUTO_TRACING_MIN_DURATION", 0.01)))
```

这样无需每次都手动调用，且能保证所有测试 session 都自动埋点。


## Iteration 20260411.2315

可是原版 conftest 已经具备同样效果

开始解释，无论有任何疑惑或者规划顺利完成，最后都要用 ask_question 向我确认下一步行动（如：是否可以开始行动），务必带上自由输入的选项。

## Iteration 20260412.1337

现在处理 docs/kanban/tasks/Logging Tracing Observibility.md，请先切换上下文到当前文件，分析当前文件的内容和结构，理解当前文件的作用和与其他文件的关系，再进行后续的解释、规划或者编码。
模块、函数 首次导入调用时间较长，min_duration 能排除吗，是否可以放在所有 import 之后
查询资料或本地测试，给出一个最优 min_duration 默认值，既能排除首次耗时时的 span，又能覆盖绝大多数业务函数的 span。
开始解释，解释完成用 ask_question 向我确认下一步行动（如：是否可以开始编码），务必带上自由输入的选项。

## Iteration 20260412.1412

现在来 review lib/utils/streamlit_utils.py，请先切换上下文到当前文件，分析当前文件的内容和结构，理解当前文件的作用和与其他文件的关系，再进行后续的解释、规划或者编码。
review class SpanProcessor 这个类
大问题其实在这里：有多个 streamlit 会话时，所有 log 会定向到最新 mount 的那一个
增加一个功能，按 span/trace id 等，可自动手动在 mount 时指定，根据 id 和 script_run_ctx 对应关系，路由到正确的 streamlit 页面上
开始规划，无论有任何疑惑或者规划顺利完成，最后都要用 ask_question 向我确认下一步行动（如：是否可以开始行动），务必带上自由输入的选项。

## Iteration 20260412.1418

- auto claim 是什么
- 是直接用 script_run_ctx 对象标识还是 session_id ？
- 听上去不需要 mount，直接在 on_start 自动添加路由就好了
- 对了，有自动添加，哪如何自动删除呢
开始解释，解释完成用 ask_question 向我确认下一步行动（如：是否可以开始编码），务必带上自由输入的选项。

## Iteration 20260412.1424

- 哪怕局部 rerun script_run_ctx 也会变化？那意味着 渲染的控件都会失效？原代码好像没有这样的bug
- 采用 unmount 代替原 shutdown 是吧？
开始解释，解释完成用 ask_question 向我确认下一步行动（如：是否可以开始编码），务必带上自由输入的选项。

## Iteration 20260412.1428

为 `SpanProcessor` 增加多 session 路由能力，支持多用户并发 Streamlit 应用：

**设计**：

- 新增 `_Session` dataclass，包含 `ctx`、`container`、`role`、`spans`
- `_sessions: dict[str, _Session]`（session_id → 状态），替代原单一 `_script_run_ctx`
- `_routes: dict[int, str]`（trace_id → session_id），用于路由
- 路由规则：root span（`parent_context is None`）在 Streamlit 线程中自动认领 trace_id；后续所有同 trace 的 span 路由到同一 session；root span 结束时自动清理路由
- 新增 `unmount(session_id=None)` 手动移除 session 并清理其所有路由
- 保留 `shutdown()` 作为 OTel 接口，清理全部状态
- `is_mounted` 改为只读 property，返回 `bool(self._sessions)`


好的，先更新规则：

> 用户发起 feature / task 的 iteration，务必把本轮对话的结论添加到相应的文档中，如果任务方向有变化，则还要更新文档中的相关部分，保持文档的时效性和准确性。
> 开发前务必阅读 [coding-guidelines](../rules/coding-guidelines.md)，严格按照规范编码
> 无论遭遇任何问题或者顺利完成，最后都要用 ask_question 向我确认下一步行动（如：是否需要我 review 改动），务必带上自由输入的选项。

开始开发，无论遭遇难以解决的问题或者任务顺利完成，最后都要用 ask_question 向我确认下一步行动（如：是否需要我 review 改动），务必带上自由输入的选项。

## Iteration 20260414.1138

慎用 logfire.install_auto_tracing logfire.LogfireLoggingHandler：

- install_auto_tracing 会注入所有函数，min_duration 无法跳过首次 warmup 导致的长耗时 span，建议只在功能测试时使用
- logfire.LogfireLoggingHandler 会将参数按 pydantic 序列化发送，隐式性能开销巨大

TODO: 优化 logfire 在项目中的使用

- 非测试环境禁用 install_auto_tracing
- 根据实际测试指导（profile-guided）添加 instrument
