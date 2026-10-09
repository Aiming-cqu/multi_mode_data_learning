#!/usr/bin/env -S pixi run -e vllm -- test -s

from __future__ import absolute_import, annotations

import abc, logging, threading, typing as tp
import torch

from ..utils.containers import CacheDict
from ..utils.rwlock import RWLock


logger: logging.Logger = logging.getLogger(name=__name__)


class ModelLike(tp.Protocol):
    r"""
    模型协议，定义支持设备迁移的模型接口。

    实现此协议的类可以将模型数据迁移到指定设备（如 CPU 或 GPU）。
    """

    def to(self, device: torch.device) -> tp.Any:
        r"""
        将模型迁移到指定设备。

        Args:
            device: 目标设备，如 torch.device("cuda") 或 torch.device("cpu")

        Returns:
            迁移后的模型实例
        """
        ...


class ModelContextManager(tp.ContextManager[ModelLike]):
    r"""
    模型上下文管理器，提供线程安全的模型访问。

    使用读写锁保护模型，允许多个读取者并发访问模型，
    同时确保模型在卸载时的独占访问。

    Args:
        model: 被管理的模型实例
        device: 模型所在设备

    Attributes:
        model (ModelLike): 被管理的模型实例
    """

    def __init__(self, model: ModelLike, *, device: torch.device):
        self.model: ModelLike = model
        self.device: torch.device = device
        self._rwlock = RWLock(pre_read=True)

    def __enter__(self) -> ModelLike:
        r"""
        进入上下文，获取读取锁。

        Returns:
            模型实例
        """
        self._rwlock.acquire_read()
        # self.stream = torch.cuda.Stream(device=self.device)
        # self.stream_ctx: torch.cuda.StreamContext = torch.cuda.stream(self.stream)
        # self.stream_ctx.__enter__()
        return self.model

    def __exit__(self, exc_type, exc_val, exc_tb):
        r"""
        退出上下文，释放读取锁。

        Args:
            exc_type: 异常类型（如果有）
            exc_val: 异常值（如果有）
            exc_tb: 异常回溯（如果有）
        """
        # self.stream_ctx.__exit__(exc_type, exc_val, exc_tb)
        # self.stream.synchronize()
        self._rwlock.release_read()


class ModelLoaderBase(abc.ABC):
    r"""
    模型加载器基类，支持模型在多 GPU 和 RAM 之间的动态加载/卸载。

    使用 LRU 缓存策略管理内存中的模型，当 GPU 内存不足时自动卸载
    最少使用的模型到 CPU 内存，需要时再从 CPU 加载回 GPU。
    采用"最少模型优先"策略在多 GPU 间分配负载。

    Args:
        gpus: GPU 设备索引列表，默认 None 表示自动检测所有可用 CUDA 设备；
              若无可用 CUDA 则回退到 CPU
        max_onloading_models: 每个 GPU 中最大同时加载的模型数量，默认 6
        max_offloading_models: CPU 内存中最大缓存的模型数量（跨所有 GPU 共享），默认 9
    """

    def __init__(
        self,
        *,
        devices: tp.Optional[tp.Sequence[tp.Union[torch.device, str]]] = None,
        max_onloading_models: int = 6,
        max_offloading_models: int = 9,
    ):
        if devices is None: devices = [f'cuda:{i}' for i in range(torch.cuda.device_count())]  # fmt: skip
        devices = [torch.device(d) for d in devices]

        # model_id → device mapping for fast lookup
        self._devices_by_model = dict[str, torch.device]()
        # Per-device set of loaded model IDs (for load-count and device lookup)
        self._model_sets_by_device: dict[torch.device, set[str]] = {d: set() for d in devices}

        self._max_per_device: int = max_onloading_models
        # Global LRU tracker for all GPU-loaded models (ordered oldest→newest)
        self._onloading_models = CacheDict[str, ModelContextManager](
            max_size=(max_onloading_models * len(self._model_sets_by_device))
        )
        self._offloading_models = CacheDict[str, ModelLike](max_size=max_offloading_models)

        self._rwlock: RWLock = RWLock()
        self._onloading_lock = threading.Lock()

    def __repr__(self) -> str:
        r"""
        返回对象的字符串表示。

        Returns:
            包含类名、设备列表和缓存配置的字符串
        """
        return (
            f'<{self.__class__.__name__}'
            f' devices={list(self._model_sets_by_device)!r}'
            f' max_onloading_models={self._max_per_device!r}'
            f' max_offloading_models={self._offloading_models.max_size!r}'
            '>'
        )

    @abc.abstractmethod
    def load_model(self, model_id: str, *, device: torch.device) -> ModelLike:
        r"""
        从存储加载模型到指定设备。

        Args:
            model_id: 模型标识符
            device: 目标设备

        Returns:
            加载的模型实例
        """
        ...

    def get(self, model_id: str) -> ModelContextManager:
        r"""
        获取模型上下文管理器。

        如果模型已在某个 GPU 中，直接返回；如果在 CPU 缓存中，加载到最优 GPU；
        如果都不在，从存储加载到最优 GPU。
        最优 GPU 使用"最少模型优先"策略选择，必要时根据全局 LRU 策略卸载其他模型。

        Args:
            model_id: 模型标识符

        Returns:
            模型上下文管理器，用于 with 语句安全访问模型
        """
        # Fast path: model is already on a GPU
        with self._rwlock.read():
            try: return self._get_onloading_model(model_id)  # fmt: skip
            except (KeyError,): pass  # fmt: skip

        model: ModelLike
        device: torch.device
        with self._rwlock.write():
            try: return self._get_onloading_model(model_id)  # fmt: skip
            except (KeyError,): pass  # fmt: skip

            with self._onloading_lock:
                offload: tp.Optional[tuple[str, ModelContextManager]] = (
                    self._onloading_models.mayevict()
                )
            if offload:
                model_id_, ctx_mgr = offload
                device = self._devices_by_model.pop(model_id_)
                self._model_sets_by_device[device].discard(model_id_)
                self._offloading_models.mayevict()
                logger.info('offload model %r from %r', model_id_, device)
                with ctx_mgr._rwlock.write():
                    ctx_mgr.model.to(torch.device("cpu"))
                self._offloading_models[model_id_] = ctx_mgr.model
            else:
                device = min(
                    self._model_sets_by_device,
                    key=(lambda d: len(self._model_sets_by_device[d])),
                )

            if model_id in self._offloading_models:
                # Onload from CPU cache
                model = self._offloading_models.pop(model_id)
                logger.info('onload model %r to %r', model_id, device)
                model.to(device)
            else:
                # Load from scratch
                logger.info('load model %r to %r', model_id, device)
                model = self.load_model(model_id, device=device)

            self._devices_by_model[model_id] = device
            self._model_sets_by_device[device].add(model_id)
            ret = ModelContextManager(model, device=device)
            with self._onloading_lock:
                self._onloading_models[model_id] = ret
            return ret

    def _get_onloading_model(self, model_id: str) -> ModelContextManager:
        logger.debug('try get onloading model %r', model_id)
        with self._onloading_lock:
            ret = self._onloading_models[model_id]  # updates LRU order
        ret._rwlock.pre_read = True
        return ret


def test_model_loader():
    r"""
    模型加载器的基础功能测试。

    验证模型加载、卸载、缓存策略和 LRU 淘汰机制。

    Parameters:
        -
    """
    try:
        import os, random
        import tqdm

        from transformers import AutoModel
        from typing_extensions import override

        class AutoModelLoader(ModelLoaderBase):
            @override
            def load_model(self, model_id, device):
                model = AutoModel.from_pretrained(model_id)
                model.eval()
                model.to(device)
                return model

        models_dir = f'{os.environ["MODELSCOPE_CACHE"]}/models'
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

        max_offloading_models = len(model_ids) - 1
        max_onloading_models = (max_offloading_models - 1) // torch.cuda.device_count()
        loader = AutoModelLoader(
            max_onloading_models=max_onloading_models,
            max_offloading_models=max_offloading_models,
        )

        for _ in tqdm.trange(100):
            model_path = f'{models_dir}/{random.choice(model_ids)}'
            with loader.get(model_path) as model:
                assert model_path in loader._onloading_models, loader._onloading_models
                assert len(loader._onloading_models) <= loader._onloading_models.max_size
                assert len(loader._offloading_models) <= loader._offloading_models.max_size
    finally:
        if __name__ == '__main__': globals().update(locals())  # fmt: skip


def test_model_loader_concurrent():
    r"""
    模型加载器的并发访问测试。

    验证多线程环境下模型加载器的线程安全性，
    包括并发获取模型、读写锁的正确性。
    同时验证多设备场景下每设备容量限制和全局 LRU 卸载策略。

    Parameters:
        -
    """
    import threading, time, random

    class MockModel:
        def __init__(self, model_id):
            self.model_id = model_id
            self.device = torch.device("cpu")

        def to(self, device):
            self.device = device

    class MockModelLoader(ModelLoaderBase):
        def load_model(self, model_id, device):
            time.sleep(0.01)  # 模拟加载延迟
            model = MockModel(model_id)
            model.to(device)
            return model

    loader = MockModelLoader(max_onloading_models=2, max_offloading_models=3)
    model_ids = [f'Model-{i}' for i in range(10)]
    errors = []
    lock = threading.Lock()

    def worker(worker_id):
        try:
            for _ in range(20):
                model_id = random.choice(model_ids)
                logger.info('request %r', model_id)
                with loader.get(model_id) as model:
                    model = tp.cast(MockModel, model)
                    assert model.model_id == model_id, f"Worker-{worker_id}: model mismatch"
                    assert model.device in loader._model_sets_by_device, (
                        f"Worker-{worker_id}: device mismatch"
                    )
                    time.sleep(random.uniform(0.001, 0.01))
                    assert len(loader._onloading_models) <= loader._onloading_models.max_size
                    assert len(loader._offloading_models) <= loader._offloading_models.max_size
        except (Exception,) as e:
            logger.exception('')
            with lock: errors.append(f"Worker-{worker_id}: {e}")  # fmt: skip

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads: t.start()  # fmt: skip
    for t in threads: t.join()  # fmt: skip

    assert not errors, errors


if __name__ == '__main__':
    from conflog import configure_logging, configure_auto_tracing

    configure_logging(env="test")
    configure_auto_tracing(env="test")

    test_model_loader()
    test_model_loader_concurrent()
