# Cooper 平台接入

| 属性 | 值 |
| ---- | --- |
| ID | cooper-platform-integration |
| 类型 | feature |
| 优先级 | high |
| 状态 | done |
| 创建日期 | 2026-04-08 |
| 更新日期 | 2026-05-17 |

## 概述

通过 Cooper Open API 实现标注数据自动上传和发版数据自动下载，减少手动操作。

## 背景

`lib/platforms/ep/cooper.py` 有现成代码，需要按项目规范重构（async、httpx、logging、schema、typing）。

## 范围

**在范围内：**

- 上传文档（支持 file-object / renamed / bytes）
- 列出目录文件
- 下载文档
- token 安全管理（团队 token 存代码，个人 token 走 `local.sh`）
- 可测试（在线服务，不 mock）、可观测（logfire）

**不在范围内：**

- 不涉及 Cooper 权限申请流程（那是人工操作）

## 成功指标

| 指标 | 基线 | 目标 | 评价方法 |
| ---- | ---- | ---- | -------- |
| 上传功能 | — | 3 种 file type × 3 种 data_path 全通过 | 参数化测试 9 用例 |
| 下载功能 | — | 下载后文件内容一致 | 集成测试 |
| 安全性 | token 硬编码 | 个人 token 仅在 `local.sh` | 代码审查 |

## 验证方案

### 评价方法

- 在线服务测试（group_id=2199094698523, parent_id=2207369729546），不 mock
- `COOPER_USERNAME` 从 `os.environ` 读取，不 skip

## 用户故事

- 作为数据标注管理员，我希望能够自动将标注数据上传到 Cooper 平台，减少手动操作
- 作为开发者，我希望能够从 Cooper 自动下载发版数据，实现数据同步自动化

## 背景

lib/platforms/ep/cooper.py 提供了一些现成代码。

Cooper Open API 关键信息：

1. **Api Token 申请**：申请人提交申请，经过直接上级和 Cooper 团队审批。申请链接：https://bpm.didichuxing.com/process/form/bykey/cooper_open_api?tenantId=Cooper
2. **公共参数**：所有公共参数应放在 HTTP 请求头（Header）中，包括鉴权 Token（Apikey，注意大小写）和用户名（username）
3. **服务环境**：线上环境 API 地址：http://api-kylin.intra.xiaojukeji.com/EP_CLOUD_DISK_oe_openapi_cooper_server_prod
4. **接口示例**：获取文件列表接口：`/openapi/v1/files`，通过 GET 方法调用，需要提供 `resource_id`（文件夹ID）和 `group_id`（团队ID或空间ID）作为查询参数

## 需求详情

### 功能需求

1. 支持标注数据自动上传到 Cooper
2. 支持发版数据从 Cooper 自动下载

### 技术需求

1. 提取代码功能点：上传文档、list 目录、下载文档
2. 按项目规范重构代码：async、httpx、logging、validation/schema、typing、path naming 等
3. 安全性：团队 token 可以留在代码里，个人 token 必须移走，推荐 pre-pixi.sh local.sh 设置
4. 可测试
5. 可观测

## 相关文件

- `lib/platforms/ep/cooper.py` — Cooper 平台集成代码

## 验证方案

1. 使用在线服务测试（不要 mock）
2. 用 group_id=2199094698523 parent_id=2207369729546 测试
3. 用测试目录下的数据验证 upload 和 list
4. 不要 skip COOPER_USERNAME，环境中一定会提供，用 os.environ["COOPER_USERNAME"]

## Iterations

### Iteration 20260408.01

- 提取代码功能点：上传文档、list目录、下载文档
- 按项目规范重构代码：async、httpx、logging、validation/schema、typing、path naming等
- 安全性：团队token可以留在代码里，个人token必须移走，推荐 pre-pixi.sh local.sh 设置
- 可测试
- 可观测

最后用 ask_question 向我确认下一步行动（如：review代码），务必带上自由输入的选项。

### Iteration 20260409.0001

Cooper 用在线服务测，不要 mock。用 `group_id=2199094698523 parent_id=2207369729546` 测试。

### Iteration 20260409.1633

用测试目录下的数据验证 upload 和 list；`COOPER_USERNAME` 必须从 `os.environ` 读取，不可 skip。

### Iteration 20260409.1642

更新 docstring（测试函数加 `验证` section）和测试。

### Iteration 20260411.1249

将上传测试参数化：

- `test_upload_file` 按 `case`（file-object / renamed / bytes）× `data_path`（3 种文件）二维参数化，共 9 个用例
- `test_upload_file_multi` 独立测试多文件顺序上传

结论：Cooper API 每次请求只接受一个文件，多文件需多次调用。

### Iteration 20260411.1310

将接口重命名为 `upload_file`：

- 签名：`upload_file(group_id, parent_id, file: FileTypes) -> FileInfo`
- 返回单个 `FileInfo`（非列表）
- 实现中验证 `res["data"]` 长度为 1，否则 `raise RuntimeError`

## 总结

已完成 Cooper 平台接入功能，包括：

1. **文档上传** — `CooperClient.upload_file(group_id, parent_id, file: FileTypes) -> FileInfo`，支持裸文件对象、命名文件对象、内存 bytes 三种形式
2. **目录列表** — `CooperClient.list_dir(group_id, resource_id) -> list[FileInfo]`
3. **下载链接** — `CooperClient.get_download_url(group_id, resource_id) -> str`，多文件时 Cooper 返回 ZIP 包链接
4. **协作文档导出** — `CooperClient.export_cooperate(resource_id, dest) -> Path`，流式下载 Cooper 在线文档到本地文件
5. **Web 链接** — `get_dirview_url(group_id, resource_id) -> str` 模块级函数

代码遵循项目规范：async/httpx、tenacity 重试、pydantic 模型校验、完整 docstring 和类型注解。测试全部使用真实 Cooper 在线服务（无 mock），10 个用例全通过。

## Iteration 20260415.2029

新增协作文档导出下载功能：

- 新增 `CooperClient.export_cooperate(resource_id, dest)` — 流式导出 Cooper 在线文档到本地文件
- 签名：`export_cooperate(resource_id: int, dest: PathLike | str) -> Path`
- 使用 `httpx.stream()` 流式写入，适合大文件
- 自动创建目标目录（`dest.parent.mkdir(parents=True, exist_ok=True)`）
- 新增模块级便捷函数 `export_cooperate()`
- 新增集成测试 `test_export_cooperate`，使用 `resource_id=2207460511730`（Word 文档），验证 PK (OOXML) 文件头

## Iteration 20260415.2056

- 做两层封装，一层返回 async stream object，一层直接保存到文件
- 将 lib/platforms/ep/cooper.py 改造成 cli 工具（注意 __main__ 和 shebang），提供命令行文件操作
- 完善 lib/platforms/ep/cooper.py 中的 todo，支持通过 URL 直接指定资源（如 `cooper export https://cooper.didichuxing.com/team-file/2199094698523/2207445719119`）

## Iteration 20260415.2251

忽略前面的工作，现在处理 docs/kanban/features/Cooper 平台接入.md，请先切换上下文到当前文件，分析当前文件的内容和结构，理解当前文件的作用和与其他文件的关系，再进行后续的解释、规划或者编码。

- /create-skill 创建 skill，指导 agent 通过 cooper cli(pixi run cooper export) + markitdown mcp(pixi exec markitdown-mcp-server) 进行 cooper 文档读取
- 可用的转换工具有，先加进去，赛马看看哪个更好用：
	* pixi exec markitdown-mcp-server
	* uvx markitdown-mcp==0.0.1a4
	* pixi exec markitdown
	* pixi exec mammoth
- 两种 url 分开 parse，作为不同用途
- 对 download，parse_cooper_url 的 url 一定是目录，下载目录可行吗？你测试过吗？

开始行动，无论遭遇难以解决的问题或者任务顺利完成，最后都要用 ask_question 向我确认下一步行动（如：是否需要我 review 改动），务必带上自由输入的选项。

创建 `reading-cooper-documents` skill，指导 Agent 通过 Cooper CLI + markitdown 工具链读取 Cooper 文档：

- 区分两种 URL 类型：docs2（协作文档，用 `export`）和 team-file（团队文件，用 `download`）
- 四种转换工具：markitdown CLI、mammoth、markitdown-mcp-server、uvx markitdown-mcp
- team-file URL 的 resource_id 通常指向目录，download 会打包为 ZIP

关于 download 目录：`get_download_url` 的 doctest 显示传入目录 resource_id 时 Cooper 返回 `download.zip`，说明 API 支持目录下载。但未做完整端到端测试。

## Iteration 20260415.1631

- `lib/platforms/ep/cooper.py` 的 `download` / `export` 新增 stdout 输出支持：目标路径传 `-` 时直接写入 `sys.stdout.buffer`
- CLI 在 stdout 模式下不再额外向 stdout 打印 `{path} ({size} bytes)`，避免破坏 pipe 数据流
- 可直接串联 `markitdown` 的 stdin 模式，例如：
  `pixi run cooper export - --url https://cooper.didichuxing.com/docs2/document/2207460511730 | pixi exec markitdown -x docx > /tmp/report.md`

## Iteration 20260415.1705

- 已验证 `cooper export -` 的 stdout 字节流与导出到文件的内容一致，pipe 数据流没有被 CLI 状态文本污染
- 某个 Cooper docs2 导出的 `.docx` 在 `markitdown` / `mammoth` 中都会报 `KeyError: 'w:type'`
- 根因定位到 `word/styles.xml`：多条 `shimo*` 自定义 `<w:style>` 缺失 `w:type`
- 已验证的绕过方式：给缺失样式补 `w:type="paragraph"` 后重新打包，`markitdown` 可正常转换

## Iteration 20260415.1720

- 在 `cooper` CLI 中新增 `normalize-docx` 子命令，默认 stdin → stdout，可直接接在 `export -` 和 `markitdown` 之间
- 新增底层函数 `normalize_styles_xml()` / `normalize_docx_file()`，自动为缺失 `w:type` 的 `<w:style>` 补默认值 `paragraph`
- 新增单元测试覆盖 XML 归一化和 DOCX ZIP 重写逻辑
- 推荐链路：
  `pixi run cooper export - --url https://cooper.didichuxing.com/docs2/document/2207460511730 | pixi run cooper normalize-docx | pixi exec markitdown -x docx > /tmp/report.md`

## Iteration 20260415.1745

- 将 `download_to_file()` / `is_stdout_path()` / `download_to_stdout()` / `download_to_output()` 抽到 `lib/utils/io_utils.py`
- `io_utils.py` 补充 doctest，并新增 `open_binary_input()` / `open_binary_output()` / `ensure_seekable_input()` 统一处理路径、stdio 和非 seekable stdin
- `normalize-docx` 不再走 `bytes -> BytesIO`，改为直接处理文件对象；stdin 场景通过 `SpooledTemporaryFile` 转成 seekable 输入后再交给 `ZipFile`

## Iteration 20260416.0944

- `cooper upload` 新增 stdin 支持：`file_path` 传 `-` 时从 `stdin` 读取上传内容
- 新增 `--name/-n` 选项：stdin 模式下显式指定 multipart 文件名；本地文件模式下可用于覆盖默认文件名
- CLI 上传入口改为复用 `open_binary_input()`，保持本地文件和 stdio 两条路径的一致处理方式
- 新增 `resolve_upload_target()` 单测，覆盖本地路径默认命名、显式重命名以及 stdin 缺少 `--name` 的报错
- 现在可以直接这样用：`cat report.docx | pixi run cooper upload - --name report.docx --url https://cooper.didichuxing.com/team-file/{group_id}/{parent_id}`

## Iteration 20260416.1458

- 参考 `lib/platforms/ep/cooper.py` 的 Typer 结构，把 `lib/utils/s3_utils.py` 也补成了 CLI，支持 `ls`、`put`、`get`、`sign`、`put-sign`
- 复用现有 `pyproject.toml` 任务入口 `pixi run s3-cli`，不再新增第二套命令名
- `put` / `put-sign` 默认按原始 `object_name` 上传；只有显式传入 `--app-name` 和 `--prefix` 时，才会启用 `prefix/app_name/YYYYMM/object_name` 分区规则
- 当前只有 `ls` 支持递归；`put` / `get` / `sign` / `put-sign` 仍然是单对象命令，不支持 batch/递归
- 按要求把 CLI 相关 Typer 定义收回到 `__main__ -> main()` 中，模块顶层只保留可复用的核心函数
- 新增 `tests/s3_utils_test.py`，覆盖对象名解析、响应头构造和上传/下载/签名核心函数
- `README.md` 已补充 `s3-cli` 使用说明、stdin/stdout 管道示例和分区上传示例
