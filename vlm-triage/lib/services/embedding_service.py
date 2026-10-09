#!/usr/bin/env -S pixi run -e vllm -- test -s

r"""
图像 embedding 提取与相似度计算服务模块。

提供使用多个预训练模型从图像中提取 embedding 的方法，
以及使用各种度量计算成对相似度的功能。

主要组件:
    - EmbeddingService: embedding 提取与相似度计算服务类
    - ImageEmbeddingExtractorLoader: 图像 embedding 提取器加载器

Attributes:
    -
"""

from __future__ import absolute_import, annotations

import io, os, threading, typing as tp
import PIL.Image
import logfire
import torch

from typing_extensions import override

from ..algorithms.embedding_extractor import (
    EmbeddingExtractorBase,
    ImageEmbeddingExtractor,
    VLEmbeddingExtractor,
)
from ..algorithms.embedding_metrics import EmbeddingSimilarityBase
from .model_offloading import ModelLoaderBase, ModelContextManager


class EmbeddingExtractorLoader(ModelLoaderBase):
    r"""
    图像 embedding 提取器的模型加载器。
    """

    @logfire.instrument
    @override
    def load_model(self, model_id: str, *, device: torch.device) -> ImageEmbeddingExtractor:
        r"""
        加载图像 embedding 提取器。

        Args:
            model_id: 模型标识符或路径
            device: 模型推理的 Torch 设备

        Returns:
            配置好的 ImageEmbeddingExtractor 实例

        TODO: add VLEmbeddingExtractor support
        """
        model_id, _, kind = model_id.rpartition('#')
        match kind:
            case 'IMAGE': return ImageEmbeddingExtractor(model_id, device=device)  # fmt: skip
            case 'VL': return VLEmbeddingExtractor(model_id, device=device)  # fmt: skip
            case _: raise ValueError(f'Unsupported model kind: {kind} in model_id: {model_id}')


class EmbeddingService:
    r"""
    图像 embedding 提取与相似度计算服务。

    提供使用多个预训练模型从图像中提取 embedding 的方法，
    以及使用各种度量计算成对相似度的功能。

    Args:
        loader: 模型加载器实例
        max_batch_size: 单次批处理的最大图像数量
    """

    semaphore: tp.ClassVar = threading.Semaphore(
        value=int(os.getenv("TRIAGE_EMBEDDING_API_CONCURRENCY", 4))
    )

    @classmethod
    @logfire.instrument(extract_args=False)
    def decode_image(cls, image_data: bytes) -> PIL.Image.Image:
        r"""
        将图像字节解码为 PIL Image。

        Args:
            image_data: 原始图像字节（PNG、JPEG等）

        Returns:
            RGB 格式的 PIL Image
        """
        return PIL.Image.open(io.BytesIO(initial_bytes=image_data)).convert(mode="RGB")

    def __init__(self, loader: EmbeddingExtractorLoader, *, max_batch_size: int = 256):
        r"""
        初始化 embedding 服务。

        Args:
            loader: 模型加载器实例
            max_batch_size: 单次批处理的最大图像数量
        """
        self.loader: EmbeddingExtractorLoader = loader
        self.max_batch_size: int = max_batch_size

    @logfire.instrument(extract_args=["model_ids", "processor_kwds"])
    def embed_images(
        self,
        images_data: tp.Sequence[bytes],
        model_ids: tp.Collection[str],
        text: str = '',
        **processor_kwds: tp.Any,
    ) -> dict[str, torch.Tensor]:
        r"""
        使用指定模型从图像中提取 embedding。

        Args:
            images_data: 图像字节序列
            model_ids: embedding 提取的模型标识符集合
            **processor_kwds: 传递给图像处理器的额外参数

        Returns:
            模型 ID 到 embedding 张量的字典。
            每个张量形状为 (num_images, embedding_dim)
        """
        if (batch_size := len(images_data)) > self.max_batch_size:
            raise ValueError(f'Batch size {batch_size} exceeds limit {self.max_batch_size}')

        with self.semaphore:
            ret = dict[str, torch.Tensor]()
            for model_id in model_ids:
                with self.get_extractor(model_id + ('#VL' if text else '#IMAGE')) as extractor:
                    extractor = tp.cast(EmbeddingExtractorBase[PIL.Image.Image], extractor)
                    with logfire.span('decode {num:d} images', num=len(images_data)):
                        images = list[PIL.Image.Image](map(self.decode_image, images_data))
                    with logfire.span(f'extract with {model_id=}'):
                        e_nc = extractor.extract(images, text=text, **processor_kwds)
                    with logfire.span('transfer to cpu', model_id=model_id):
                        ret[model_id] = e_nc.cpu()
        return ret

    @logfire.instrument(extract_args=["model_ids", "metric_names", "processor_kwds"])
    def compute_images_similarity(
        self,
        images_data: tp.Sequence[bytes],
        model_ids: tp.Sequence[str],
        metric_names: tp.Sequence[str] = ("Cosine", "L2"),
        **processor_kwds: tp.Any,
    ) -> torch.Tensor:
        r"""
        使用 embedding 计算图像之间的相似度分数。

        Args:
            images_data: 图像字节序列
            model_ids: embedding 提取的模型标识符序列
            metric_names: 相似度度量名称序列（如 "Cosine"、"L2"）
            **processor_kwds: 传递给图像处理器的额外参数

        Returns:
            相似度分数张量，形状为 (num_images, num_models, num_metrics, 2)
            - [:, :, :, 0]: 与基准图像（索引 0）的相似度
            - [:, :, :, 1]: 与特征图像（索引 -1）的相似度
        """
        embeddings_by_model: dict[str, torch.Tensor] = self.embed_images(
            images_data, model_ids, **processor_kwds
        )
        ss = list[torch.Tensor]()
        for metric_name in metric_names:
            op = EmbeddingSimilarityBase.Registry[metric_name]()
            for model_id in model_ids:
                e_nc = embeddings_by_model[model_id]
                sb_n = op.compute(e_nc[[0]], e_nc)
                sf_n = op.compute(e_nc[[-1]], e_nc)
                ss.append(sb_n)
                ss.append(sf_n)
        s_xn = torch.concat(ss)
        s_sm2n = s_xn.view(len(metric_names), len(model_ids), 2, len(images_data))
        s_nms2 = s_sm2n.permute(3, 1, 0, 2)
        return s_nms2

    @logfire.instrument
    def get_extractor(self, model_id: str) -> ModelContextManager:
        r"""
        获取指定模型的 embedding 提取器。

        Args:
            model_id: 模型标识符（HuggingFace 模型 ID 或本地路径）

        Returns:
            模型提取器实例
        """
        return self.loader.get(f'{os.environ["MODELSCOPE_CACHE"]}/models/{model_id}')


def test_embedding_service():
    r"""
    使用简单彩色图像测试 EmbeddingService。

    创建不同颜色的测试图像，验证 embedding 提取和相似度计算正常工作。
    """
    try:
        colors = ["red", "yellow", "green"]

        service = EmbeddingService(EmbeddingExtractorLoader())

        images_data = []
        for color in colors:
            image = PIL.Image.new("RGB", (224, 224), color=color)
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            images_data.append(buf.getvalue())

        model_ids = [
            'AI-ModelScope/clip-vit-large-patch14',
            'apple/aimv2-huge-patch14-448',
            'facebook/dinov2-base',
            'facebook/dinov2-large',
            'google/siglip-base-patch16-224',
            'google/siglip-so400m-patch14-384',
            'google/siglip2-base-patch16-224',
            'google/siglip2-so400m-patch16-512',
            'Salesforce/blip2-opt-2.7b',
        ]

        embeddings_by_model = service.embed_images(
            images_data,
            model_ids,
        )
        assert embeddings_by_model[model_ids[0]].shape[0] == 3, embeddings_by_model
        assert embeddings_by_model[model_ids[1]].shape[0] == 3, embeddings_by_model

        s_nms2 = service.compute_images_similarity(
            images_data,
            model_ids,
            metric_names=["Cosine"],
        )
        assert s_nms2.shape == (3, len(model_ids), 1, 2), s_nms2.shape

        b2b_ms = s_nms2[0, ..., 0]
        torch.testing.assert_allclose(b2b_ms, torch.full_like(b2b_ms, 1))
        f2f_ms = s_nms2[-1, ..., 1]
        torch.testing.assert_allclose(f2f_ms, torch.full_like(f2f_ms, 1))

        model_ids = [
            'Qwen/Qwen3-VL-Embedding-8B',
        ]

        for color in colors:
            s_nms2 = service.compute_images_similarity(
                images_data,
                model_ids,
                metric_names=["Cosine"],
                text=color,
            )
            assert s_nms2.shape == (3, len(model_ids), 1, 2), s_nms2.shape

            print(f'{color=} {s_nms2=}')

            b2b_ms = s_nms2[0, ..., 0]
            torch.testing.assert_allclose(b2b_ms, torch.full_like(b2b_ms, 1))
            f2f_ms = s_nms2[-1, ..., 1]
            torch.testing.assert_allclose(f2f_ms, torch.full_like(f2f_ms, 1))

    finally:
        if __name__ == '__main__': globals().update(locals())  # fmt: skip


if __name__ == '__main__':
    from conflog import configure_logging, configure_auto_tracing

    configure_logging(env="test")
    configure_auto_tracing(env="test")

    test_embedding_service()
