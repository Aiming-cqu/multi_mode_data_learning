# 03-B－min_width: 340 从 YAML 到比较语句的传递过程

> 回答问题：`min_width: 340` 经过哪些站，最后怎样进入 `Filter.get_keep_boolean()` 第 844 行的 `>= / >` 比较？
> 助手整理日期：2026-09-20；源码参考：Data-Juicer `cc914ee`。
> 验证边界：静态核对本地源码，本次未重新运行实验；不代替学习者个人验收。
> 返回：[最小调用链笔记](03-最小调用链.md) · 配套回答：[完整调用图](03-A-实际调用图.md)

## 1. 先给结论：按数值所在的位置，分为 10 站

这里的“10 站”是为了学习而划分的**数据传递站点**，不是说代码只调用了 10 个函数，也不是把 340 复制了 10 次。部分站点只是同一个配置对象换了一个变量名来引用。

```text
① YAML 中的 process → image_shape_filter → min_width: 340
② parser.parse_args() 得到的 cfg 中的配置值
③ 配置收尾后 cfg.process 中的算子参数
④ 执行器持有的 self.cfg.process
⑤ load_ops(process_list) 收到的 process_list
⑥ 循环解包得到的 args['min_width']
⑦ ImageShapeFilter.__init__() 的 min_width 参数
⑧ 当前算子实例的 self.min_width 属性
⑨ get_keep_boolean() 的 min_val 参数
⑩ 第 844 行：val >= min_val（或 val > min_val）
```

本次输入见[配置 A](../02-单算子实验/experiments/config-min-width-340.yaml)。以下假设没有额外命令行或环境变量覆盖这个阈值。

## 2. 逐站说明：谁把 340 交给了谁？

| 站点 | 340 所在的位置 | 发生了什么 | 源码依据 |
|---|---|---|---|
| ① YAML | `process[0].image_shape_filter.min_width` | 配置文件把最小宽度写成数字 `340`；此时只是文件内容，还不是实例属性 | [配置 A 第 8–11 行](../02-单算子实验/experiments/config-min-width-340.yaml#L8-L11) |
| ② 解析结果 | `cfg.process` 中的配置值 | `parser.parse_args(args=args)` 遇到 `--config`，由 `ActionConfigFile` 读取 YAML 并合并配置，结果赋给 `cfg` | [绑定 action 第 107 行](../../data-juicer/data_juicer/config/config.py#L107)、[解析第 894 行](../../data-juicer/data_juicer/config/config.py#L894)、[第三方 action 第 156–158 行](../../data-juicer/.venv/lib/python3.11/site-packages/jsonargparse/_actions.py#L156-L158) |
| ③ 最终配置 | `cfg.process[0]['image_shape_filter']['min_width']` | `init_setup_from_cfg()` 处理公共设置，`update_op_process()` 合并参数、补齐默认值并校验；显式阈值在本配置下仍为 340，最后返回 `cfg` | [配置第 911–914、941 行](../../data-juicer/data_juicer/config/config.py#L911-L941)、[参数合并第 1276–1315 行](../../data-juicer/data_juicer/config/config.py#L1276-L1315) |
| ④ 执行器配置 | `executor.cfg.process`，在方法里写作 `self.cfg.process` | `DefaultExecutor(cfg)` 经父类初始化把传入配置保存到 `self.cfg`；这里不是重新解析 YAML | [入口第 26 行](../../data-juicer/tools/process_data.py#L26)、[执行器第 47 行](../../data-juicer/data_juicer/core/executor/default_executor.py#L47)、[ExecutorBase 第 13 行](../../data-juicer/data_juicer/core/executor/base.py#L13) |
| ⑤ 加载函数参数 | `load_ops()` 中的 `process_list` | `load_ops(self.cfg.process)` 把算子配置列表交给加载函数，函数里把这个列表叫作 `process_list` | [执行器第 178 行](../../data-juicer/data_juicer/core/executor/default_executor.py#L178)、[load_ops 定义第 4 行](../../data-juicer/data_juicer/ops/load.py#L4) |
| ⑥ 当前算子参数 | `args['min_width'] == 340` | 遍历列表，`op_name, args = list(process.items())[0]` 得到算子名和完整参数字典 | [load_ops 第 17–18 行](../../data-juicer/data_juicer/ops/load.py#L17-L18) |
| ⑦ 初始化参数 | `ImageShapeFilter.__init__()` 的局部参数 `min_width` | 查注册表得到类后，用 `(**args)` 创建实例；字典中的键值作为具名参数传入，覆盖签名中的默认值 1 | [load_ops 第 19 行](../../data-juicer/data_juicer/ops/load.py#L19)、[初始化签名第 27–35 行](../../data-juicer/data_juicer/ops/filter/image_shape_filter.py#L27-L35) |
| ⑧ 实例属性 | `op.min_width`，在实例方法中写作 `self.min_width` | `self.min_width = min_width` 把 340 存在当前算子实例上；初始化结束后其他方法仍可访问 | [ImageShapeFilter 第 52 行](../../data-juicer/data_juicer/ops/filter/image_shape_filter.py#L52) |
| ⑨ 判断参数 | `get_keep_boolean()` 的 `min_val` | `process_single()` 调用 `self.get_keep_boolean(w, self.min_width, self.max_width)`：第二个显式参数 340 对应 `min_val` | [算子第 90 行](../../data-juicer/data_juicer/ops/filter/image_shape_filter.py#L90)、[判断函数签名第 841 行](../../data-juicer/data_juicer/ops/base_op.py#L841) |
| ⑩ 比较语句 | `val >= min_val` 或 `val > min_val` | 把真实图片宽度 `val` 与阈值 `min_val=340` 比较；`min_closed_interval` 决定是否允许等于 | [Filter.get_keep_boolean 第 844 行](../../data-juicer/data_juicer/ops/base_op.py#L844) |

**第 ② 站不是整个配置初始化的终点。** 前面还有第一次主要解析、提取算子名，后面还有参数合并和校验；想看读取 YAML 的库内实现，见[完整调用图第 3 节](03-A-实际调用图.md#3-局部图-a只有文件路径yaml-内容怎么进入-cfg)。

## 3. 带数值位置的调用树

下面用调用树标出 ①–⑩ 所在的层级。缩进表示调用或代码块嵌套；同级分支依次执行，`←` 表示返回；`[接收列表]`、`[赋值]` 等是数据操作，不是假想的函数调用。树在目标比较语句处停止，后续返回、其他阈值和导出省略。源码简称见[回答 A 的源码表](03-A-实际调用图.md#1-怎么读下面的图)；第三方库路径见其[配置解析说明](03-A-实际调用图.md#3-局部图-a只有文件路径yaml-内容怎么进入-cfg)。

```text
main()                                                    [entry:18]
│
├─ init_configs()                                         [entry:20]
│  ├─ parser.parse_args(args)                             [config:894；前置解析见回答 A]
│  │  ├─ [库内 ActionConfigFile 调度，省略中间解析层]
│  │  │  └─ apply_config()                                [_actions:103]
│  │  │     ├─ parser.parse_path(value)                   [_actions:156]
│  │  │     │  ├─ read_text / parse_string                [_core:666–674]
│  │  │     │  │  [① 来源] YAML 中的 min_width: 340
│  │  │     │  └─ ← 返回文件配置对象                     [_core:677]
│  │  │     └─ merge_config，合并到当前配置               [_actions:157–158]
│  │  └─ ← [② 解析结果] 返回并赋给 cfg                   [_core:509；config:894]
│  ├─ init_setup_from_cfg(...)                            [config:911]
│  ├─ update_op_process(...)                              [config:914]
│  │  └─ ← [③ 整理后] cfg.process 中的阈值仍是 340       [config:1276–1315、1343]
│  └─ ← 返回 cfg 给 main                                  [config:941]
│
├─ DefaultExecutor(cfg)，创建实例                         [entry:26]
│  └─ DefaultExecutor.__init__()                          [executor:41]
│     └─ super().__init__(cfg)                            [executor:47]
│        └─ [④ 保存引用] self.cfg = cfg                  [executor_base:13]
│
└─ executor.run()                                         [entry:41；定义 executor:139]
   ├─ load_ops(self.cfg.process)                          [executor:178]
   │  ├─ [⑤ 接收列表] 函数里名为 process_list             [load:4]
   │  ├─ [循环] for process in process_list               [load:17]
   │  │  ├─ [⑥ 解包] op_name, args = ...                 [load:18；args 中有 340]
   │  │  ├─ OPERATORS.modules[op_name](**args)             [load:19]
   │  │  │  └─ ImageShapeFilter.__init__(min_width=340, ...) [shape:27–35；⑦ 参数]
   │  │  │     ├─ super().__init__(*args, **kwargs)        [shape:51]
   │  │  │     └─ [⑧ 赋值] self.min_width = min_width     [shape:52]
   │  │  └─ ops.append(新建的实例)                        [load:19]
   │  └─ ← return ops                                     [load:42]
   │
   └─ dataset.process(ops, ...)                           [executor:253；后续导出不展开]
      └─ [循环] 逐个取出 op                              [dataset:289]
         └─ op.run(...)，执行继承的 Filter.run()          [dataset:303；base_op:887]
            ├─ dataset.map(self.compute_stats, ...)       [base_op:889]
            │  └─ ← 返回带真实宽高 stats 的数据集
            └─ new_dataset.filter(self.process, ...)      [base_op:910]
               ├─ [库内回调] self.process 的 wrapper      [base_op:69–71；绑定 815–816]
               │  └─ process_batched()                  [base_op:863–864]
               │     └─ ← 返回内置 map 的惰性迭代器
               └─ [消费迭代器] lambda 调用 process_single() [base_op:864；shape:83]
                  └─ self.get_keep_boolean(w, self.min_width, ...) [shape:90]
                     └─ Filter.get_keep_boolean(...)     [base_op:841]
                        ├─ [⑨ 参数绑定] val=w，min_val=340
                        └─ [⑩ 下限比较] val >= min_val 或 val > min_val [base_op:844]
```

## 4. 三处容易误解的参数传递

### 4.1 args 是一个字典，不是每个阈值对应一个算子

只展示本次 YAML 明写的两个参数时：

```python
op_name = 'image_shape_filter'
args = {'min_width': 340, 'min_height': 1}
```

`**args` 表示展开字典，核心效果相当于：

```python
ImageShapeFilter(min_width=340, min_height=1)
```

实际字典可能还包括配置初始化补齐的公共属性和默认参数。这里的 `args` 是 [`load_ops()` 第 18 行](../../data-juicer/data_juicer/ops/load.py#L18)的局部变量，不是 `init_configs()` 中保存命令行字符串的那个 `args`。

### 4.2 min_width 和 self.min_width 不是同一个名字

```python
def __init__(self, min_width=1, ...):
    super().__init__(...)        # 父类做通用初始化
    self.min_width = min_width   # 局部参数 340 → 实例属性
```

这是[真实初始化代码第 27–52 行](../../data-juicer/data_juicer/ops/filter/image_shape_filter.py#L27-L52)的简化示意，不是可直接执行的完整代码。调用时已经传入 `min_width=340`，因此不会采用默认的 `1`；它是当前初始化方法的明确参数，不在剩余 `**kwargs` 中自动传给父类。

### 4.3 第 90 行如何对应第 841 行的参数？

调用与函数签名分别是：

```python
# ImageShapeFilter.process_single，第 90 行
self.get_keep_boolean(w, self.min_width, self.max_width)

# Filter，第 841 行
def get_keep_boolean(self, val, min_val=None, max_val=None):
    ...
```

通过实例调用方法时，Python 自动传入 `self`；其余参数依位置对应：

| 调用时传入 | 函数内部名字 | 本次含义 |
|---|---|---|
| 当前算子实例，自动传入 | `self` | 仍是同一个 `ImageShapeFilter` 实例 |
| `w` | `val` | 图片的真实宽度，例如 336 或 342 |
| `self.min_width` | `min_val` | 配置阈值 340 |
| `self.max_width` | `max_val` | 宽度上限，本配置没有显式改写它 |

所以最后一站明确是：

```python
# base_op.py 第 844 行，Filter.get_keep_boolean()
res_bool = res_bool and (val >= min_val if self.min_closed_interval else val > min_val)
```

## 5. 真实图片宽度和配置阈值，是两条不同的数据来源

不要把 `compute_stats_single()` 理解成计算 `min_width`：

- **阈值 340**：来自 YAML，沿上面的 10 站进入 `min_val`。
- **图片真实宽度**：[`compute_stats_single()` 第 73–80 行](../../data-juicer/data_juicer/ops/filter/image_shape_filter.py#L73-L80)读图后写进样本 `stats`；[`process_single()` 第 84、92 行](../../data-juicer/data_juicer/ops/filter/image_shape_filter.py#L83-L92)取出各图片的宽度 `w`，再作为 `val` 传入判断函数。

两条数据线直到第 844 行才真正相遇：**真实宽度与配置的最小宽度比较**。

默认 `min_closed_interval=True`，见[父类初始化第 803 行](../../data-juicer/data_juicer/ops/base_op.py#L803)。在没有其他覆盖、没有反转区间的情况下：

| 真实宽度 `val` | 最小阈值 `min_val` | 第 844 行实际比较 | 宽度下限是否通过 |
|---|---|---|---|
| 336 | 340 | `336 >= 340` | 否 |
| 342 | 340 | `342 >= 340` | 是 |
| 340（边界示例，不是新实验记录） | 340 | `340 >= 340` | 是；若改为开区间 `>` 则不通过 |

342 通过的是**最小宽度这一项**；样本最终保留还需要通过宽度上限、高度上下限以及多图情况下的 `any/all` 规则。本次配置 A 的单图实验中，其他尺寸条件满足时，336 宽的 img1 被过滤、342 宽的 img3 被保留；这里是源码解释，不是本次重新运行的实测声明。

## 6. 可以用来复述的一段话

> YAML 中的 `min_width: 340` 被配置解析器读入 `cfg`，经过公共设置和算子参数整理后保存在 `cfg.process`。`DefaultExecutor` 持有这个配置，运行时将 `self.cfg.process` 传给 `load_ops()`。加载函数取出算子名和参数字典，用 `**args` 创建 `ImageShapeFilter` 实例；`__init__()` 把参数保存为 `self.min_width`。处理样本时，`process_single()` 将它传给 `get_keep_boolean()` 的 `min_val`，最终在第 844 行把真实图片宽度与 340 作 `>=` 或 `>` 比较。

这段话是助手提供的参考回答。能否不看文档独立解释每次交接，仍由学习者自行验证。
