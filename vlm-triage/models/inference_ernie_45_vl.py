r"""
ERNIE-4.5-VL 多模态推理模块。

提供 ERNIE-4.5-VL-28B-A3B-PT 模型的加载与多模态（图文）推理功能。
当前作为参考实现保留：当模型卡未明确声明 vLLM backend support，或官方路径更偏向
transformers / FastDeploy 时，优先复用这里而不是强行补 `vllm serve` 脚本。

主要组件:
    - Ernie45VLInference: ERNIE-4.5-VL 推理服务类
"""

from __future__ import absolute_import, annotations

import logging, typing as tp

import torch
from modelscope import AutoProcessor, AutoModelForCausalLM

logger: logging.Logger = logging.getLogger(name=__name__)

DEFAULT_MODEL_PATH: str = "PaddlePaddle/ERNIE-4.5-VL-28B-A3B-PT"


class Ernie45VLInference:
    r"""
    ERNIE-4.5-VL 多模态推理服务。

    封装模型加载与图文推理流程，支持传入自定义消息进行生成。

    Args:
        model_path: 模型路径或 HuggingFace/ModelScope 模型标识符
    """

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH) -> None:
        self.model_path: str = model_path
        self.model: tp.Any = None
        self.processor: tp.Any = None

    def load_model(self) -> None:
        r"""加载模型和处理器，并完成预处理器绑定。"""
        try:
            logger.info("正在加载 ERNIE-4.5-VL 模型: %s", self.model_path)
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                device_map="auto",
                torch_dtype=torch.bfloat16,
                trust_remote_code=True,
            )
            self.processor = AutoProcessor.from_pretrained(
                self.model_path, trust_remote_code=True,
            )
            self.processor.eval()
            self.model.add_image_preprocess(self.processor)
            logger.info("模型加载完成")
        except Exception:
            logger.exception("加载 ERNIE-4.5-VL 模型失败")
            raise

    def infer(
        self,
        messages: list[dict[str, tp.Any]],
        *,
        max_new_tokens: int = 128,
        enable_thinking: bool = False,
    ) -> str:
        r"""
        对给定的多模态消息执行推理。

        Args:
            messages: OpenAI 格式的对话消息列表
            max_new_tokens: 最大生成 token 数
            enable_thinking: 是否启用思考模式

        Returns:
            模型生成的文本
        """
        try:
            text = self.processor.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=enable_thinking,
            )
            image_inputs, video_inputs = self.processor.process_vision_info(messages)
            inputs = self.processor(
                text=[text],
                images=image_inputs,
                videos=video_inputs,
                padding=True,
                return_tensors="pt",
            )

            device: torch.device = next(self.model.parameters()).device
            inputs = inputs.to(device)

            generated_ids = self.model.generate(
                inputs=inputs["input_ids"].to(device),
                **inputs,
                max_new_tokens=max_new_tokens,
            )
            output_text: str = self.processor.decode(generated_ids[0])
            logger.info("推理完成，输出长度: %d", len(output_text))
            return output_text
        except Exception:
            logger.exception("ERNIE-4.5-VL 推理失败")
            raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    engine = Ernie45VLInference()
    engine.load_model()

    demo_messages: list[dict[str, tp.Any]] = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe the image."},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "https://paddlenlp.bj.bcebos.com/datasets/paddlemix/demo_images/example1.jpg",
                    },
                },
            ],
        },
    ]
    result = engine.infer(demo_messages)
    logger.info("输出: %s", result)
