import os
from functools import partial
from typing import Dict, Optional

from data_juicer.ops.base_op import OPERATORS
from data_juicer.utils.lazy_loader import LazyLoader

from .ray_vllm_pipeline import RayVLLMEnginePipeline

torch = LazyLoader("torch")
vllm = LazyLoader("vllm")

OP_NAME = "llm_ray_vllm_engine_pipeline"


@OPERATORS.register_module(OP_NAME)
class LLMRayVLLMEnginePipeline(RayVLLMEnginePipeline):
    """
    Pipeline to generate response using vLLM engine on Ray.
    This pipeline leverages the vLLM engine for efficient large language model inference.
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
        api_url: str = None,
        api_key: str = None,
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
        :param api_url: Base URL of the OpenAI API
        :param api_key: API key for authentication
        :param kwargs: Extra keyword arguments.
        """
        super().__init__(accelerator_type=accelerator_type, **kwargs)

        self.api_or_hf_model = api_or_hf_model
        self.is_hf_model = is_hf_model
        self.system_prompt = system_prompt
        self.sampling_params = sampling_params or {}
        self.api_url = api_url
        self.api_key = api_key

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

        if self.is_hf_model:
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
                has_image=False,
                accelerator_type=self.accelerator_type,
            )
        else:
            from ray.data.llm import HttpRequestProcessorConfig

            if not self.api_url:
                base_url = os.environ.get("OPENAI_BASE_URL", None)
                if base_url:
                    from urllib.parse import urljoin

                    self.api_url = urljoin(base_url, "chat/completions")
            if not self.api_key:
                self.api_key = os.environ.get("OPENAI_API_KEY", None)

            if not self.api_url:
                raise ValueError("Please provide `api_url` or set OPENAI_BASE_URL environment variable.")
            if not self.api_key:
                raise ValueError("Please provide `api_key` or set OPENAI_API_KEY environment variable.")

            self.config = HttpRequestProcessorConfig(
                url=self.api_url, headers={"Authorization": f"Bearer {self.api_key}"}
            )

    @staticmethod
    def preprocess_fn(row: Dict, query_key: str, system_prompt: Optional[str], sampling_params: Dict) -> Dict:
        input_prompt = row[query_key]
        messages = [{"role": "user", "content": input_prompt}]
        if system_prompt:
            messages.insert(0, {"role": "system", "content": system_prompt})
        return dict(messages=messages, sampling_params=sampling_params)

    @staticmethod
    def postprocess_fn(row: Dict, response_key: str, ori_columns: list) -> Dict:
        output = row["generated_text"]
        out_row = {k: v for k, v in row.items() if k in ori_columns}
        out_row[response_key] = output
        return out_row

    @staticmethod
    def preprocess_fn_api(
        row: Dict, model: str, query_key: str, system_prompt: Optional[str], sampling_params: Optional[Dict] = None
    ) -> Dict:
        input_prompt = row[query_key]

        messages = [{"role": "user", "content": input_prompt}]
        if system_prompt:
            messages.insert(0, {"role": "system", "content": system_prompt})

        sampling_params = {} if not sampling_params else sampling_params

        inp = dict(payload=dict(model=model, messages=messages, **sampling_params))

        return inp

    @staticmethod
    def postprocess_fn_api(row: Dict, response_key: str, ori_columns: list) -> Dict:
        if row.get("http_response") and row["http_response"].get("choices", None):
            response = row["http_response"]["choices"][0]["message"]["content"]
        else:
            response = None

        out_row = {k: v for k, v in row.items() if k in ori_columns}
        out_row[response_key] = response
        return out_row

    def run(self, dataset, *, exporter=None, tracer=None, reduce=True):
        # keep original columns, for filter useless columns generated in the middle stages
        ori_columns = dataset.columns()
        if self.response_key not in ori_columns:
            ori_columns.append(self.response_key)

        if self.is_hf_model:
            preprocess_fn = partial(
                self.preprocess_fn,
                query_key=self.query_key,
                system_prompt=self.system_prompt,
                sampling_params=self.sampling_params,
            )
            postprocess_fn = partial(self.postprocess_fn, response_key=self.response_key, ori_columns=ori_columns)
        else:
            preprocess_fn = partial(
                self.preprocess_fn_api,
                model=self.api_or_hf_model,
                query_key=self.query_key,
                system_prompt=self.system_prompt,
                sampling_params=self.sampling_params,
            )
            postprocess_fn = partial(self.postprocess_fn_api, response_key=self.response_key, ori_columns=ori_columns)

        from ray.data.llm import build_llm_processor

        processor = build_llm_processor(
            self.config,
            preprocess=preprocess_fn,
            postprocess=postprocess_fn,
        )

        return processor(dataset)
