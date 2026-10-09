# CONTRIBUTING

TODO: 移动到 [docs](docs/) 下面

## Code Layout

* **别写任何的 `requirements.txt`** ，代码库涵盖了多平台多环境，我们使用 Pixi 对依赖和环境进行管理，请熟悉 Pixi 的使用方法并编辑 [pyproject.toml](pyproject.toml) 添加依赖
* 缓存目录建议软链：`ln -s ~/mount-env/luonairui/cache/`

## Linting

* FIXME: `tool.ruff.lint.allowed-confusables` 在 VS code 不生效

## Testing

* 提供了 6 个单文件测试命令，位于 `[tool.pixi.feature.test.tasks]` 下面，运行请记得指定 env
* 可以用 VS code 测试扩展对当前激活的环境下可用的测试进行收集和运行
* 还有强大的 Pixi task `etest` 根据每个可测试文件的 shebang 使用正确的环境运行所有测试
* 尽可能编写 doctest，只要它的依赖在 [conftest.py](conftest.py) 中能够满足

### 测试覆盖

* FIXME: 至今不知道增量 coverage 怎么做的，然后是如何与 VS code 测试扩展联动
在 `tool.coverage.report.exclude_lines` 配置不需要被覆盖的行正则

## Dependency

* 请添加显式依赖，就是你 `import` 的那些库，如果他们是可选的（常见于 `except ImportError: ...`），请考虑它存在于什么 feature 下再添加

### 依赖检查工具

* fawltydeps
* pipreqs

### pyproject.toml

主要环境：

* default, prod
* voyager, voyager-dev
* vllm-base, vllm

#### [dependency-groups]

仅包含 `voyager` feature 依赖，这是由 py310 requirements.txt 导入生成的，由于依赖太多，采用白名单方式按需启用

#### pixi feature pypi-options

有 `pypi-dependencies` 务必写上，参考模板：

```toml
[tool.pixi.feature.vllm.pypi-options]
index-url = "https://pypi.tuna.tsinghua.edu.cn/simple/"
# no-binary = ["vlm-triage"]
no-build = true # 如果全部包都有 bdist
# no-build = ["vllm"] # 如果同一 environment 下有一个 feature 的 pypi-dependencis 需要 sdist 安装，就不能用 `no-build = true`，必须写白名单
```

#### pixi feature activation

由 3 部分构成：

* 前置 activation
* local 环境配置 [scripts/activation/local.sh](scripts/activation/local.sh)，会在第一次运行 `pixi run` 时生成，请配置后再次运行以生效
* feature activation

参考模板：

```toml
scripts = [
    "scripts/activation/pre-pixi.sh",
    "scripts/activation/local.sh",
    "scripts/activation/default.sh",
]
```

#### pixi feature tasks

* Pixi shell 内建了 xargs，可能与 GNU 的不兼容，必要时请用 `/usr/bin/xargs`
* Pixi shell/run 对 `Ctrl-Z` 等 terminal 信号支持可能不好，勿折腾
* Pixi tasks cmd 只支持朴素的 `$VAR`，但是可以也应当加引号，如 `--server.port "$TRIAGE_FE_PORT"`
* 使用 [scripts/path2module.sh](scripts/path2module.sh) 进行路径到 Python 模块名转换，如：`ipyp = {cmd = 'ipython --pdb -i -m "$(scripts/path2module.sh "{{ path }}")" --', args = ["path"]}`

## 工具

### LiteLLM

当新增模型时，按下面几个维度添加多条：

* by location: 形如 "@10.152.24.7:8030"
* by name: 形如 "Qwen3-VL"
* by type: 形如 "#VisionModel"

## 提交代码

安装 dcl

```shell
curl -fsSL https://git.xiaojukeji.com/codeinsight/cli-install/raw/master/install.sh | bash
```
