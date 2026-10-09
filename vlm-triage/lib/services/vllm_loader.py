#!/usr/bin/env -S pixi run -e vllm -- test -s

from __future__ import absolute_import, annotations

import logging, threading, typing as tp

from ..utils.containers import CacheDict
from ..utils.rwlock import RWLock


logger: logging.Logger = logging.getLogger(name=__name__)


class VllmEngineLike(tp.Protocol):
    r"""最小 vLLM 引擎协议。"""

    def generate(
        self,
        prompts: list[str],
        *args: tp.Any,
        **kwargs: tp.Any,
    ) -> tp.Any:
        r"""Generate text from prompts."""
        ...


VllmEngineFactory = tp.Callable[[str], VllmEngineLike]


class VllmEngineContextManager(tp.ContextManager[VllmEngineLike]):
    r"""vLLM 引擎上下文。

    这里的读写锁不是保护数据读写，而是保护“请求生命周期”：
    - `__enter__` 期间持有读锁，表示有推理请求正在使用引擎；
    - 驱逐流程持有写锁，表示准备关闭引擎；
    - 读写互斥确保引擎不会在请求执行窗口中被 shutdown。
    """

    def __init__(self, engine: VllmEngineLike):
        self.engine: VllmEngineLike = engine
        self._rwlock = RWLock(pre_read=True)

    def __enter__(self) -> VllmEngineLike:
        self._rwlock.acquire_read()
        return self.engine

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: tp.Any,
    ) -> None:
        self._rwlock.release_read()


class VllmModelLoader:
    r"""
    vLLM 模型加载器（PoC）。

    目标：
    1. 保持 loader 语义：`with loader.get(model_id) as engine: ...`
    2. 用 LRU 控制同时驻留的引擎数量
    3. 驱逐时等待正在运行的请求结束，再安全关闭引擎
    """

    def __init__(
        self,
        *,
        max_loaded_models: int = 1,
        engine_factory: VllmEngineFactory | None = None,
        engine_options: tp.Mapping[str, tp.Any] | None = None,
    ):
        if max_loaded_models <= 0:
            raise ValueError(f'max_loaded_models must be positive, got {max_loaded_models}')
        self._engine_options = dict(engine_options or dict[str, tp.Any]())
        self._engine_factory: VllmEngineFactory = engine_factory or self._create_engine
        self._loaded_models = CacheDict[str, VllmEngineContextManager](max_size=max_loaded_models)
        self._rwlock: RWLock = RWLock()
        self._loaded_lock = threading.Lock()

    def _create_engine(self, model_id: str) -> VllmEngineLike:
        r"""Create a vLLM engine using default runtime settings."""
        from vllm import LLM

        return tp.cast(
            VllmEngineLike,
            LLM(
                model=model_id,
                trust_remote_code=True,
                **self._engine_options,
            ),
        )

    def _close_engine(self, model_id: str, engine: VllmEngineLike) -> None:
        r"""Close/shutdown a vLLM engine if the API is available."""
        shutdown = getattr(engine, 'shutdown', None)
        if callable(shutdown):
            logger.info('shutdown vllm engine %r', model_id)
            shutdown()
            return
        close = getattr(engine, 'close', None)
        if callable(close):
            logger.info('close vllm engine %r', model_id)
            close()

    def _get_loaded_engine(self, model_id: str) -> VllmEngineContextManager:
        with self._loaded_lock:
            ctx_mgr = self._loaded_models[model_id]
        ctx_mgr._rwlock.pre_read = True
        return ctx_mgr

    def get(self, model_id: str) -> VllmEngineContextManager:
        r"""Get a vLLM engine context for a model id."""
        with self._rwlock.read():
            try:
                return self._get_loaded_engine(model_id)
            except KeyError:
                pass

        with self._rwlock.write():
            try:
                return self._get_loaded_engine(model_id)
            except KeyError:
                pass

            with self._loaded_lock:
                evicted = self._loaded_models.mayevict()
            if evicted is not None:
                old_model_id, old_ctx = evicted
                with old_ctx._rwlock.write():
                    self._close_engine(old_model_id, old_ctx.engine)

            logger.info('load vllm engine %r', model_id)
            new_ctx = VllmEngineContextManager(self._engine_factory(model_id))
            with self._loaded_lock:
                self._loaded_models[model_id] = new_ctx
            return new_ctx
