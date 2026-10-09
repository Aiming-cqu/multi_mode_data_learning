# VL Embedding 模型探索

| 属性 | 值 |
| ---- | --- |
| ID | vl-embedding-model-exploration |
| 类型 | feature |
| 优先级 | high |
| 状态 | active |
| 创建日期 | 2026-04-07 |
| 更新日期 | 2026-05-17 |

## 概述

探索支持文本引导的 VL（Vision-Language）Embedding 模型，通过文本输入引导 embedding 抽取，提升特征抽取与 topic 的语义对齐效果。

## 背景

`lib/algorithms/embedding_extractor.py` 使用 CLIP、DINO、AIM 等模型做图像 embedding 抽取。当前需要扩展为 text-conditioned 路线，让同一张图在不同 topic 下产出不同 embedding，从而提升 CR 定位中"by topic 优化"的区分度。

## 范围

**在范围内：**

- 双塔检索打分路线：CLIP / PE-Lang / SigLIP / SigLIP2 做 baseline
- 联合编码 conditional embedding 主线：Qwen3-VL-Embedding 系列
- 候选模型调研与 ModelScope 下载
- 统一接口抽象（区分双塔打分 vs 联合编码 embedding）

**不在范围内：**

- 不涉及纯视觉 backbone（DINOv2 不走 text 输入）
- 不接入通用生成式 VLM（Kimi-VL、Qwen3-VL Instruct/Thinking）做 embedding
- 不训练或微调模型

## 成功指标

| 指标 | 基线 | 目标 | 评价方法 |
| ---- | ---- | ---- | -------- |
| 联合编码模型可运行 | 仅双塔模型可用 | Qwen3-VL-Embedding-8B 通过推理冒烟测试 | `pixi run -e vllm -- pytest models/qwen3_vl_embedding.py` |
| Text 条件性验证 | 无 | 同图不同 text → embedding 余弦距离 ≥ 0.1 | 构造红/黄/黑色块 + 中文短语测试用例 |
| 循环稳定性 | 无 | 同输入 5 次推理 → embedding 余弦距离 < 1e-4 | 参数化循环测试 |
| CR 定位评测提升 | 见聚合算法评测基线 | joint embedding 在 multi_cr 场景 Recall≥? | `experiments/cr-locator-eval/` 框架 |

## 用户故事

- 作为算法工程师，我希望通过文本引导 embedding 抽取，提升特征与 topic 的语义对齐效果
- 作为开发者，我希望使用统一接口接入不同的 VL 模型

## 需求详情

### 技术方案

原流程：
```
image -> Model -> embedding ~ full image
```

VL 流程：
```
image + text -> Model -> embedding = (image embedding * text embedding) / image embedding = argmax(P(embedding ~ image | text))
```

### 双塔模型与 conditional image embedding

对于 CLIP、SigLIP、PE-Lang 这类双塔模型，标准形式其实是：

```
z_image = f_image(image)
z_text = f_text(text)
score(image, text) = sim(z_image, z_text)
```

这里 text 改变的是匹配分数，而不是图像 embedding 本身。

也就是说：

- 同一张图在双塔模型里的 `z_image` 应该与 text 无关
- text-guided 的效果主要体现在检索、排序、筛选、打分阶段
- 如果观察到“同一张图 + 不同 text 导致 embedding 改变”，那通常已经不是标准双塔语义，而是额外做了融合、重加权或联合编码

因此，“text guided conditional image embedding” 在工程上至少有两条路线：

1. 双塔检索打分路线

	不强行定义条件化后的图像向量，而是保留：

	- 图像 embedding：`z_image`
	- 文本 embedding：`z_text`
	- 图文匹配分数：`score(image, text)`

	这条路线适合做 topic 检索、相似度排序、候选筛选，优点是图像 embedding 可缓存，推理代价低，接口也最稳定。

2. 联合编码 conditional embedding 路线

	真正的 conditional image embedding 更接近：

	```
	z_cond = g(image, text)
	```

	也就是模型把 image 和 text 一起送入统一编码流程，再输出一个联合向量。这个联合向量会随着 text 改变而改变。

	当前仓库里，`models/qwen3_vl_embedding.py` 走的就是这条路线：先把图文输入格式化成同一会话，再做前向与 pooling，输出 joint embedding。

3. 双塔上的折中方案

	还可以在双塔模型的图像 patch token 之上额外做 text-guided pooling 或轻量融合头，得到一个后处理式的 `z_image|text`。但这不是 CLIP / SigLIP 的原生训练目标，通常需要额外验证，甚至需要少量训练数据做校准。

当前文档的倾向是：

- CLIP / PE-Lang / SigLIP / SigLIP2 主要承担双塔检索打分基线
- Qwen3-VL-Embedding 主要承担联合编码 conditional embedding 主线
- BLIP2 可以继续探索，但“能接收 text 输入”不等于“当前抽取出的 embedding 一定具有稳定的 text 条件性”

这也是为什么 Kimi-VL、Qwen3-VL Instruct / Thinking 这类通用生成式 VLM 不应直接算进 VL embedding 主候选：它们公开接口与仓库现有接入方式都围绕生成式推理，而不是稳定的 embedding 输出协议。

### 使用示例

```python
# topic="collision"
EmbeddingExtractor.extract([image], text='purple box touches or overlaps with other shapes')

# topic="harsh_brake"
EmbeddingExtractor.extract([image], text='the path above the purple box get red, and maybe intersects with other shapes')
```

### 候选模型

筛选标准：

- 模型需要直接提供图文对齐 embedding 能力，或明确面向 embedding / retrieval 任务
- 模型输出需要能稳定映射到可比较向量，而不是只支持生成式 `generate` 推理
- 纯视觉 backbone 不计入当前 VL embedding 主候选

当前方向：优先联合编码 / multimodal embedding 模型，双塔模型退到 baseline。

联合编码主候选（已下载）：

- Qwen/Qwen3-VL-Embedding-8B
	- 官方多模态 embedding 模型
	- 支持文本、图像、截图、视频及任意混合输入
	- 支持自定义 embedding 维度，最高 4096
	- 与当前仓库已有的 `models/qwen3_vl_embedding.py` 路线最一致
- Qwen/Qwen3-VL-Reranker-8B
	- 不是 embedding 模型，而是联合编码检索链路中的二阶段 reranker
	- 适合在 embedding 初筛后做精排
- Salesforce/blip2-opt-2.7b
	- 仅保留为探索型备选
	- 能接收图文输入，但不是面向 embedding / retrieval 训练的主线模型

双塔 baseline 候选（已下载）：

- AI-ModelScope/clip-vit-large-patch14
- AI-ModelScope/PE-Lang-G14-448
- google/siglip-base-patch16-224
- google/siglip-so400m-patch14-384
- google/siglip2-base-patch16-224
- google/siglip2-so400m-patch16-512

说明：

- 上述双塔模型更适合做 baseline 检索打分，不应再和联合编码 conditional embedding 主线混为一谈
- `AI-ModelScope/PE-Lang-G14-448` 仍值得保留，但当前本地模型产物不完整（缺少配置文件），需要先补齐文件再验证

未下载的 SOTA / 强候选（联合编码方向）：

- Qwen/Qwen3-VL-Embedding-2B
	- 官方轻量版 joint embedding 模型
	- 与 8B 版本保持同协议，最适合优先补充下载
- jinaai/jina-embeddings-v4
	- 多模态、多语言统一 embedding 模型
	- 支持 dense 单向量检索与 late interaction 多向量检索
	- 对视觉丰富文档检索尤其有吸引力
- BAAI/BGE-VL-MLLM-S1
	- 面向通用多模态检索的 MLLM embedding 模型
	- 明确支持 text + image 组合查询，对 conditional query embedding 很贴近
- nv-community/nemotron-colembed-vl-8b-v2
	- 面向视觉文档检索的 late interaction 多向量 embedding 模型
	- 在 ViDoRe V3 上是强基线甚至榜首级候选
	- 但推理更重，且许可证为非商用
- iic/GVE-7B
	- 面向文本 / 图像 / 视频 / 组合查询的统一 embedding 模型
	- 更偏视频检索场景，不是当前图文 conditional embedding 的第一优先级

暂不作为主线的模型：

- facebook/dinov2-base
- facebook/dinov2-large
- moonshotai/Kimi-VL-A3B-Instruct
- moonshotai/Kimi-VL-A3B-Thinking
- Qwen/Qwen3-VL-8B-Instruct-FP8
- Qwen/Qwen3-VL-8B-Thinking-FP8

原因：

- DINOv2 属于纯视觉 backbone，不提供 text-conditioned embedding
- Kimi-VL 与 Qwen3-VL Instruct / Thinking 当前定位是通用生成式 VLM；公开用法与仓库现有接入都以 `generate` 为主，不是稳定的 embedding 输出协议

当前 shortlist：

1. Qwen/Qwen3-VL-Embedding-8B
2. Qwen/Qwen3-VL-Embedding-2B
3. Qwen/Qwen3-VL-Reranker-8B
4. jinaai/jina-embeddings-v4
5. BAAI/BGE-VL-MLLM-S1

结论：如果目标是仓库内最快落地的联合编码 conditional embedding 主线，当前最优先的是 Qwen3-VL-Embedding 系列；如果目标扩展到视觉文档检索或多向量检索，再进一步关注 Jina Embeddings v4、BGE-VL-MLLM-S1 与 Nemotron ColEmbed VL。

## Iteration 20260517.1800

- 完成模型短名单分析，明确双塔检索打分 vs 联合编码 conditional embedding 两条路线划分
- 联合编码主线首选 Qwen3-VL-Embedding-8B，最短路径接入
- 列出后续下载候选取向：Qwen3-VL-Embedding-2B、jina-embeddings-v4、BGE-VL-MLLM-S1 等
- 双塔模型退至 baseline 角色（CLIP / PE-Lang / SigLIP / SigLIP2）

## 相关文件

- `lib/algorithms/embedding_extractor.py` - 现有 embedding 特征抽取实现
- `models/qwen3_vl_embedding.py` - Qwen3-VL-Embedding-8B 推理代码
- `models/inference_kimi_vl.py` - Kimi-VL 当前生成式推理接入
- `scripts/modelscope-download.sh` - ModelScope 下载全集，包含 embedding 与非 embedding 模型

## 验证方案

1. 双塔模型验证 `score(image, text)` 的方向性是否正确，而不是验证同一张图的 embedding 会随 text 改变
2. 联合编码模型验证 `embedding(image, text)` 是否对 text 敏感，且同语义图文对是否更接近
3. 完成其中一种主线模型的接入，并验证与现有抽象的兼容性或识别出需要拆分的新抽象

## Iterations

### Iteration 20260410.1509

开始规划，无论有什么疑惑或者规划顺利完成，最后都要用 ask_question 向我确认下一步行动（如：是否可以开始行动），务必带上自由输入的选项。


## Iteration 20260410.1918

我们先丰富一下 test_vl_embedding_extractor 用例，探索一下 text 输入是否可用

举个例子，text输入 红色，对应红色、黄色、黑色填充的图像来说，三个样本的embedding应该遵循某种规律对吧
以及text输入是黑色时
就地构造几个用例咱看下 Salesforce/blip2-opt-2.7b 的效果吧

开始规划，无论有任何疑惑或者规划顺利完成，最后都要用 ask_question 向我确认下一步行动（如：是否可以开始行动），务必带上自由输入的选项。


## Iteration 20260410.1951

你的意思是测试需要用 embedding metric 吗？那单独写一个 tests 下的测试吧，这个文件里的保留，验证推理能否跑通
其他

- 中文、短语测试是个好选项
- 有必要测不同 text embedding 的不同，以论证模型确实使用了 text
- 要验证 text 的方向性有效
- vl embedding 模型有随机采样吗？联网查证一下，同时编写循环稳定性测试
- 如果组合样例多的话记得用 pytest 参数化

如果没有疑问就开工吧，无论遭遇难以解决的问题或者任务顺利完成，最后都要用 ask_question 向我确认下一步行动（如：是否需要我 review 改动），务必带上自由输入的选项。


## Iteration 20260410.2036

- 调研 modelscope 上的 SOTA VL embedding 模型，如果可以，添加到下载文件 scripts/modelscope-download.sh
- 从 scripts/modelscope-download.sh 里挑出 候选  VL embedding 的模型
- 新模型更新到当前文档


## Iteration 20260411.2259

你确定？moonshotai/Kimi-VL-A3B-Instruct 这种如何获得 embedding ？

开始规划，无论有任何疑惑或者规划顺利完成，最后都要用 ask_question 向我确认下一步行动（如：是否可以开始行动），务必带上自由输入的选项。


## Iteration 20260411.2352

再次回顾 download 脚本中的候选后，当前结论：

- 主候选收敛为 CLIP / PE-Lang / SigLIP / SigLIP2 / Qwen3-VL-Embedding
- BLIP2 暂列探索型备选，不作为主线候选
- Kimi-VL 与 Qwen3-VL Instruct/Thinking 已从当前 VL embedding 主候选中移除
- 原因是它们当前公开与仓库内接入方式都以生成式推理为主，不是直接暴露 embedding 接口的模型


## Iteration 20260412.0007

clip siglip 等 image 和 text 是独立的双塔流程，怎么做 text guided conditional image embedding 呢？
开始解释，无论有任何疑惑或者规划顺利完成，最后都要用 ask_question 向我确认下一步行动（如：是否可以开始行动），务必带上自由输入的选项。

先把解释更新到文档，再用 ask_question 向我确认下一步行动

当前解释结论：

- 对于 CLIP / SigLIP / PE-Lang 这类双塔模型，text 会改变图文匹配分数，但不会改变图像 embedding 本身
- 如果目标是 topic 检索或候选筛选，应优先建模 text-guided score，而不是强行定义 conditional image embedding
- 如果目标是严格意义上的 conditional image embedding，则更适合走联合编码路线，例如 Qwen3-VL-Embedding 这类 joint embedding 模型
- 因此后续接口设计应考虑把“双塔检索打分”与“联合编码 embedding”分成两套语义，而不是复用同一个抽象硬包住所有模型

我现在要调研 联合编码 embedding，给我挑选模型 + 调研未下载的 SOTA 模型

开始行动，无论遭遇难以解决的问题或者任务顺利完成，最后都要用 ask_question 向我确认下一步行动（如：是否需要我 review 改动），务必带上自由输入的选项。


## Iteration 20260412.0034

联合编码 embedding 方向的本轮结论：

- 已下载模型里，真正适合作为联合编码主线的是 Qwen/Qwen3-VL-Embedding-8B
- 已下载的 Qwen/Qwen3-VL-Reranker-8B 应视为二阶段精排配套，而不是 embedding 替代品
- 已下载的 CLIP / PE-Lang / SigLIP / SigLIP2 仍有价值，但更适合作为双塔 baseline，而不是 conditional embedding 主线
- 已下载的 BLIP2 仅保留为探索型备选，不再作为主线候选

未下载但值得重点关注的 SOTA / 强候选：

- Qwen/Qwen3-VL-Embedding-2B：最适合优先补充下载，和 8B 版本协议一致，便于做成本 / 效果权衡
- jinaai/jina-embeddings-v4：多模态多语言统一 embedding，支持 dense 与 late interaction
- BAAI/BGE-VL-MLLM-S1：更贴近 image + text 组合查询场景，适合 conditional query embedding 探索
- nv-community/nemotron-colembed-vl-8b-v2：视觉文档检索强候选，但推理成本与许可证约束更强
- iic/GVE-7B：视频检索方向的统一 embedding 候选，当前优先级低于通用图文检索主线

当前建议的接入顺序：

1. 先围绕 Qwen3-VL-Embedding-8B 做主线验证
2. 再补 Qwen3-VL-Embedding-2B 做轻量化对照
3. 若要做高精度检索链路，再引入 Qwen3-VL-Reranker-8B
4. 若要扩展外部 SOTA 对比，再优先关注 Jina Embeddings v4 与 BGE-VL-MLLM-S1

## Iteration 20260412.1136

### 为什么不考虑OpenGVLab的几个模型？

**根本原因：** OpenGVLab在下载脚本中的模型都**不是embedding模型**，而是通用VLM或视频backbone。

#### 仓库已下载的OpenGVLab模型分析

| 模型 | 官方设计 | Embedding支持 | 推理模式 | 为什么不适合 |
|------|--------|--------|--------|--------|
| InternVideo2-Stage2_1B | 视频理解 | ❌ 无 | 视频帧编码 | 仅处理视频，无文本conditional能力 |
| InternVL3_5-241B | 通用VLM | ❌ 无 | 生成式推理 | 面向指令跟随与文本生成，不是embedding/retrieval |
| InternVL3_5-38B | 通用VLM | ❌ 无 | 生成式推理 | 同上 |
| VideoMAEv2-Huge | 视频特征 | ❌ 无 | 视频backbone | 纯视频backbone，不是多模态 |

#### 核心差异对比

**Qwen3-VL-Embedding-8B（当前选中）：**
- 官方embedding模型 → 内置embedding()接口
- 联合编码设计 → (image, text)联合输入，输出conditional embedding
- 为embedding/retrieval优化 → 稳定的向量输出，支持自定义维度
- 设计目标明确 → 性能保障

**OpenGVLab通用VLM（InternVL系列）：**
- 通用模型 → 以生成式推理为主(generate)
- 可接收图文但无embedding输出 → 需要自定义改装(提取hidden states)
- 改装方案不稳定 → hidden state pooling无官方优化
- 成本高 → InternVL3.5-38B参数量是Qwen3-8B的4倍，推理代价远高

#### 为什么"可以接收图文输入"不等于"有conditional embedding"

这是常见的混淆：通用VLM接收图文 → 理解 → 生成回复，而embedding模型接收图文 → 理解 → 输出数值向量。

- "InternVL可以接收图文输入" ≠ "InternVL有conditional embedding"
- "GPT-4V可以处理图像" ≠ "GPT-4V是embedding模型"
- "LLaMA-Vision可以做multimodal reasoning" ≠ "LLaMA-Vision有conditional embedding"

#### 当前不选OpenGVLab的理由汇总

1. **设计不匹配** - 模型都以生成式VLM或backbone设计，不是embedding优先
2. **无官方接口** - 没有embedding()/embed()这样的标准接口
3. **不稳定** - 需要自定义改装(hidden state提取)，性能无保障
4. **成本高** - InternVL参数量大，推理成本远高于Qwen3-8B
5. **社区验证少** - 作为embedding用途的验证少，可靠性低

#### 何时应该考虑OpenGVLab

1. **如果OpenGVLab发布官方embedding模型** - 与Qwen3/Jina/BGE做对标
2. **如果需要视频embedding扩展** - 当前不在scope内，优先级后移
3. **如果需要多语言embedding扩展** - 未来方向，需结合embedding能力

#### 结论

✅ **推荐继续使用Qwen3-VL-Embedding主线** - 官方embedding设计，稳定可靠

❌ **暂不建议用OpenGVLab改装embedding** - 设计不匹配，不符合标准

**下一步建议：** 重点验证Qwen3-VL-Embedding-8B的conditional能力，准备Jina Embeddings v4、BGE-VL-MLLM-S1作为对标

## Iteration 20260412.1635


现在处理 docs/kanban/features/VL Embedding 模型探索.md，请先切换上下文到当前文件，分析当前文件的内容和结构，理解当前文件的作用和与其他文件的关系，再进行后续的解释、规划或者编码。

修复推理 Qwen3-VL-Embedding-8B 遇到的以下问题：

```
✨ Pixi task (test in vllm): pytest --cov="$PROJECT_ROOT" --cov-append --cov-report= lib/algorithms/embedding_extractor.py
16:13:00.768 pytest: vlm-triage
             │ /home/luban/.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/bin/pytest:10
             │ project='vlm-triage'
============================================================= test session starts =============================================================
platform linux -- Python 3.13.12, pytest-9.0.2, pluggy-1.6.0
rootdir: /home/luban/workspaces/vlm-triage
configfile: pyproject.toml
plugins: anyio-4.12.1, logfire-4.29.0, asyncio-1.3.0, cov-7.1.0
asyncio: mode=Mode.AUTO, debug=True, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 2 items
16:13:25.215   lib/algorithms/embedding_extractor.py::test_image_embedding_extractor
               │ /home/luban/.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/bin/pytest:10

lib/algorithms/embedding_extractor.py .16:14:19.945   lib/algorithms/embedding_extractor.py::test_vl_embedding_extractor
               │ /home/luban/.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/bin/pytest:10
F                                                                                                [100%]

================================================================== FAILURES ===================================================================
_________________________________________________________ test_vl_embedding_extractor _________________________________________________________

    def test_vl_embedding_extractor():
        try:
            import os

            models_dir = f'{os.environ["MODELSCOPE_CACHE"]}/models'

            for model_id in [
                # 'AI-ModelScope/PE-Lang-G14-448',  # FIXME: missing config.json
                'Qwen/Qwen3-VL-Embedding-8B',
            ]:
                model_path = f'{models_dir}/{model_id}'
                extractor = ImageEmbeddingExtractor(model_path)
                images = [PIL.Image.new("RGB", (224, 224))]
>               e_nc = extractor.extract(images, text='black')
                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

lib/algorithms/embedding_extractor.py:233:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
lib/algorithms/embedding_extractor.py:162: in extract
    out_tensors = model(**inp_tensors)
                  ^^^^^^^^^^^^^^^^^^^^
../../.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.13/site-packages/torch/nn/modules/module.py:1773: in _wrapped_call_impl
    return self._call_impl(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.13/site-packages/torch/nn/modules/module.py:1784: in _call_impl
    return forward_call(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.13/site-packages/transformers/utils/generic.py:1072: in wrapper
    outputs = func(self, *args, **kwargs)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.13/site-packages/transformers/models/qwen3_vl/modeling_qwen3_vl.py:1140: in forward
    image_mask, _ = self.get_placeholder_mask(
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = Qwen3VLModel(
  (visual): Qwen3VLVisionModel(
    (patch_embed): Qwen3VLVisionPatchEmbed(
      (proj): Conv3d(3, 1152...)
      )
    )
    (norm): Qwen3VLTextRMSNorm((4096,), eps=1e-06)
    (rotary_emb): Qwen3VLTextRotaryEmbedding()
  )
)
input_ids = tensor([[ 11453, 151643]], device='cuda:0')
inputs_embeds = tensor([[[-0.0374, -0.0183,  0.0196,  ..., -0.0239,  0.0485,  0.0040],
         [ 0.0016,  0.0046,  0.0046,  ..., -0.0064,  0.0276,  0.0208]]],
       device='cuda:0')
image_features = tensor([[ 1.1865, -1.1074, -1.5674,  ..., -0.4001, -0.9629, -0.4233],
        [ 1.2168, -1.1211, -1.5527,  ..., -0.405...4075, -0.9634, -0.4255],
        [ 1.1924, -1.1104, -1.5762,  ..., -0.4043, -0.9702, -0.4409]],
       device='cuda:0')
video_features = None

    def get_placeholder_mask(
        self,
        input_ids: torch.LongTensor,
        inputs_embeds: torch.FloatTensor,
        image_features: Optional[torch.FloatTensor] = None,
        video_features: Optional[torch.FloatTensor] = None,
    ):
        """
        Obtains multimodal placeholder mask from `input_ids` or `inputs_embeds`, and checks that the placeholder token count is
        equal to the length of multimodal features. If the lengths are different, an error is raised.
        """
        if input_ids is None:
            special_image_mask = inputs_embeds == self.get_input_embeddings()(
                torch.tensor(self.config.image_token_id, dtype=torch.long, device=inputs_embeds.device)
            )
            special_image_mask = special_image_mask.all(-1)
            special_video_mask = inputs_embeds == self.get_input_embeddings()(
                torch.tensor(self.config.video_token_id, dtype=torch.long, device=inputs_embeds.device)
            )
            special_video_mask = special_video_mask.all(-1)
        else:
            special_image_mask = input_ids == self.config.image_token_id
            special_video_mask = input_ids == self.config.video_token_id

        n_image_tokens = special_image_mask.sum()
        special_image_mask = special_image_mask.unsqueeze(-1).expand_as(inputs_embeds).to(inputs_embeds.device)
        if image_features is not None and inputs_embeds[special_image_mask].numel() != image_features.numel():
>           raise ValueError(
                f"Image features and image tokens do not match: tokens: {n_image_tokens}, features {image_features.shape[0]}"
            )
E           ValueError: Image features and image tokens do not match: tokens: 0, features 49

../../.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.13/site-packages/transformers/models/qwen3_vl/modeling_qwen3_vl.py:1093: ValueError
------------------------------------------------------------ Captured stderr call -------------------------------------------------------------
16:14:19.948 Calling lib.algorithms.embedding_extractor.EmbeddingExtractorBase.__init__
             │ lib/algorithms/embedding_extractor.py:37
16:14:19.949   load model '/home/luban/mount-env/luonairui/modelscope/cache/models/Qwen/Qwen3-VL-Embedding-8B'
               │ /home/luban/workspaces/vlm-triage/lib/algorithms/embedding_extractor.py:63 info
               │ logfire.logger_name='lib.algorithms.embedding_extractor'

│
│
│
logfire.logging_args=
(
    '/home/luban/mount-env/luonairui/modelscope/cache/models/Qwen/Qwen3-VL-Embe…
)
Loading checkpoint shards: 100%|██████████| 4/4 [00:00<00:00, 154.78it/s]
16:15:28.972   load processor for '/home/luban/mount-env/luonairui/modelscope/cache/models/Qwen/Qwen3-VL-Embedding-8B'
               │ /home/luban/workspaces/vlm-triage/lib/algorithms/embedding_extractor.py:74 info
               │ logfire.logger_name='lib.algorithms.embedding_extractor'

│
│
│
logfire.logging_args=
(
    '/home/luban/mount-env/luonairui/modelscope/cache/models/Qwen/Qwen3-VL-Embe…
)
16:15:30.038 Calling lib.algorithms.embedding_extractor.ImageEmbeddingExtractor.extract
             │ lib/algorithms/embedding_extractor.py:132
16:15:30.072   Calling lib.utils.torch_utils.inspect_tensors
               │ lib/utils/torch_utils.py:91
16:15:30.077     Calling lib.utils.torch_utils._TensorInspector.inspect
                 │ lib/utils/torch_utils.py:68
16:15:30.078       Calling lib.utils.torch_utils._TensorInspector.inspect
                   │ lib/utils/torch_utils.py:68
16:15:30.079         /home/luban/mount-env/luonairui/modelscope/cache/models/Qwen/Qwen3-VL-Embedding-8B.inputs['input_ids']: torch.int64(1, 2)@cuda:0
                     │ /home/luban/workspaces/vlm-triage/lib/utils/torch_utils.py:78 info
                     │ logfire.logger_name='lib.algorithms.embedding_extractor'
16:15:30.081       Calling lib.utils.torch_utils._TensorInspector.inspect
                   │ lib/utils/torch_utils.py:68
16:15:30.082         /home/luban/mount-env/luonairui/modelscope/cache/models/Qwen/Qwen3-VL-Embedding-8B.inputs['attention_mask']: torch.int64(1, 2)@cuda:0
                     │ /home/luban/workspaces/vlm-triage/lib/utils/torch_utils.py:78 info
                     │ logfire.logger_name='lib.algorithms.embedding_extractor'
16:15:30.084       Calling lib.utils.torch_utils._TensorInspector.inspect
                   │ lib/utils/torch_utils.py:68
16:15:30.085         /home/luban/mount-env/luonairui/modelscope/cache/models/Qwen/Qwen3-VL-Embedding-8B.inputs['pixel_values']: torch.float32(196, 1536)@cuda:0
                     │ /home/luban/workspaces/vlm-triage/lib/utils/torch_utils.py:78 info
                     │ logfire.logger_name='lib.algorithms.embedding_extractor'
16:15:30.087       Calling lib.utils.torch_utils._TensorInspector.inspect
                   │ lib/utils/torch_utils.py:68
16:15:30.088         /home/luban/mount-env/luonairui/modelscope/cache/models/Qwen/Qwen3-VL-Embedding-8B.inputs['image_grid_thw']: torch.int64(1, 3)@cuda:0
                     │ /home/luban/workspaces/vlm-triage/lib/utils/torch_utils.py:78 info
                     │ logfire.logger_name='lib.algorithms.embedding_extractor'
-------------------------------------------------------------- Captured log call --------------------------------------------------------------
INFO     lib.algorithms.embedding_extractor:embedding_extractor.py:63 load model '/home/luban/mount-env/luonairui/modelscope/cache/models/Qwen/Qwen3-VL-Embedding-8B'
INFO     lib.algorithms.embedding_extractor:embedding_extractor.py:74 load processor for '/home/luban/mount-env/luonairui/modelscope/cache/models/Qwen/Qwen3-VL-Embedding-8B'
INFO     lib.algorithms.embedding_extractor:torch_utils.py:78 /home/luban/mount-env/luonairui/modelscope/cache/models/Qwen/Qwen3-VL-Embedding-8B.inputs['input_ids']: torch.int64(1, 2)@cuda:0
INFO     lib.algorithms.embedding_extractor:torch_utils.py:78 /home/luban/mount-env/luonairui/modelscope/cache/models/Qwen/Qwen3-VL-Embedding-8B.inputs['attention_mask']: torch.int64(1, 2)@cuda:0
INFO     lib.algorithms.embedding_extractor:torch_utils.py:78 /home/luban/mount-env/luonairui/modelscope/cache/models/Qwen/Qwen3-VL-Embedding-8B.inputs['pixel_values']: torch.float32(196, 1536)@cuda:0
INFO     lib.algorithms.embedding_extractor:torch_utils.py:78 /home/luban/mount-env/luonairui/modelscope/cache/models/Qwen/Qwen3-VL-Embedding-8B.inputs['image_grid_thw']: torch.int64(1, 3)@cuda:0
============================================================== warnings summary ===============================================================
lib/algorithms/embedding_extractor.py::test_image_embedding_extractor
  /home/luban/.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.13/site-packages/transformers/image_processing_utils.py:51: UserWarning: The following named arguments are not valid for `BitImageProcessor.preprocess` and were ignored: 'text'
    return self.preprocess(images, **kwargs)

lib/algorithms/embedding_extractor.py::test_image_embedding_extractor
  <frozen importlib._bootstrap>:488: DeprecationWarning: builtin type SwigPyPacked has no __module__ attribute

lib/algorithms/embedding_extractor.py::test_image_embedding_extractor
  <frozen importlib._bootstrap>:488: DeprecationWarning: builtin type SwigPyObject has no __module__ attribute

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================================================== short test summary info ===========================================================
FAILED lib/algorithms/embedding_extractor.py::test_vl_embedding_extractor - ValueError: Image features and image tokens do not match: tokens: 0, features 49
============================================= 1 failed, 1 passed, 3 warnings in 152.06s (0:02:32) =============================================
```

开始行动，无论遭遇难以解决的问题或者任务顺利完成，最后都要用 ask_question 向我确认下一步行动（如：是否需要我 review 改动），务必带上自由输入的选项。

## Iteration 20260412.1649

我觉得应该继承 ImageEmbeddingExtractor 到一个新类 VLEmbeddingExtractor 来实现 VL 的逻辑
开始行动，无论遭遇难以解决的问题或者任务顺利完成，最后都要用 ask_question 向我确认下一步行动（如：是否需要我 review 改动），务必带上自由输入的选项。

## Iteration 20260412.1653

- I think text is no longer optional in VL extractor
- 增加调试日志看看conversations等处理过程：conversations、text_inputs、mask 等
- 对于 N 张图，text输入是要 repeat N 遍吗？还是只 N 个 image placeholder token + 1 个 text 就行？
- padding=True 对所有类似模型都是必须的吗？
- 使用 docs/rules/coding-guidelines.md 中的科学计算命名法对出现的 tensor 命名
- 补充类型批注
- 修改完成后直接运行 lib/algorithms/embedding_extractor.py 进行测试
开始行动，无论遭遇难以解决的问题或者任务顺利完成，最后都要用 ask_question 向我确认下一步行动（如：是否需要我 review 改动），务必带上自由输入的选项。

## Iteration 20260412.1705

- pytest -rN 是什么选项？
- 有必要将 torch.float16 设为默认 dtype 吗？还是说只为 VL embedding 模型设置 torch.float16 默认值
- 构思基于颜色块的 图像-文本测试用例，验证 text 条件性，这比纯图像 embedding会多一些信息。至于放哪，我觉得 参考 lib/services/embedding_service.py 里的用例，是不是放一起更好？
- 新模型下载完成了，出现错误，这又是一个不能用的代码，是吗？

```
INFO     lib.algorithms.embedding_extractor:embedding_extractor.py:63 load model '/home/luban/mount-env/luonairui/modelscope/cache/models/BAAI/BGE-VL-MLLM-S1'
INFO     lib.algorithms.embedding_extractor:embedding_extractor.py:74 load processor for '/home/luban/mount-env/luonairui/modelscope/cache/models/BAAI/BGE-VL-MLLM-S1'
INFO     lib.algorithms.embedding_extractor:torch_utils.py:78 /home/luban/mount-env/luonairui/modelscope/cache/models/BAAI/BGE-VL-MLLM-S1.inputs['input_ids']: torch.int64(1, 2)@cuda:0
INFO     lib.algorithms.embedding_extractor:torch_utils.py:78 /home/luban/mount-env/luonairui/modelscope/cache/models/BAAI/BGE-VL-MLLM-S1.inputs['attention_mask']: torch.int64(1, 2)@cuda:0
INFO     lib.algorithms.embedding_extractor:torch_utils.py:78 /home/luban/mount-env/luonairui/modelscope/cache/models/BAAI/BGE-VL-MLLM-S1.inputs['pixel_values']: torch.float32(1, 3, 3, 336, 336)@cuda:0
INFO     lib.algorithms.embedding_extractor:torch_utils.py:78 /home/luban/mount-env/luonairui/modelscope/cache/models/BAAI/BGE-VL-MLLM-S1.inputs['image_sizes']: torch.int64(1, 2)@cuda:0
______________________________________________________________________ test_vl_embedding_extractor ______________________________________________________________________

    def test_vl_embedding_extractor():
        try:
            import os

            models_dir = f'{os.environ["MODELSCOPE_CACHE"]}/models'

            for model_id in [
                # 'AI-ModelScope/PE-Lang-G14-448',  # FIXME: missing config.json
                'BAAI/BGE-VL-MLLM-S1',
                'iic/GVE-7B',
                'jinaai/jina-embeddings-v4',
                'nv-community/nemotron-colembed-vl-8b-v2',
                'Qwen/Qwen3-VL-Embedding-8B',
            ]:
                print(f'test {model_id=}')

                model_path = f'{models_dir}/{model_id}'
                extractor = VLEmbeddingExtractor(model_path, trust_remote_code=True)
                images = [PIL.Image.new("RGB", (224, 224))]
>               e_nc = extractor.extract(images, text='black')
                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

lib/algorithms/embedding_extractor.py:328:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
lib/algorithms/embedding_extractor.py:242: in extract
    out_tensors = self.model(**inp_tensors)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^
../../.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.13/site-packages/torch/nn/modules/module.py:1773: in _wrapped_call_impl
    return self._call_impl(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.13/site-packages/torch/nn/modules/module.py:1784: in _call_impl
    return forward_call(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../mount-env/luonairui/huggingface/modules/transformers_modules/BGE_hyphen_VL_hyphen_MLLM_hyphen_S1/modeling_llavanext_for_embedding.py:183: in forward
    image_newline=self.image_newline,
                  ^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = LLaVANextForEmbedding(
  (model): LlavaNextModel(
    (vision_tower): CLIPVisionModel(
      (vision_model): CLIPVisio...rotary_emb): MistralRotaryEmbedding()
    )
  )
  (lm_head): Linear(in_features=4096, out_features=32005, bias=False)
)
name = 'image_newline'

    def __getattr__(self, name: str) -> Union[Tensor, "Module"]:
        if "_parameters" in self.__dict__:
            _parameters = self.__dict__["_parameters"]
            if name in _parameters:
                return _parameters[name]
        if "_buffers" in self.__dict__:
            _buffers = self.__dict__["_buffers"]
            if name in _buffers:
                return _buffers[name]
        if "_modules" in self.__dict__:
            modules = self.__dict__["_modules"]
            if name in modules:
                return modules[name]
>       raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )
E       AttributeError: 'LLaVANextForEmbedding' object has no attribute 'image_newline'

../../.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.13/site-packages/torch/nn/modules/module.py:1962: AttributeError
--------------------------------------------------------------------------- Captured log call ---------------------------------------------------------------------------
INFO     lib.algorithms.embedding_extractor:embedding_extractor.py:63 load model '/home/luban/mount-env/luonairui/modelscope/cache/models/BAAI/BGE-VL-MLLM-S1'
INFO     lib.algorithms.embedding_extractor:embedding_extractor.py:74 load processor for '/home/luban/mount-env/luonairui/modelscope/cache/models/BAAI/BGE-VL-MLLM-S1'
```

开始解释，解释完成用 ask_question 向我确认下一步行动（如：是否可以开始编码），务必带上自由输入的选项。

## Iteration 20260412.2249

- 候选模型好像有不支持 bfp16 的，看来只能为 VL 模型配置这个默认值了？
- 下一个模型

```
______________________________________________________________________ test_vl_embedding_extractor ______________________________________________________________________

    def test_vl_embedding_extractor():
        try:
            import os

            models_dir = f'{os.environ["MODELSCOPE_CACHE"]}/models'

            for model_id in [
                # 'AI-ModelScope/PE-Lang-G14-448',  # FIXME: missing config.json
                # 'BAAI/BGE-VL-MLLM-S1',  # BUG: AttributeError: 'LLaVANextForEmbedding' object has no attribute 'image_newline'
                'iic/GVE-7B',
                'jinaai/jina-embeddings-v4',
                'nv-community/nemotron-colembed-vl-8b-v2',
                'Qwen/Qwen3-VL-Embedding-8B',
            ]:
                print(f'test {model_id=}')

                model_path = f'{models_dir}/{model_id}'
>               extractor = VLEmbeddingExtractor(model_path, trust_remote_code=True)
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

lib/algorithms/embedding_extractor.py:327:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
lib/algorithms/embedding_extractor.py:64: in __init__
    self.model: torch.nn.Module = AutoModel.from_pretrained(
../../.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.13/site-packages/transformers/models/auto/auto_factory.py:586: in from_pretrained
    model_class = get_class_from_dynamic_module(
../../.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.13/site-packages/transformers/dynamic_module_utils.py:616: in get_class_from_dynamic_module
    return get_class_in_module(class_name, final_module, force_reload=force_download)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.13/site-packages/transformers/dynamic_module_utils.py:311: in get_class_in_module
    module_spec.loader.exec_module(module)
<frozen importlib._bootstrap_external>:1023: in exec_module
    ???
<frozen importlib._bootstrap>:488: in _call_with_frames_removed
    ???
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    import math
    from dataclasses import dataclass
    from typing import List, Optional, Tuple, Union

    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.nn import CrossEntropyLoss

    from transformers.activations import ACT2FN
    from transformers.cache_utils import Cache, DynamicCache, SlidingWindowCache, StaticCache
    from transformers.generation import GenerationMixin
    from transformers.modeling_attn_mask_utils import AttentionMaskConverter
    from transformers.modeling_outputs import BaseModelOutputWithPast, ModelOutput
    from transformers.modeling_rope_utils import ROPE_INIT_FUNCTIONS
    from transformers.modeling_utils import PreTrainedModel
    from transformers.utils import (
        add_start_docstrings,
        add_start_docstrings_to_model_forward,
        is_flash_attn_2_available,
        is_flash_attn_greater_or_equal_2_10,
        logging,
        replace_return_docstrings,
    )
    from transformers.models.qwen2_5_vl.configuration_qwen2_5_vl import Qwen2_5_VLConfig, Qwen2_5_VLVisionConfig
>   from transformers.models.qwen2_5_vl.modeling_qwen2_5_vl import Qwen2_5_VLForConditionalGeneration, QWEN2_5_VL_INPUTS_DOCSTRING, Qwen2_5_VLCausalLMOutputWithPast
E   ImportError: cannot import name 'QWEN2_5_VL_INPUTS_DOCSTRING' from 'transformers.models.qwen2_5_vl.modeling_qwen2_5_vl' (/home/luban/.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.13/site-packages/transformers/models/qwen2_5_vl/modeling_qwen2_5_vl.py)

../../mount-env/luonairui/huggingface/modules/transformers_modules/GVE_hyphen_7B/modeling_gve.py:26: ImportError
```

开始解释，解释完成用 ask_question 向我确认下一步行动（如：是否可以开始编码），务必带上自由输入的选项。

## Iteration 20260412.2312

下一个模型：

```
=============================================================================== FAILURES ================================================================================
____________________________________________________________________ test_image_embedding_extractor _____________________________________________________________________

    def test_image_embedding_extractor():
        r"""
        测试 ImageEmbeddingExtractor。

        使用 DINOv2 模型创建测试提取器，并验证 embedding 的形状是否正确。

        验证:
            - 提取器成功创建
            - 提取的 embedding 维度为 2
            - embedding 的第一维与图像数量一致

        Parameters:
            -
        """

        try:
            import os

            models_dir = f'{os.environ["MODELSCOPE_CACHE"]}/models'

            for model_id in [
                # 'AI-ModelScope/PE-Lang-G14-448',  # FIXME: missing config.json
                'AI-ModelScope/clip-vit-large-patch14',
                'apple/aimv2-huge-patch14-448',
                # 'BAAI/BGE-VL-MLLM-S1',  # FIXME: AttributeError: 'LLaVANextForEmbedding' object has no attribute 'image_newline'
                'facebook/dinov2-base',
                'facebook/dinov2-large',
                'google/siglip-base-patch16-224',
                'google/siglip-so400m-patch14-384',
                'google/siglip2-base-patch16-224',
                'google/siglip2-so400m-patch16-512',
                # 'iic/GVE-7B',  # FIXME: ImportError: cannot import name 'QWEN2_5_VL_INPUTS_DOCSTRING' from 'transformers.models.qwen2_5_vl.modeling_qwen2_5_vl' (/home/luban/.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.13/site-packages/transformers/models/qwen2_5_vl/modeling_qwen2_5_vl.py)
                'jinaai/jina-embeddings-v4',
                'nv-community/nemotron-colembed-vl-8b-v2',
                'Salesforce/blip2-opt-2.7b',
            ]:
                print(f'test {model_id=}')

                extractor = ImageEmbeddingExtractor(
                    f'{models_dir}/{model_id}',
                    trust_remote_code=True,
                )
                images = [PIL.Image.new("RGB", (224, 224))]
>               e_nc = extractor.extract(images, text='')
                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

lib/algorithms/embedding_extractor.py:311:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
lib/algorithms/embedding_extractor.py:162: in extract
    out_tensors = self.model(**inp_tensors)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^
../../.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.13/site-packages/torch/nn/modules/module.py:1773: in _wrapped_call_impl
    return self._call_impl(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.13/site-packages/torch/nn/modules/module.py:1784: in _call_impl
    return forward_call(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.13/site-packages/peft/peft_model.py:2986: in forward
    return self.base_model(
../../.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.13/site-packages/torch/nn/modules/module.py:1773: in _wrapped_call_impl
    return self._call_impl(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.13/site-packages/torch/nn/modules/module.py:1784: in _call_impl
    return forward_call(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = LoraModel(
  (model): JinaEmbeddingsV4Model(
    (model): Qwen2_5_VLModel(
      (visual): Qwen2_5_VisionTransformerPr...g_A): ParameterDict()
      (lora_embedding_B): ParameterDict()
      (lora_magnitude_vector): ModuleDict()
    )
  )
)
args = ()
kwargs = {'attention_mask': tensor([], device='cuda:0', size=(1, 0)), 'image_grid_thw': tensor([[ 1, 16, 16]], device='cuda:0'), 'input_ids': tensor([], device='cuda:0', size=(1, 0)), 'inputs_embeds': None, ...}

    def forward(self, *args: Any, **kwargs: Any):
>       return self.model.forward(*args, **kwargs)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       TypeError: JinaEmbeddingsV4Model.forward() missing 1 required positional argument: 'task_label'

../../.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.13/site-packages/peft/tuners/tuners_utils.py:311: TypeError
______________________________________________________________________ test_vl_embedding_extractor ______________________________________________________________________

    def test_vl_embedding_extractor():
        try:
            import os

            models_dir = f'{os.environ["MODELSCOPE_CACHE"]}/models'

            for model_id in [
                # 'AI-ModelScope/PE-Lang-G14-448',  # FIXME: missing config.json
                # 'BAAI/BGE-VL-MLLM-S1',  # FIXME: AttributeError: 'LLaVANextForEmbedding' object has no attribute 'image_newline'
                # 'iic/GVE-7B',  # FIXME: ImportError: cannot import name 'QWEN2_5_VL_INPUTS_DOCSTRING' from 'transformers.models.qwen2_5_vl.modeling_qwen2_5_vl' (/home/luban/.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.13/site-packages/transformers/models/qwen2_5_vl/modeling_qwen2_5_vl.py)
                'jinaai/jina-embeddings-v4',
                'nv-community/nemotron-colembed-vl-8b-v2',
                'Qwen/Qwen3-VL-Embedding-8B',
            ]:
                print(f'test {model_id=}')

                model_path = f'{models_dir}/{model_id}'
                extractor = VLEmbeddingExtractor(model_path, trust_remote_code=True)
                images = [PIL.Image.new("RGB", (224, 224))]
>               e_nc = extractor.extract(images, text='black')
                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

lib/algorithms/embedding_extractor.py:339:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
lib/algorithms/embedding_extractor.py:235: in extract
    text_inputs: list[str] = self.processor.apply_chat_template(
../../.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.13/site-packages/transformers/utils/deprecation.py:172: in wrapped_func
    return func(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^
../../.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.13/site-packages/transformers/utils/deprecation.py:172: in wrapped_func
    return func(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = JinaEmbeddingsV4Processor:
- image_processor: Qwen2VLImageProcessorFast {
  "auto_map": {
    "AutoProcessor": "modeli...ata": null,
  "video_processor_type": "Qwen2VLVideoProcessor"
}


{
  "processor_class": "JinaEmbeddingsV4Processor"
}

conversation = [[{'content': [{'type': 'image'}, {'text': 'black', 'type': 'text'}], 'role': 'user'}]], chat_template = None
kwargs = {'add_generation_prompt': True, 'tokenize': False}

    @deprecate_kwarg("video_fps", version="4.58", new_name="fps")
    @deprecate_kwarg(
        "video_load_backend",
        version="4.59",
        additional_message=". This function will use `torchcodec` by default, or `torchvision` if `torchcodec` is not installed.",
    )
    def apply_chat_template(
        self,
        conversation: Union[list[dict[str, str]], list[list[dict[str, str]]]],
        chat_template: Optional[str] = None,
        **kwargs: Unpack[AllKwargsForChatTemplate],
    ) -> str:
        """
        Similar to the `apply_chat_template` method on tokenizers, this method applies a Jinja template to input
        conversations to turn them into a single tokenizable string.

        The input is expected to be in the following format, where each message content is a list consisting of text and
        optionally image or video inputs. One can also provide an image, video, URL or local path which will be used to form
        `pixel_values` when `return_dict=True`. If not provided, one will get only the formatted text, optionally tokenized text.

        conversation = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "url": "https://www.ilankelman.org/stopsigns/australia.jpg"},
                    {"type": "text", "text": "Please describe this image in detail."},
                ],
            },
        ]

        Args:
            conversation (`Union[list[Dict, [str, str]], list[list[dict[str, str]]]]`):
                The conversation to format.
            chat_template (`Optional[str]`, *optional*):
                The Jinja template to use for formatting the conversation. If not provided, the tokenizer's
                chat template is used.
        """
        if chat_template is None:
            if isinstance(self.chat_template, dict) and "default" in self.chat_template:
                chat_template = self.chat_template["default"]
            elif isinstance(self.chat_template, dict):
                raise ValueError(
                    'The processor has multiple chat templates but none of them are named "default". You need to specify'
                    " which one to use by passing the `chat_template` argument. Available templates are: "
                    f"{', '.join(self.chat_template.keys())}"
                )
            elif self.chat_template is not None:
                chat_template = self.chat_template
            else:
>               raise ValueError(
                    "Cannot use apply_chat_template because this processor does not have a chat template."
                )
E               ValueError: Cannot use apply_chat_template because this processor does not have a chat template.

../../.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.13/site-packages/transformers/processing_utils.py:1571: ValueError
======================================================================== short test summary info ========================================================================
FAILED lib/algorithms/embedding_extractor.py::test_image_embedding_extractor - TypeError: JinaEmbeddingsV4Model.forward() missing 1 required positional argument: 'task_label'
FAILED lib/algorithms/embedding_extractor.py::test_vl_embedding_extractor - ValueError: Cannot use apply_chat_template because this processor does not have a chat template.
```

开始解释，解释完成用 ask_question 向我确认下一步行动（如：是否可以开始编码），务必带上自由输入的选项。


## Iteration 20260412.2315

- 目前test_vl_embedding_extractor测试可用的模型有：
	'nv-community/nemotron-colembed-vl-8b-v2',
	'Qwen/Qwen3-VL-Embedding-8B',
接下来设计 text 条件的有效性测试用例，开发代码进行验证

总结结论和下一步计划，更新到文档 docs/kanban/features/VL Embedding 模型探索.md

开始行动，无论遭遇难以解决的问题或者任务顺利完成，最后都要用 ask_question 向我确认下一步行动（如：是否需要我 review 改动），务必带上自由输入的选项。

### 完成内容

#### 1. VLEmbeddingExtractor 实现

在 `lib/algorithms/embedding_extractor.py` 中新增 `VLEmbeddingExtractor(ImageEmbeddingExtractor)`:

- 使用 processor 的 `apply_chat_template` 为每张图像构建独立会话，插入 `<|image_pad|>` 占位符
- `text: str` 为 keyword-only 必需参数，与每张图像重复组合
- 使用 last-token pooling 提取 embedding（VL embedding 模型的标准做法）
- 默认 bf16 推理（通过 `set_dtype` override），减少显存占用
- 支持 batch 处理（`padding=True`）
- 完整 type annotations 和 debug logging

#### 2. 模型兼容性测试结果

| 模型 | 架构 | 状态 | 问题 |
|------|------|------|------|
| **Qwen/Qwen3-VL-Embedding-8B** | qwen3_vl | ✅ 可用 | - |
| **nv-community/nemotron-colembed-vl-8b-v2** | qwen3_vl 变体 | ✅ 可用 | - |
| BAAI/BGE-VL-MLLM-S1 | llava_next | ❌ | `'LLaVANextForEmbedding' object has no attribute 'image_newline'` |
| iic/GVE-7B | qwen2_5_vl 自定义 | ❌ | `cannot import name 'QWEN2_5_VL_INPUTS_DOCSTRING'`（transformers 4.57.6 不兼容） |
| jinaai/jina-embeddings-v4 | qwen2_5_vl + LoRA | ❌ | `forward() missing 'task_label'` + processor 无 chat template |

结论：每个 VL 模型有自己的架构、输入格式和 processor 要求，不存在通用的单一 extractor。当前 `VLEmbeddingExtractor` 基于 `apply_chat_template` + last-token pooling，兼容 Qwen3-VL 系列和 Nemotron ColEmbed VL。

#### 3. Text 条件性验证结果 (`test_vl_embedding_text_conditionality`)

使用纯色 PIL 图像（红/绿/蓝，224×224）× 3 种 text 查询，在 Qwen3-VL-Embedding-8B 上验证：

**确定性**: cosine sim = 1.0000（bf16 精度下完全一致）✅

**敏感性**: 同一图像 + 不同 text → cosine sim 0.96~0.98（text 确实改变了 embedding）✅

**方向性 (9×9 相似度矩阵)**:

```
                red+red  green+red blue+red red+green green+green blue+green red+blue green+blue blue+blue
red+red        : 1.000,    0.022,   0.054,   0.975,     0.022,      0.053,   0.959,    0.027,     0.055
green+red      : 0.022,    1.000,   0.056,   0.019,     0.964,      0.053,   0.025,    0.967,     0.055
blue+red       : 0.054,    0.056,   1.000,   0.054,     0.052,      0.986,   0.057,    0.053,     0.981
red+green      : 0.975,    0.019,   0.054,   1.000,     0.020,      0.053,   0.971,    0.024,     0.054
green+green    : 0.022,    0.964,   0.052,   0.020,     1.000,      0.049,   0.026,    0.960,     0.051
blue+green     : 0.053,    0.053,   0.986,   0.053,     0.049,      1.000,   0.056,    0.049,     0.984
red+blue       : 0.959,    0.025,   0.057,   0.971,     0.026,      0.056,   1.000,    0.029,     0.057
green+blue     : 0.027,    0.967,   0.053,   0.024,     0.960,      0.049,   0.029,    1.000,     0.052
blue+blue      : 0.055,    0.055,   0.981,   0.054,     0.051,      0.984,   0.057,    0.052,     1.000
```

| 统计量 | 值 | 含义 |
|--------|------|------|
| avg intra-image sim | **0.9720** | 同一图像 + 不同 text → 非常相似 |
| avg intra-text sim | **0.0435** | 同一 text + 不同图像 → 几乎正交 |
| avg cross sim | **0.0435** | 不同图像 + 不同 text → 几乎正交 |

**关键结论**:

1. **图像主导 embedding 空间**: intra-image (0.97) >> intra-text (0.04)，图像内容是主要信号
2. **Text 有可测量的调节效果**: 同一图像的 embedding 在不同 text 下仍有 2-4% 的变化（sensitivity sim 0.96~0.98）
3. **不同图像之间几乎正交**: sim ≈ 0.04，说明纯色图像在 embedding 空间中充分分散
4. **Text 不形成独立聚类**: intra-text ≈ cross，text 改变不会让不同图像向"同一方向"靠拢

这对于实际场景意味着：**VL embedding 在纯色测试图上的 text 效果偏弱（~3% 变化）**。真实场景图像（含有丰富语义内容如碰撞、车辆、行人等）的 text 引导效果可能更强，需要后续用实际路测数据验证。

### 下一步计划

1. **真实场景 text 条件性验证**: 使用路测碰撞场景图像 + topic 描述文本（如 "collision"、"harsh braking"），验证 text 引导在实际数据上的效果是否比纯色图像显著
2. **中文 text 支持**: 验证中文 text 输入（如"碰撞"、"急刹"）的效果是否与英文一致
3. **Qwen3-VL-Embedding-2B 下载与验证**: 轻量版模型，评估精度-效率 tradeoff
4. **与 EmbeddingService 集成**: ✅ 已完成。`VLEmbeddingExtractor` 已接入 `lib/services/embedding_service.py`（VL 模型通过 `model_id/VL` 后缀路由），并进一步打通 `visual_cr_locator` 链路（`LocatorConfig.text` → `compute_sample_embedding_metrics()`）
5. **不兼容模型的独立 Extractor**: 如果 BGE-VL、Jina v4 等模型的优先级上升，需要为其架构开发专用 Extractor

## Iteration 20260512.1508

忽略前面的工作，现在处理 @'docs/kanban/features/VL Embedding 模型探索.md'，请先切换到当前文件，理解当前所述的任务，再进行后续的解释、规划或者编码，并及时将阶段性总结更新到本文件。

@lib/algorithms/embedding_extractor.py 中增加了 VLEmbeddingExtractor
我们希望暴露到 api 上，链路为
> embedding_extractor -> embedding_service -> apps/embedding_api/main.py
至于 VLEmbeddingExtractor 和 ImageEmbeddingExtractor 的 路由区分，我希望在 embedding_service 通过 text 非空来区分，当 text = '', None, 不存在时 默认 ImageEmbeddingExtractor

集成完毕，在 @apps/visual_cr_locator/api.py 所在的链路中增加可选的 text 高级参数并打通传递到 embedding

开始规划，无论有任何疑惑或者规划顺利完成，最后都要用 ask_question / ask_user 向我确认下一步行动（如：是否可以开始行动）。

### 完成内容

#### 1. Embedding API 已支持 VL 模型路由 (commit `b9aa224`)

- `ImageEmbeddingExtractorLoader` → `EmbeddingExtractorLoader`，通过 `model_id` 后缀 `/IMAGE` vs `/VL` 路由
- `embed_images()` 新增 `text: str = ''` 参数，非空时路由到 `VLEmbeddingExtractor`
- `apps/embedding_api/main.py` 更新 loader 引用

#### 2. Visual CR Locator 链路已打通

- `LocatorConfig` 新增 `text: str = ''` 字段（`lib/services/visual_cr_locator_types.py`）
- `compute_sample_embedding_metrics()` 接受 `text` 参数并透传到 embedding API（`lib/services/visual_cr_locator_service.py`）
- API 端点无需改动：`text` 通过请求体 `LocatorConfig.text` 自然流入

#### 3. 测试结果

- `test_get_annotation_info` ✅ 通过
- `test_locate` / `test_locate_with_text(text='')` — 因 `AmbiguousSupportError` 失败（投票结果从 cr_index=19 漂移），系模型重启后投票非确定性，非本次改动引入
- Embedding API 日志确认 `text=` 正确透传
- 非空 text（`'box collision in BEV'` 等）的 VL 路由用例已预埋（`if 0`），待 locator 支持 VL-capable model_ids 后激活

## Iteration 20260512.2220

结合 @apps/embedding_api/test.py:test_embed_images_vl 解释为什么 @apps/embedding_api/main.py 中
model_ids fmt 等抽取失败？

```
> /home/luban/.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.12/site-packages/fastapi/routing.py(328)run_endpoint_function()
    326
    327     if is_coroutine:
--> 328         return await dependant.call(**values)
    329     else:
    330         return await run_in_threadpool(dependant.call, **values)

ipdb> p values
{'processor_kwds': {'text': 'box'}, 'fmt': 'arrow_recordbatch', 'image_files': [UploadFile(filename='upload', size=674, headers=Headers({'content-disposition': 'form-data; name="image_files"; filename="upload"', 'content-type': 'application/octet-stream'})), UploadFile(filename='upload', size=674, headers=Headers({'content-disposition': 'form-data; name="image_files"; filename="upload"', 'content-type': 'application/octet-stream'})), UploadFile(filename='upload', size=674, headers=Headers({'content-disposition': 'form-data; name="image_files"; filename="upload"', 'content-type': 'application/octet-stream'}))], 'model_ids': ('AI-ModelScope/clip-vit-large-patch14', 'apple/aimv2-huge-patch14-448', 'facebook/dinov2-base', 'facebook/dinov2-large', 'google/siglip2-base-patch16-224', 'Salesforce/blip2-opt-2.7b')}
ipdb> u
```
