#!/usr/bin/env -S pixi run -e vllm -- test -s

from __future__ import absolute_import, annotations

import abc, logging, typing as tp
import PIL.Image
import torch
import torch.nn

from transformers import AutoModel, AutoProcessor, ProcessorMixin
from typing_extensions import override

from ..utils.torch_utils import ensure_2d, inspect_tensors, torch_to


_T = tp.TypeVar('_T')

logger: logging.Logger = logging.getLogger(name=__name__)


class EmbeddingExtractorBase(abc.ABC, tp.Generic[_T]):
    r"""
    Abstract base class for embedding extractors.

    Provides common functionality for loading models and processors,
    with device management and dtype configuration.

    Type Parameters:
        _T: The input type this extractor accepts (e.g., PIL.Image.Image).

    Attributes:
        model_id: HuggingFace model identifier or local path.
        device: Torch device for model inference.
        dtype: Optional torch dtype for model weights.
    """

    def __init__(
        self,
        model_id: str,
        *,
        device: tp.Optional[tp.Union[torch.device, str]] = None,
        dtype: tp.Optional[torch.dtype] = None,
        trust_remote_code: bool = False,
    ):
        r"""
        Initialize the embedding extractor.

        Args:
            model_id: HuggingFace model identifier or local path to model.
            device: Torch device for inference. Defaults to CUDA if available,
                otherwise CPU.
            dtype: Optional torch dtype for model weights.
            trust_remote_code: Whether to trust remote code from the model repo.
        """
        self.model_id: str = model_id
        self.device: torch.device = torch.device(
            device or ("cuda" if torch.cuda.is_available() else "cpu")
        )

        self.set_dtype(dtype)

        logger.info('load model %r', self.model_id)
        self.model: torch.nn.Module = AutoModel.from_pretrained(
            self.model_id,
            device_map=self.device,
            dtype=self.dtype,
            attn_implementation="sdpa",
            trust_remote_code=trust_remote_code,
        )
        self.model.eval()
        self.model.to(device=self.device)  # NOTE: never cast by yourself

        logger.info('load processor for %r', self.model_id)
        self.processor: ProcessorMixin = AutoProcessor.from_pretrained(
            self.model_id,
            trust_remote_code=trust_remote_code,
        )

    def __repr__(self) -> str:
        return (
            f'<{self.__class__.__name__}'
            f' model_id={self.model_id!r}'
            f' device={self.device!r}'
            f' dtype={self.dtype!r}'
            '>'
        )

    @abc.abstractmethod
    def extract(self, inputs: tp.Sequence[_T], **processor_kwds) -> torch.Tensor:
        r"""
        Extract embeddings from a sequence of inputs.

        Args:
            inputs: Sequence of inputs to process.
            **processor_kwds: Additional keyword arguments passed to the processor.

        Returns:
            NxC tensor where N is the number of inputs and C is the
            embedding dimension.
        """
        ...

    def set_dtype(self, dtype: tp.Optional[torch.dtype]):
        self.dtype: tp.Optional[torch.dtype] = dtype
        # if not self.dtype and self.device.type == "cuda":
        #     self.dtype = torch.float16

    def to(self, device: tp.Union[torch.device, str]) -> tp.Self:
        r"""
        Transfer the model to a different device.

        Args:
            device: Target torch device or device string.

        Returns:
            Self reference for method chaining.
        """

        device = torch.device(device)
        logger.info('transfer %r to %r', self, device)
        self.model.to(device)
        self.device = device
        return self


class ImageEmbeddingExtractor(EmbeddingExtractorBase[PIL.Image.Image]):
    r"""
    Embedding extractor for PIL images.

    Extracts visual embeddings from images using vision transformers
    or CNN-based models. Supports various output formats including
    image_embeds, pooler_output, and last_hidden_state.
    """

    @override
    def extract(self, inputs: tp.Sequence[PIL.Image.Image], **processor_kwds) -> torch.Tensor:
        r"""
        Extract embeddings from a sequence of PIL images.

        Processes images through the model and extracts embeddings from
        various possible output locations (image_embeds, pooler_output,
        last_hidden_state, or qformer_outputs).

        Args:
            inputs: Sequence of PIL Image objects.
            **processor_kwds: Additional arguments passed to the processor
                (e.g., do_rescale, return_tensors).

        Returns:
            NxC tensor of image embeddings.

        Raises:
            NotImplementedError: If unable to locate embedding tensor in
                model outputs.
        """

        inp_tensors = self.processor(images=list(inputs), return_tensors="pt", **processor_kwds)
        inp_tensors = torch_to(inp_tensors, self.device)

        inspect_tensors(f'{self.model_id}.inputs', inp_tensors, once=True, print_fn=logger.info)
        with torch.no_grad(), torch.autocast(self.device.type, dtype=self.dtype):
            out_tensors = self.model(**inp_tensors)
        inspect_tensors(
            f'{self.model_id}.outputs', out_tensors, once=True, print_fn=logger.info
        )

        if isinstance(v := getattr(out_tensors, "image_embeds", None), torch.Tensor):
            return ensure_2d(v)
        elif isinstance(v := getattr(out_tensors, "pooler_output", None), torch.Tensor):
            return ensure_2d(v)
        elif isinstance(v := getattr(out_tensors, "last_hidden_state", None), torch.Tensor):
            # use CLS token
            return v[:, 0, :]
        elif (o := getattr(out_tensors, "qformer_outputs", None)) is not None:
            # use CLS token
            return o.last_hidden_state[:, 0, :]

        raise NotImplementedError(f'Unable to locate embedding tensor in {out_tensors=}')


class VLEmbeddingExtractor(ImageEmbeddingExtractor):
    r"""
    Embedding extractor for VL (Vision-Language) models such as Qwen3-VL-Embedding.

    Unlike pure vision models, VL models require image placeholder tokens
    (e.g. ``<|image_pad|>``) in ``input_ids`` so the model can align image
    features with text tokens.  This class uses the processor's chat template
    to produce correct ``input_ids`` and applies last-token pooling to obtain
    the final embedding vector.
    """

    @override
    def set_dtype(self, dtype: tp.Optional[torch.dtype]):
        self.dtype: tp.Optional[torch.dtype] = dtype
        if not self.dtype and self.device.type == "cuda":
            self.dtype = torch.bfloat16

    @override
    def extract(
        self, inputs: tp.Sequence[PIL.Image.Image], *, text: str, **processor_kwds
    ) -> torch.Tensor:
        r"""
        Extract embeddings from a sequence of PIL images using a VL model.

        Each image is wrapped in its own chat-template conversation together
        with *text* (repeated per image).  The processor expands the image
        placeholder into the correct number of tokens.  The model's last
        valid hidden state per sample is taken as the embedding.

        Args:
            inputs: Sequence of PIL Image objects.
            text: Text query placed alongside each image in the conversation.

        Returns:
            NxC tensor of embeddings.
        """

        if len(inputs) == 0: raise ValueError('Input sequence is empty')  # fmt: skip

        # Build one conversation per image, each containing the image placeholder + text
        conversations: list[list[dict[str, tp.Any]]] = []
        for _ in inputs:
            conversations.append(
                [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image"},
                            {"type": "text", "text": text},
                        ],
                    }
                ]
            )
        logger.debug('conversations[0]=%r', conversations[0])

        text_inputs: list[str] = self.processor.apply_chat_template(
            conversations,
            tokenize=False,
            add_generation_prompt=True,
        )
        logger.debug('text_inputs[0]=%r', text_inputs[0])

        inp_tensors: dict[str, torch.Tensor] = self.processor(
            text=text_inputs,
            images=list(inputs),
            return_tensors="pt",
            padding=True,
        )
        inp_tensors = torch_to(inp_tensors, self.device)

        inspect_tensors(f'{self.model_id}.inputs', inp_tensors, once=True, print_fn=logger.info)
        with torch.no_grad(), torch.autocast(self.device.type, dtype=self.dtype):
            out_tensors = self.model(**inp_tensors)
        inspect_tensors(
            f'{self.model_id}.outputs', out_tensors, once=True, print_fn=logger.info
        )

        # Last-token pooling (standard for VL embedding models)
        hidden_nsc: torch.Tensor = out_tensors.last_hidden_state
        mask_ns: torch.Tensor = inp_tensors['attention_mask']
        logger.debug('hidden_nsc.shape=%r mask_ns.shape=%r', hidden_nsc.shape, mask_ns.shape)

        last_pos_n: torch.Tensor = mask_ns.sum(dim=1) - 1
        batch_n: torch.Tensor = torch.arange(hidden_nsc.shape[0], device=hidden_nsc.device)
        embedding_nc: torch.Tensor = hidden_nsc[batch_n, last_pos_n]
        return embedding_nc


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
            # 'jinaai/jina-embeddings-v4',  # FIXME: TypeError: JinaEmbeddingsV4Model.forward() missing 1 required positional argument: 'task_label'
            # 'nv-community/nemotron-colembed-vl-8b-v2',  # FIXME: RuntimeError: Expected tensor for argument #1 'indices' to have one of the following scalar types: Long, Int; but got torch.cuda.FloatTensor instead (while checking...
            'Salesforce/blip2-opt-2.7b',
        ]:
            print(f'test {model_id=}')

            extractor = ImageEmbeddingExtractor(
                f'{models_dir}/{model_id}',
            )
            images = [PIL.Image.new("RGB", (224, 224))]
            e_nc = extractor.extract(images, text='')

            assert e_nc.ndim == 2, e_nc.shape
            assert e_nc.shape[0] == len(images), e_nc.shape

    finally:
        if __name__ == '__main__': globals().update(locals())  # fmt: skip


def test_vl_embedding_extractor():
    try:
        import os

        models_dir = f'{os.environ["MODELSCOPE_CACHE"]}/models'

        for model_id in [
            # 'AI-ModelScope/PE-Lang-G14-448',  # FIXME: missing config.json
            # 'BAAI/BGE-VL-MLLM-S1',  # FIXME: AttributeError: 'LLaVANextForEmbedding' object has no attribute 'image_newline'
            # 'iic/GVE-7B',  # FIXME: ImportError: cannot import name 'QWEN2_5_VL_INPUTS_DOCSTRING' from 'transformers.models.qwen2_5_vl.modeling_qwen2_5_vl' (/home/luban/.pixi/cache/envs/vlm-triage-16667750860955762807/envs/vllm/lib/python3.13/site-packages/transformers/models/qwen2_5_vl/modeling_qwen2_5_vl.py)
            # 'jinaai/jina-embeddings-v4',  # FIXME: ValueError: Cannot use apply_chat_template because this processor does not have a chat template.
            'nv-community/nemotron-colembed-vl-8b-v2',
            'Qwen/Qwen3-VL-Embedding-8B',
        ]:
            print(f'test {model_id=}')

            model_path = f'{models_dir}/{model_id}'
            extractor = VLEmbeddingExtractor(model_path, trust_remote_code=True)
            images = [PIL.Image.new("RGB", (224, 224))]
            e_nc = extractor.extract(images, text='black')

            assert e_nc.ndim == 2, e_nc.shape
            assert e_nc.shape[0] == len(images), e_nc.shape

    finally:
        if __name__ == '__main__': globals().update(locals())  # fmt: skip


def test_vl_embedding_text_conditionality():
    r"""
    测试 VL embedding 的 text 条件性。

    使用纯色 PIL 图像 (红、绿、蓝) 搭配不同 text 输入，验证 VL embedding
    模型是否正确响应 text 条件。

    验证:
        - 确定性: 相同输入重复推理，embedding 完全一致 (cosine sim > 0.99)
        - 敏感性: 同一图像 + 不同 text → embedding 显著不同 (cosine sim < 0.99)
        - 方向性: 图像主导 embedding 空间 (intra-image sim > intra-text sim)，
          且 text 效果非平凡 (intra-image > cross)

    Parameters:
        -
    """
    try:
        import os

        import torch.nn.functional as F

        models_dir = f'{os.environ["MODELSCOPE_CACHE"]}/models'

        for model_id in [
            'Qwen/Qwen3-VL-Embedding-8B',
        ]:
            print(f'test {model_id=}')

            model_path = f'{models_dir}/{model_id}'
            extractor = VLEmbeddingExtractor(model_path, trust_remote_code=True)

            # Solid-color test images: red, green, blue
            color_rgb: dict[str, tuple[int, int, int]] = {
                'red': (255, 0, 0),
                'green': (0, 255, 0),
                'blue': (0, 0, 255),
            }
            color_images: dict[str, PIL.Image.Image] = {
                name: PIL.Image.new('RGB', (224, 224), rgb)
                for name, rgb in color_rgb.items()
            }
            all_images: list[PIL.Image.Image] = list(color_images.values())
            color_names: list[str] = list(color_images.keys())

            # Extract embeddings: 3 images × 3 text queries + 1 repeat for determinism
            e_red_nc: torch.Tensor = extractor.extract(all_images, text='red')
            e_green_nc: torch.Tensor = extractor.extract(all_images, text='green')
            e_blue_nc: torch.Tensor = extractor.extract(all_images, text='blue')
            e_red2_nc: torch.Tensor = extractor.extract(all_images, text='red')  # determinism

            # --- Test 1: Determinism ---
            sim_det_n: torch.Tensor = F.cosine_similarity(e_red_nc, e_red2_nc)
            print(f'determinism sim: {sim_det_n}')
            assert (sim_det_n > 0.99).all(), f'determinism failed: {sim_det_n}'

            # --- Test 2: Sensitivity ---
            sim_red_vs_blue_n: torch.Tensor = F.cosine_similarity(e_red_nc, e_blue_nc)
            sim_red_vs_green_n: torch.Tensor = F.cosine_similarity(e_red_nc, e_green_nc)
            print(f'sensitivity (red vs blue text): {sim_red_vs_blue_n}')
            print(f'sensitivity (red vs green text): {sim_red_vs_green_n}')
            assert (sim_red_vs_blue_n < 0.99).all(), f'sensitivity failed: {sim_red_vs_blue_n}'
            assert (sim_red_vs_green_n < 0.99).all(), f'sensitivity failed: {sim_red_vs_green_n}'

            # --- Test 3: Directionality ---
            # Build 9 embeddings matrix: rows ordered by text, columns by image
            # Layout: [img0+txt0, img1+txt0, img2+txt0, img0+txt1, ...]
            all_e_nc: torch.Tensor = torch.cat([e_red_nc, e_green_nc, e_blue_nc])
            all_e_norm_nc: torch.Tensor = F.normalize(all_e_nc, p=2, dim=-1)
            sim_99: torch.Tensor = all_e_norm_nc @ all_e_norm_nc.T

            # Labels: img_color+text_color
            labels: list[str] = [
                f'{img}+{txt}'
                for txt in color_names
                for img in color_names
            ]
            print('Cosine similarity matrix (9×9):')
            for i, label in enumerate(labels):
                row = ', '.join(f'{sim_99[i, j].item():.3f}' for j in range(9))
                print(f'  {label:15s}: [{row}]')

            # Partition off-diagonal pairs into intra-image vs intra-text
            intra_image_sims: list[float] = []  # same image, different text
            intra_text_sims: list[float] = []  # same text, different image
            cross_sims: list[float] = []  # different image AND different text
            for i in range(9):
                img_i: str = labels[i].split('+')[0]
                txt_i: str = labels[i].split('+')[1]
                for j in range(i + 1, 9):
                    img_j: str = labels[j].split('+')[0]
                    txt_j: str = labels[j].split('+')[1]
                    s: float = sim_99[i, j].item()
                    same_img: bool = img_i == img_j
                    same_txt: bool = txt_i == txt_j
                    if same_img and not same_txt:
                        intra_image_sims.append(s)
                    elif same_txt and not same_img:
                        intra_text_sims.append(s)
                    elif not same_img and not same_txt:
                        cross_sims.append(s)

            avg_intra_image: float = sum(intra_image_sims) / len(intra_image_sims)
            avg_intra_text: float = sum(intra_text_sims) / len(intra_text_sims)
            avg_cross: float = sum(cross_sims) / len(cross_sims)
            print(f'avg intra-image sim: {avg_intra_image:.4f}  (same image, different text)')
            print(f'avg intra-text sim:  {avg_intra_text:.4f}  (same text, different image)')
            print(f'avg cross sim:       {avg_cross:.4f}  (different image AND text)')

            # 3a: Image dominance — same image with different text is more similar
            #     than different image with same text (image signal > text signal)
            assert avg_intra_image > avg_intra_text, (
                f'image should dominate: intra_image={avg_intra_image:.4f} > intra_text={avg_intra_text:.4f}'
            )

            # 3b: Text effect is non-trivial — switching text changes the embedding
            #     more than random variation: intra-image < 1.0 is already covered
            #     by sensitivity. Here we verify text adds structure: same-image
            #     pairs (text varies) are more similar than fully cross pairs.
            assert avg_intra_image > avg_cross, (
                f'shared image should be more similar than fully cross: '
                f'intra_image={avg_intra_image:.4f} > cross={avg_cross:.4f}'
            )

    finally:
        if __name__ == '__main__': globals().update(locals())  # fmt: skip


if __name__ == '__main__':
    from conflog import configure_logging, configure_auto_tracing

    configure_logging(env="test")
    configure_auto_tracing(env="test")

    test_image_embedding_extractor()
    test_vl_embedding_extractor()
    test_vl_embedding_text_conditionality()
