r"""
Valley-Eagle-7B 多模态推理模块。

当前作为参考实现保留：`Hyggge/Valley-Eagle-7B` 在当前仓库环境中无法稳定通过
`vllm serve` 启动，错误表现为 `model type valley` 无法被 Transformers / vLLM
识别。因此这里直接复用上游 README 中的 `ValleyEagleChat` 路径，提供单文件参考实现。

主要组件:
    - ValleyEagleInference: Valley-Eagle-7B 推理服务类
"""

from __future__ import annotations

import importlib
import logging
import sys
import typing as tp
from pathlib import Path

import PIL.Image
from modelscope import snapshot_download

logger: logging.Logger = logging.getLogger(name=__name__)

DEFAULT_MODEL_PATH: str = "Hyggge/Valley-Eagle-7B"


def _normalize_chat_history(
    messages: list[dict[str, tp.Any]],
) -> list[dict[str, str]]:
    r"""将 OpenAI 风格消息压成 Valley README 所需的简单 chat_history 结构。"""
    normalized: list[dict[str, str]] = []
    for message in messages:
        role = str(message["role"])
        content = message.get("content", "")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(str(item.get("text", "")))
            text = "\n".join(part for part in text_parts if part)
        else:
            text = str(content)
        normalized.append({"role": role, "content": text})
    return normalized


class ValleyEagleInference:
    r"""
    Valley-Eagle-7B 推理服务。

    通过 snapshot_download + 动态导入 `valley_eagle_chat`，尽量贴近上游 README 的
    官方调用方式。

    Args:
        model_path: 模型路径或 ModelScope 模型标识符
        padding_side: 传给 `ValleyEagleChat` 的 padding_side
    """

    def __init__(
        self,
        model_path: str = DEFAULT_MODEL_PATH,
        *,
        padding_side: str = "left",
    ) -> None:
        self.model_path = model_path
        self.padding_side = padding_side
        self.model_dir: Optional[Path] = None
        self.model: tp.Any = None

    def _resolve_model_dir(self) -> Path:
        path = Path(self.model_path)
        if path.exists():
            return path
        downloaded = snapshot_download(self.model_path)
        return Path(downloaded)

    def load_model(self) -> None:
        r"""下载模型目录并按 README 的 ValleyEagleChat 方式加载。"""
        try:
            self.model_dir = self._resolve_model_dir()
            sys.path.insert(0, str(self.model_dir))
            valley_chat_module = importlib.import_module("valley_eagle_chat")
            valley_chat_cls = getattr(valley_chat_module, "ValleyEagleChat")
            self.model = valley_chat_cls(
                model_path=str(self.model_dir),
                padding_side=self.padding_side,
            )
            logger.info("Valley-Eagle-7B 模型加载完成: %s", self.model_dir)
        except Exception:
            logger.exception("加载 Valley-Eagle-7B 模型失败")
            raise

    def infer(
        self,
        messages: list[dict[str, tp.Any]],
        images: Optional[list[PIL.Image.Image]] = None,
    ) -> str:
        r"""
        对给定消息和图像执行推理。

        Args:
            messages: OpenAI 风格消息列表；会被压缩成 Valley README 所需的 chat_history
            images: PIL 图像列表；视频场景可先自行抽帧再传入

        Returns:
            模型生成的文本
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        request = {
            "chat_history": _normalize_chat_history(messages),
            "images": images or [],
        }
        try:
            response: str = self.model(request)
            logger.info("推理完成，输出长度: %d", len(response))
            return response
        except Exception:
            logger.exception("Valley-Eagle-7B 推理失败")
            raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    demo_image = PIL.Image.new("RGB", (224, 224), color="white")
    demo_messages: list[dict[str, tp.Any]] = [
        {
            "role": "system",
            "content": "You are Valley, developed by ByteDance. You are a helpful assistant.",
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe the given image."},
            ],
        },
    ]

    engine = ValleyEagleInference()
    engine.load_model()
    result = engine.infer(demo_messages, [demo_image])
    logger.info("输出: %s", result)
