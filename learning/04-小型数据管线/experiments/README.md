# 04 实验说明

[返回学习笔记](../04-小型数据管线.md)

> 2026-10-02：04 入门阶段已收尾。以下命令作为记录与可选扩展保留，未执行的合格输入管线和复跑不计为已完成。

## 已有文件

- [基准输入](input.jsonl)：A–E，共 5 条。
- [异常输入](input_error.jsonl)：A–F，共 6 条；前五条与基准一致，F 引用不存在的图片。手工拆分已完成，不代表自动预检已完成。
- [两步配置](config-shape-dedup.yaml)：当前实际顺序为去重 → 尺寸过滤，读取基准输入。
- [单步配置](config-dedup-only.yaml)：只去重，读取基准输入。配置头部的旧注释不准确，以实际 process、export_path 和下面命令为准。

## 已有运行方式

从项目根目录进入源码目录后执行；两条命令代表两个独立实验，并非要求现在全部重跑。

```bash
cd data-juicer
.venv/bin/dj-process --config "../learning/04-小型数据管线/experiments/config-shape-dedup.yaml"
.venv/bin/dj-process --config "../learning/04-小型数据管线/experiments/config-dedup-only.yaml"
```

配置位置：[两步配置](config-shape-dedup.yaml) · [单步配置](config-dedup-only.yaml)。

注意：相对路径以运行工作目录为基准。单步配置当前仍指定隐藏目录 `.outputs`；此前单步结果已在对话核对为 A、B、C，但原结果文件本次检查已不存在。此处不补造输出或擅自重跑。

## 异常实验与后续

异常实验发生在拆分之前，当时两步配置所指的输入内含 F；当前两步配置只会读取恢复后的五条基准输入，**不会自动读取异常输入**。历史异常证据与数量解释见 [笔记第 4.4 节](../04-小型数据管线.md#44-已完成实验记录助手整理2026-10-02)。

预检脚本与实测已补齐，使用方式见下节。按 [笔记收尾说明](../04-小型数据管线.md#6-阶段收尾与验收范围)，后续运行改为可选扩展，不再作为当前待办。后续复跑需使用独立输出目录，避免覆盖历史证据；不要修改已有输入或历史备份配置来冒充原始运行。

## 预检与可选后续管线

脚本：[precheck.py](precheck.py)。输入：[异常输入](input_error.jsonl)。助手已运行的输出：[合格清单](precheck-20261002/valid.jsonl)、[异常清单](precheck-20261002/invalid.jsonl)、[摘要](precheck-20261002/summary.json)。结果为 6 条分为 5 条合格与 1 条异常，原始输入未修改。

从项目根目录运行预检；下面使用新目录，避免覆盖助手已保存的结果。若该目录也已存在，换一个新名称。

```bash
data-juicer/.venv/bin/python learning/04-小型数据管线/experiments/precheck.py --input learning/04-小型数据管线/experiments/input_error.jsonl --output-dir learning/04-小型数据管线/experiments/precheck-manual-01
```

这只是读取与解码校验，不做尺寸过滤、去重，也不自动运行管线。相对媒体路径按输入清单目录解析；当前输入使用绝对路径。

接下来使用 [合格输入配置](config-prechecked.yaml)，它读取助手已生成的合格清单，导出到独立位置，不覆盖旧实验。本步骤尚未运行。从项目根目录执行：

```bash
cd data-juicer
.venv/bin/dj-process --config "../learning/04-小型数据管线/experiments/config-prechecked.yaml"
```

若希望使用自己新跑的预检结果，请先将这份配置的 `dataset_path` 指向对应合格清单，并使用新的导出位置。配置中的现有输出位置重复运行会被覆盖。
