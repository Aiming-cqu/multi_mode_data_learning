# VL Embedding Text Conditionality

验证 VL embedding 模型对 text prompt 的条件响应方向性。

## 目标

- **确定性**: 相同输入重复推理，embedding 完全一致 (cosine sim > 0.99)
- **敏感性**: 同一图像 + 不同 text → embedding 显著不同 (cosine sim < 0.99)
- **方向性**: 图像主导 embedding 空间 (intra-image sim > intra-text sim)，且 text 效果非平凡 (intra-image > cross)

## 环境

- Pixi env: `vllm`
- 需要 MODELSCOPE_CACHE 环境变量
- 需要 GPU

## 运行

```bash
pixi run -e vllm -- python experiments/vl-conditionality/test_vl_conditionality.py
```
