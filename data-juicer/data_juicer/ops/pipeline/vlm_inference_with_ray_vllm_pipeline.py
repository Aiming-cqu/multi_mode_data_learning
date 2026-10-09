from functools import partial
from typing import Dict, Optional

from data_juicer.ops.base_op import OPERATORS
from data_juicer.utils.lazy_loader import LazyLoader
from data_juicer.utils.mm_utils import load_image

from .ray_vllm_pipeline import RayVLLMEnginePipeline

torch = LazyLoader("torch")
vllm = LazyLoader("vllm")

OP_NAME = "vlm_ray_vllm_engine_pipeline"


@OPERATORS.register_module(OP_NAME)
class VLMRayVLLMEnginePipeline(RayVLLMEnginePipeline):
    """
    Pipeline to generate response using vLLM engine on Ray.
    This pipeline leverages the vLLM engine for efficient large vision language model inference.
    More details about ray vLLM engine can be found at: https://docs.ray.io/en/latest/data/working-with-llms.html
    """

    _accelerator = "cuda"

    def __init__(
        self,
        api_or_hf_model: str = "Qwen/Qwen2.5-7B-Instruct",
        is_hf_model: bool = True,
        *,
        system_prompt: Optional[str] = None,
        accelerator_type: Optional[str] = None,
        sampling_params: Optional[Dict] = None,
        engine_kwargs: Optional[Dict] = None,
        **kwargs,
    ):
        """
        Initialization method.

        :param api_or_hf_model: API or huggingface model name.
        :param system_prompt: System prompt for guiding the optimization task.
        :param accelerator_type: The type of accelerator to use (e.g., "V100", "A100").
            Default to None, meaning that only the CPU will be used.
        :param sampling_params: Sampling parameters for text generation (e.g.,
            {'temperature': 0.9, 'top_p': 0.95}).
        :param engine_kwargs: The kwargs to pass to the vLLM engine.
            See documentation for details: https://docs.vllm.ai/en/latest/api/vllm/engine/arg_utils/#vllm.engine.arg_utils.AsyncEngineArgs.
        :param kwargs: Extra keyword arguments.
        """
        super().__init__(accelerator_type=accelerator_type, **kwargs)

        self.is_hf_model = is_hf_model
        if not self.is_hf_model:
            raise NotImplementedError("Only huggingface model is supported for now.")

        self.system_prompt = system_prompt
        self.sampling_params = sampling_params or {}

        _default_engine_kwargs = dict(
            enable_chunked_prefill=True,
            max_num_batched_tokens=4096,  # Reduce if CUDA OOM occurs
            max_model_len=4096,  # Constrain to fit test GPU memory
            tensor_parallel_size=1,
            pipeline_parallel_size=1,
            trust_remote_code=True,
        )

        if engine_kwargs:
            _default_engine_kwargs.update(engine_kwargs)

        from ray.data.llm import vLLMEngineProcessorConfig

        self.config = vLLMEngineProcessorConfig(
            model_source=api_or_hf_model,
            engine_kwargs=_default_engine_kwargs,
            concurrency=self.num_proc,
            batch_size=self.batch_size,
            apply_chat_template=True,
            chat_template=None,
            tokenize=True,
            detokenize=True,
            has_image=True,
            accelerator_type=self.accelerator_type,
        )

    @staticmethod
    def vision_preprocess(
        row: dict, query_key: str, image_key: str, system_prompt: Optional[str], sampling_params: Dict
    ) -> dict:
        """
        Preprocessing function for vision-language model inputs.
        """
        messages = []

        if system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": system_prompt,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": row[query_key] + "\n\n"},
                    *[{"type": "image", "image": load_image(img), "detail": "low"} for img in row[image_key]],
                ],
            }
        )
        return dict(messages=messages, sampling_params=sampling_params)

    @staticmethod
    def postprocess_fn(row: Dict, response_key: str, ori_columns: list) -> Dict:
        output = row["generated_text"]
        out_row = {k: v for k, v in row.items() if k in ori_columns}
        out_row[response_key] = output

        return out_row

    def run(self, dataset, *, exporter=None, tracer=None, reduce=True):
        # keep original columns, for filter useless columns generated in the middle stages
        ori_columns = dataset.columns()
        if self.response_key not in ori_columns:
            ori_columns.append(self.response_key)

        vision_preprocess = partial(
            self.vision_preprocess,
            query_key=self.query_key,
            image_key=self.image_key,
            system_prompt=self.system_prompt,
            sampling_params=self.sampling_params,
        )

        postprocess_fn = partial(
            self.postprocess_fn,
            response_key=self.response_key,
            ori_columns=ori_columns,
        )

        from ray.data.llm import build_llm_processor

        processor = build_llm_processor(
            self.config,
            preprocess=vision_preprocess,
            postprocess=postprocess_fn,
        )

        return processor(dataset)
