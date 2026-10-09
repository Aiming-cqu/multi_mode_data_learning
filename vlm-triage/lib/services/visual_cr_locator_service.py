#!/usr/bin/env -S pixi run -- test -s

r"""
Visual CR Locator Service — 视觉拐点定位核心服务。

通过分析仿真动画视频帧的视觉差异，定位自动驾驶回放任务中导致行为变化的关键 CR。

数据流水线
----------
::

    get_tasks                 # 1. 从 CR Locator 平台拉取任务和 CR 列表
    → cluster_event_windows   # 2. 根据 DPE 事件时间戳聚类采样窗口
    → get_sample_images       # 3. FFmpeg 裁剪动画帧 → 本地图片
    → upload_images_to_s3     # 4. put 上传图片到 S3 并签名 URL
    → compute_visual_metrics  # 5. 计算 embedding / CV 相似度指标
    → get_result              # 6. 投票定位拐点 + 生成 Excel 报告

存储策略
--------
- **图片**: 从 CACHE_DIR 上传到 S3 (``put_and_sign``)，返回签名 URL。
- **Excel**: 写入 DATA_DIR (S3 挂载盘)，直接 ``sign`` 获得 URL，并上传到 Cooper。
- **临时文件**: FFmpeg 输出到 CACHE_DIR，``CRProcessTask.close()`` 时清理。

主要类
------
- `LocatorTask`: 单次定位任务的完整生命周期管理。
- `CRProcessTask`: 单个 CR 对应的图片采样子任务。
- `LocatorService`: 对外服务入口，提供 ``locate`` 和 ``get_annotation_info`` 两个异步接口。
"""

from __future__ import absolute_import, annotations

import asyncio, dataclasses as dc, io, logging, os, shutil, typing as tp
import httpx
import logfire
import numpy as nt
import pandas as pf

from async_lru import alru_cache
from functools import cached_property
from pathlib import Path
from tenacity import retry, stop_after_attempt
from tqdm.asyncio import tqdm_asyncio

from ..algorithms.cr_locate import (
    CRLocateResult,
    get_fob_and_outliers,
    locate_cr_by_variance_minimization,
    locate_cr_by_voting,
)
from ..algorithms.max_coverage import max_coverage
from ..platforms.ep.cooper import CooperClient
from ..platforms.ep.cooper_types import FileInfo
from ..platforms.tetools.cr_locator import get_cr_locator_data
from ..platforms.tetools.cr_locator_types import (
    CRInfo,
    CRLocatorIdType,
    CRLocatorData,
    CommitInfo,
)
from ..platforms.voyager_proxy import (
    TaskIdType,
    TaskData,
    get_orion_task_data,
    get_dpe_METRIC_EVENT_MAPPING,
)
from ..tools.resources import (
    Resource,
    HTTPStorage,
    FileStorage,
    hash_func,
)
from ..tools.session import Session, SessionContextManager, SessionIdType
from ..utils.arrow_utils import load as arrow_load
from ..utils.dpe_helper import normalize_dpe_output
from ..utils.excel_utils import (
    CONDITION_NUMERIC_GRADIENT,
    apply_conditional_format,
    apply_data_validation,
    embed_images,
    write_df,
)
from ..utils.s3_utils import (
    DEFAULT_DATA_PREFIX,
    prepend_object_partition,
    fput_and_sign,
    sign,
)
from .visual_cr_locator_types import (
    ScenarioIdType,
    SampleImageInfo,
    AnnotationInfo,
    LocatorConfig,
    LocatorScenarioResult,
    LocatorResult,
)

if tp.TYPE_CHECKING:
    from tenacity.stop import StopBaseT


_TD = tp.TypeVar('_TD', pf.DataFrame, pf.Series)

PathLikeStr = tp.Union[os.PathLike[str], str]

CACHE_DIR: Path = Path(os.environ['TRIAGE_CACHE_DIR'])
DATA_DIR: Path = Path(os.environ['TRIAGE_DATA_DIR'])

# Cooper 标注目录：https://cooper.didichuxing.com/team-file/2199094698523/2207445719119
COOPER_GROUP_ID: int = 2199094698523
COOPER_PARENT_ID: int = 2207445719119

CONCURRENCY = int(os.getenv('TRIAGE_LOCATOR_API_CONCURRENCY', 4))
STOP_POLICY: 'StopBaseT' = stop_after_attempt(3)

VL_MODEL_IDS: list[str] = [
    'Qwen/Qwen3-VL-Embedding-8B',
]


logger: logging.Logger = logging.getLogger(__name__)


get_cr_locator_data = alru_cache(ttl=300)(get_cr_locator_data)  # type: ignore
sign = retry(stop=STOP_POLICY)(sign)


@dc.dataclass
class LocatorFail(Exception):
    r"""定位流程产出了结果但存在告警（如歧义投票、支持度不足）。

    与普通异常不同，``result`` 仍然包含可用的定位结果，调用方可选择降级使用。
    """

    locator_id: CRLocatorIdType
    message: str
    result: LocatorResult


class LocatorTask(tp.ContextManager):
    r"""单次视觉拐点定位任务。

    管理从数据获取到结果输出的完整生命周期，是服务的核心工作单元。
    使用上下文管理器 (``with LocatorTask(...) as task:``) 保证资源清理。

    Class-level 资源:
        - ``embedding_client`` / ``cv_client``: 复用的 httpx 异步客户端。
        - ``cooper_client``: Cooper 文件上传客户端。
        - ``*_semaphore``: 并发控制信号量，避免过载下游服务。

    Instance 属性 (按流水线阶段产生):
        - ``locator_data``: CR Locator 平台返回的原始数据 (``get_tasks``)。
        - ``cr_tasks``: 展开后的 ``CRProcessTask`` 列表 (``get_tasks``)。
        - ``end_times_by_scenario``: 每个场景的采样窗口结束时间 (``cluster_event_windows``)。
        - ``image_info_f``: 图片元信息 DataFrame (``get_sample_images``)。
        - ``cr_metric_sc_f``: 视觉指标透视表 (``compute_visual_metrics``)。
    """

    base_task_index: tp.ClassVar[CRLocatorIdType] = -1
    feat_task_index: tp.ClassVar[CRLocatorIdType] = -2
    embedding_client: tp.ClassVar = httpx.AsyncClient(
        base_url=os.environ['TRIAGE_EMBEDDING_API_URL'],
        timeout=float(os.getenv('TRIAGE_EMBEDDING_API_TIMEOUT', 90.0)),
    )
    cv_client: tp.ClassVar = httpx.AsyncClient(
        base_url=os.environ['TRIAGE_CV_API_URL'],
        timeout=float(os.getenv('TRIAGE_CV_API_TIMEOUT', 90.0)),
    )
    cooper_client: tp.ClassVar = CooperClient()
    task_semaphore: tp.ClassVar = asyncio.Semaphore(value=(CONCURRENCY * 1))
    embedding_semaphore: tp.ClassVar = asyncio.Semaphore(value=6)
    cv_semaphore: tp.ClassVar = asyncio.Semaphore(value=16)
    cooper_semaphore: tp.ClassVar = asyncio.Semaphore(value=min(4, CONCURRENCY * 1))
    s3_semaphore: tp.ClassVar = asyncio.Semaphore(value=min(16, CONCURRENCY * 4))

    @classmethod
    def reorder_end_cr(cls, obj: _TD) -> _TD:
        r"""将 base 和 feature 两行分别移至首尾，中间保留 CR 原序。"""
        end_index: list[int] = [cls.base_task_index, cls.feat_task_index]
        index = [
            cls.base_task_index,
            *obj.index.difference(end_index, sort=False),  # NOTE: any is ok
            cls.feat_task_index,
        ]
        return obj.loc[index]

    def __init__(
        self,
        locator_id: CRLocatorIdType,
        *,
        config: LocatorConfig = LocatorConfig(),
    ):
        self.locator_id: CRLocatorIdType = locator_id
        self.config: LocatorConfig = config
        self.cr_tasks = list[CRProcessTask]()

    def __repr__(self) -> str:
        return (
            f'{self.__class__.__name__}(locator_id={self.locator_id!r}'
            f', ncrs={len(self.cr_tasks)}'
            ')'
        )

    def __enter__(self) -> tp.Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @cached_property
    def locator_url(self) -> str:
        r"""CR Locator 平台页面链接。"""
        return f'http://10.190.55.60:8000/pages/crlocator.html?id={self.locator_id}'

    @cached_property
    def diff_url(self) -> str:
        r"""Voyager 平台 task diff 对比页面链接。"""
        return (
            'https://voyager.intra.xiaojukeji.com/static/management/'
            '#/simulation/review?reviewType=taskDiff'
            f'&taskIds={self.base_task_id},{self.feat_task_id}'
            f'&selectedMetrics={",".join(self.locator_data.metrics)}'
        )

    @cached_property
    def data_prefix(self) -> str:
        r"""基于 session ID 的分区路径前缀 (不含 S3 bucket 前缀)。"""
        session_id: SessionIdType = Session.current().id
        return prepend_object_partition(hash_func(f'{session_id}'.encode()), prefix='')

    @cached_property
    def s3_prefix(self) -> str:
        r"""完整 S3 对象名前缀 (含 DEFAULT_DATA_PREFIX)。"""
        return f'{DEFAULT_DATA_PREFIX}/{self.data_prefix}'

    @cached_property
    def data_dir(self) -> Path:
        r"""DATA_DIR 下按 session 分区的数据目录 (S3 挂载盘)，自动创建。"""
        ret = DATA_DIR / self.data_prefix
        ret.mkdir(parents=True, exist_ok=True)
        return ret

    @logfire.instrument
    def close(self):
        for task in self.cr_tasks:
            task.close()
        self.cr_tasks.clear()

    @retry(stop=STOP_POLICY, reraise=True)
    @logfire.instrument
    async def upload_to_s3(self, file_path: PathLikeStr, object_name: str, **kwds) -> str:
        r"""put 上传文件到 S3 并签名获得 URL (用于 cache 目录中的图片等非挂载盘文件)。"""
        async with self.s3_semaphore:
            return await fput_and_sign(file_path, f'{self.s3_prefix}/{object_name}', **kwds)

    @logfire.instrument(extract_args=False)
    async def upload_images_to_s3(self, image_info_f: pf.DataFrame) -> pf.DataFrame:
        r"""批量 put 上传图片到 S3。

        为 DataFrame 中每行构造语义化文件名，并发上传到 S3 并签名。
        返回新增 ``file_name`` 和 ``file_url`` 列的 DataFrame 副本。
        """
        df = image_info_f.copy()
        df['file_name'] = (
            f'locator_id={self.locator_id:d}'
            + df.scenario_id.map(lambda s: f'-scenario_id={s:s}')
            + df.cr_index.map(lambda i: f'-cr_index={i:02d}')
            + df.task_id.map(lambda i: f'-task_id={i:d}')
            + df.commit.fillna(value='').map(lambda s: f'-commit={s:s}' if s else '')
            + df.window_index.map(lambda s: f'-window_index={s:s}')
            + df.end_time.map(lambda i: f'-window_time={i:05d}')
            + df.sample_index.map(lambda s: f'-sample_index={s:s}')
            + df.sample_abs_time.map(lambda i: f'-sample_time={i:05d}')
            + '.jpg'
        )
        df['file_url'] = await tqdm_asyncio.gather(
            *(
                self.upload_to_s3(
                    r.image_path,
                    r.file_name,
                    content_type='image/jpeg',
                    response_headers={'response-content-disposition': 'inline'},
                )
                for r in df.itertuples(index=False)
            ),
            desc=f'[{self.locator_id}] upload_sample_images',
        )
        return df

    @retry(stop=STOP_POLICY, reraise=True)
    @logfire.instrument(record_return=True)
    async def upload_to_cooper(self, file_path: PathLikeStr) -> FileInfo:
        r"""上传文件到 Cooper 测试用的目录。"""
        async with self.cooper_semaphore:
            with Path(file_path).open('rb') as f:
                return await self.cooper_client.upload_file(
                    COOPER_GROUP_ID, COOPER_PARENT_ID, f
                )

    @logfire.instrument
    async def get_tasks(self) -> tp.Self:
        r"""流水线第 1 步：从 CR Locator 平台拉取数据并展开 CR 任务列表。

        产生的属性:
            - ``locator_data``: 平台原始数据。
            - ``cr_tasks``: base + N×CR + feature 的任务列表 (每场景)。
            - ``cr_f``: CR task_id/commit 汇总 DataFrame。
            - ``base_task_id`` / ``feat_task_id``: 基线/特征任务 ID。
        """
        async with self.task_semaphore:
            self.locator_data: CRLocatorData = await get_cr_locator_data(self.locator_id)
            if (type_ := self.locator_data.type) in (9,):
                raise NotImplementedError(
                    f'Unsupported locator type on {self.locator_id=}: {type_!r}',
                )

            METRIC_EVENT_MAPPING: tp.Mapping[str, str] = await get_dpe_METRIC_EVENT_MAPPING()

        self.event_names: list[str] = [
            METRIC_EVENT_MAPPING.get(s, s[4:] if s.startswith('dpe_') else '')
            for s in self.locator_data.metrics
        ]
        self.event_names = list(filter(None, self.event_names))

        self.base_task_id: TaskIdType = self.locator_data.diff_data.base_task
        self.feat_task_id: TaskIdType = self.locator_data.diff_data.feature_task
        self.cr_tasks.clear()
        dfs = []

        for scenario_id, scenario_crs_info in self.locator_data.result.items():
            task_id: TaskIdType = self.base_task_id
            task = CRProcessTask(task_id, self.base_task_index, scenario_id, self)
            if self.config.use_vlm_animation:
                task.override_animation_url(self.locator_data.diff_data.base_vlm_animation)
            else:
                task.override_sample_xy(self.config.sample_xy_e2e)
            self.cr_tasks.append(task)

            records = []
            for cr_index, cr_info in enumerate(scenario_crs_info, start=1):
                task_id = cr_info.task_id.id
                task = CRProcessTask(task_id, cr_index, scenario_id, self)
                if self.config.use_vlm_animation:
                    task.override_animation_url(cr_info.task_id.vlm_animation)
                self.cr_tasks.append(task)
                records.append((cr_info.task_id.id, cr_info.commit.commit))
            df = pf.DataFrame.from_records(records, columns=['task_id', 'commit'])
            df['scenario_id'] = scenario_id
            dfs.append(df)

            task_id = self.feat_task_id
            task = CRProcessTask(task_id, self.feat_task_index, scenario_id, self)
            if self.config.use_vlm_animation:
                task.override_animation_url(self.locator_data.diff_data.feature_vlm_animation)
            else:
                task.override_sample_xy(self.config.sample_xy_e2e)
            self.cr_tasks.append(task)

        self.cr_f = pf.concat(dfs, sort=False)  # type: pf.DataFrame
        logger.debug(
            'locator_id=%r cr_f=\n%s',
            self.locator_id,
            self.cr_f.to_csv(sep='\t'),
        )
        logger.info(
            'locator_id=%r event_names=%r base_task_id=%r feat_task_id=%r ncrs=%d',
            self.locator_id,
            self.event_names,
            self.base_task_id,
            self.feat_task_id,
            len(self.cr_tasks),
        )
        return self

    @logfire.instrument
    async def cluster_event_windows(self) -> tp.Self:
        r"""流水线第 2 步：获取 DPE 事件并用最大覆盖算法聚类采样窗口。

        对每个场景的事件时间戳运行 ``max_coverage``，选出最有代表性的窗口。

        产生的属性:
            - ``end_times_by_scenario``: ``{scenario_id: [end_time_ms, ...]}``。
            - ``end_time_f``: 窗口信息 DataFrame (含 ``window_index``)。
        """
        await tqdm_asyncio.gather(
            *(t.get_dpe_events() for t in self.cr_tasks),
            desc=f'[{self.locator_id}] cluster_event_windows',
        )

        dfs = [
            t.event_f.assign(
                task_id=t.task_id,
                cr_index=t.cr_index,
                scenario_id=t.scenario_id,
            )
            for t in self.cr_tasks
        ]
        self.event_f = df = pf.concat(dfs, sort=False)  # type: pf.DataFrame
        logger.debug(
            'locator_id=%r event_f=\n%s',
            self.locator_id,
            self.event_f.to_csv(sep='\t'),
        )

        self.end_times_by_scenario = dict[ScenarioIdType, list[int]]()

        for scenario_id in self.locator_data.result:
            t_a = nt.sort(df.loc[df.scenario_id.eq(scenario_id)].timestamp)
            if len(t_a) == 0:
                raise ValueError(
                    f'No events can be sampled in {self.locator_id=} {scenario_id=}'
                )

            w_a = max_coverage(
                t_a,
                self.config.max_windows,
                self.config.window_duration - self.config.window_offset,
            )
            self.end_times_by_scenario[scenario_id] = t_a[[e for s, e in w_a]].tolist()

        series = pf.Series(data=self.end_times_by_scenario, name='end_time')
        series.index.name = 'scenario_id'
        self.end_time_f = df = series.explode().astype('Int64').reset_index()
        df['window_index'] = (df.index + 1).map(lambda i: f'{i:02d}')
        logger.debug(
            'locator_id=%r end_time_f=\n%s',
            self.locator_id,
            self.end_time_f.to_csv(sep='\t'),
        )
        logger.info(
            'locator_id=%r nevents=%d end_times_by_scenario=%r',
            self.locator_id,
            len(df),
            self.end_times_by_scenario,
        )
        return self

    @logfire.instrument
    async def get_sample_images(self) -> tp.Self:
        r"""流水线第 3 步：FFmpeg 裁剪动画帧为采样图片。

        并发驱动所有 ``CRProcessTask.get_sample_images``，然后合并结果
        并补充描述字段 (cr_desc, window_desc, sample_desc 等)。

        产生的属性:
            - ``image_sample_f``: 原始图片路径 DataFrame。
            - ``image_info_f``: 合并元信息后的完整图片 DataFrame。
        """
        await tqdm_asyncio.gather(
            *(
                t.get_sample_images(self.end_times_by_scenario[t.scenario_id])
                for t in self.cr_tasks
            ),
            desc=f'[{self.locator_id}] get_sample_images',
        )

        dfs = [
            t.image_sample_f.assign(
                task_id=t.task_id,
                cr_index=t.cr_index,
                scenario_id=t.scenario_id,
            )
            for t in self.cr_tasks
        ]
        self.image_sample_f = df = pf.concat(dfs, sort=False)  # type: pf.DataFrame
        logger.debug(
            'locator_id=%r image_sample_f=\n%s',
            self.locator_id,
            self.image_sample_f.to_csv(sep='\t'),
        )

        offset: int = self.config.window_offset - self.config.window_duration
        df = self.image_sample_f
        df = df.merge(self.cr_f, how='left')
        df['cr_desc'] = df.task_id.astype('string') + df.commit.fillna(value='').map(
            lambda s: f' / {s}' if s else '',
        )
        df = df.merge(self.end_time_f, how='left')
        df['sample_rel_time'] = (
            df.sample_index.astype(int) - 1
        ) * self.config.sample_interval + offset
        df['sample_abs_time'] = df.end_time + df.sample_rel_time
        df['window_desc'] = 'W' + df.window_index + df.end_time.map(lambda t: f' @ {t:d}ms')
        df['sample_desc'] = (
            'S' + df.sample_index + df.sample_rel_time.map(lambda t: f' @ {t:+d}ms')
        )
        self.image_info_f = df  # type: pf.DataFrame
        logger.debug(
            'locator_id=%r image_info_f=\n%s',
            self.locator_id,
            self.image_info_f.to_csv(sep='\t'),
        )
        logger.info('locator_id=%r nsamples=%d', self.locator_id, len(df))
        return self

    @logfire.instrument(extract_args=['scenario_id'], record_return=True)
    def dump_to_excel(self, scenario_id: ScenarioIdType, **dfs: pf.DataFrame) -> str:
        r"""创建 Excel 到 data 目录 (S3 挂载盘)。

        Excel 包含以下 sheet:
            - ``meta``: locator/diff/task 元信息。
            - ``image_samples``: 透视图片网格 + 嵌入缩略图 + 数据验证。
            - ``**dfs``: 额外传入的 DataFrame (如 FoB/outlier 矩阵)，
              自动添加 bool 条件格式和数值渐变色。

        Returns:
            写入的文件名 (不含目录路径)。
        """
        df_name: str = ''.join('-' + k for k in dfs) if dfs else ''
        file_name: str = f'locator_id={self.locator_id}-{scenario_id=!s}{df_name}.xlsx'

        meta: dict[str, tp.Any] = {
            'locator_id': self.locator_id,
            'locator_url': self.locator_url,
            'metrics': ','.join(self.locator_data.metrics),
            'events': ','.join(self.event_names),
            'diff_type': self.locator_data.diff_data.diff_type,
            'diff_url': self.diff_url,
            'base_task_id': self.base_task_id,
            'feat_task_id': self.feat_task_id,
            'scenario_id': scenario_id,
        }
        series = pf.Series(data=meta, name='value')
        series.index.name = 'key'
        series = series.astype('string')

        df = self.image_info_f
        df = df.loc[df.scenario_id.eq(scenario_id)].copy()
        df['task_id'] = df.task_id.astype('string')
        df = df.pivot(
            columns=['window_index', 'end_time', 'sample_index', 'sample_rel_time'],
            index=['cr_index', 'task_id', 'commit'],
            values='image_path',
        )
        df = df.loc[self.reorder_end_cr(df.index.get_level_values('cr_index').to_series())]

        with pf.ExcelWriter(self.data_dir / file_name, engine='xlsxwriter') as writer:
            sheet_name: str = 'meta'
            write_df(
                writer,
                sheet_name,
                series.to_frame(name=sheet_name),
            )

            sheet_name = 'image_samples'
            write_df(
                writer,
                sheet_name,
                pf.DataFrame(data='', index=df.index, columns=df.columns),
            )
            embed_images(
                writer,
                sheet_name,
                df,
                self.config.sample_wh,
                padding=6,
            )
            apply_data_validation(writer, sheet_name, df)

            for name, df in dfs.items():
                write_df(writer, name, df)
                for col in df.select_dtypes(include=['bool']).columns:
                    apply_conditional_format(writer, name, df, column=col)
                for col in df.select_dtypes(include=['number']).columns:
                    apply_conditional_format(
                        writer,
                        name,
                        df,
                        condition=CONDITION_NUMERIC_GRADIENT,
                        column=col,
                    )

        return file_name

    @logfire.instrument(extract_args=['scenario_id'])
    async def dump_and_upload_excel(
        self, scenario_id: ScenarioIdType, **dfs: pf.DataFrame
    ) -> str:
        r"""创建 Excel 到 data 目录 (S3 挂载盘)，直接签名获得 URL，并上传到 Cooper。"""
        file_name: str = self.dump_to_excel(scenario_id, **dfs)
        await self.upload_to_cooper(self.data_dir / file_name)
        async with self.s3_semaphore:
            return await sign(
                f'{self.s3_prefix}/{file_name}',
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                response_headers={
                    'response-content-disposition': f'attachment; filename="{file_name}"',
                },
            )

    @logfire.instrument
    async def compute_visual_metrics(self) -> tp.Self:
        r"""流水线第 4 步：并发计算 embedding 和 CV 相似度指标。

        对每个 (scenario, window, sample) 位置，收集 base→CR→feature 图片序列，
        分别调用 embedding API 和 CV API 计算相似度矩阵。

        产生的属性:
            - ``visual_metric_i_f``: 按图片路径索引的指标 DataFrame。
            - ``cr_metric_sc_f``: 透视为 (scenario, cr_index)
              × (model, metric, end, window, sample) 的宽表。
        """
        try:
            async with asyncio.TaskGroup() as tg:
                tasks = set[asyncio.Task]()
                for sample_name, df in self.image_sample_f.set_index('cr_index').groupby(
                    by=['scenario_id', 'window_index', 'sample_index'],
                ):
                    name: tuple = (self.locator_id,) + sample_name
                    series = df.image_path
                    try:
                        series = self.reorder_end_cr(series)
                    except (KeyError,):
                        logger.warning(
                            'skip sample position %r not exist in ends:\n%s',
                            name,
                            df.to_csv(sep='\t'),
                        )
                        continue
                    tasks.add(
                        tg.create_task(
                            self.compute_sample_embedding_metrics(
                                series,
                                name=name,
                                text=self.config.text,
                            )
                        )
                    )
                    tasks.add(tg.create_task(self.compute_sample_cv_metrics(series, name=name)))
                dfs = await tqdm_asyncio.gather(
                    *tasks,
                    desc=f'[{self.locator_id}] compute_visual_metrics',
                )
        except* Exception as eg:
            for exc in eg.exceptions:
                exc.add_note(f'locator_id={self.locator_id!r} compute_visual_metrics')
            raise

        dfs_by_method = dict[str, list[pf.DataFrame]]()
        for df in dfs:
            for method, group in df.groupby(by='method'):
                dfs_by_method.setdefault(method, []).append(group.drop(columns=['method']))
        self.visual_metric_i_f = df = pf.concat(
            [pf.concat(g, axis=0, sort=False) for g in dfs_by_method.values()],
            axis=1,
            sort=False,
        )  # type: pf.DataFrame
        logger.debug(
            'locator_id=%r visual_metric_i_f=\n%s',
            self.locator_id,
            self.visual_metric_i_f.to_csv(sep='\t'),
        )

        df = self.image_sample_f.merge(df, left_on='image_path', right_index=True)
        df = df.drop(columns=['task_id', 'image_path'])
        df = df.pivot(
            index=['scenario_id', 'cr_index'],
            columns=['window_index', 'sample_index'],
        )
        df.columns = pf.MultiIndex.from_tuples(
            [tuple(c[0].split(':')) + c[1:] for c in df.columns],
            names=(['model_id', 'metric_name', 'end'] + df.columns.names[1:]),
        )
        self.cr_metric_sc_f: pf.DataFrame = df
        logger.debug(
            'locator_id=%r cr_metric_sc_f=\n%s',
            self.locator_id,
            self.cr_metric_sc_f.to_csv(sep='\t'),
        )
        return self

    @retry(stop=STOP_POLICY, reraise=True)
    @logfire.instrument
    async def compute_sample_embedding_metrics(
        self,
        image_paths: tp.Sequence[PathLikeStr],
        name: tp.Optional[tp.Any] = None,
        *,
        text: str = '',
    ) -> pf.DataFrame:
        r"""调用 embedding API 计算图片序列的相似度指标。"""

        params: dict[str, tp.Any] = {"text": text}
        if text: params["model_ids"] = VL_MODEL_IDS  # fmt: skip

        async with self.embedding_semaphore:
            files: list[tuple[str, bytes]] = [
                ('image_files', Path(p).read_bytes()) for p in image_paths
            ]
            resp = await self.embedding_client.post(
                '/compute_similarity',
                files=files,
                params=params,
            )

        df = arrow_load(io.BytesIO(resp.raise_for_status().content), 'arrow', hint='table')
        df.index = image_paths
        logger.debug('name=%r embedding_metric_f=\n%s', name, df.to_csv(sep='\t'))
        return df.assign(method='embedding')

    @retry(stop=STOP_POLICY, reraise=True)
    @logfire.instrument
    async def compute_sample_cv_metrics(
        self,
        image_paths: tp.Sequence[PathLikeStr],
        name: tp.Optional[tp.Any] = None,
    ) -> pf.DataFrame:
        r"""调用 CV API 计算图片序列的传统视觉相似度指标。"""
        async with self.cv_semaphore:
            files: list[tuple[str, bytes]] = [
                ('image_files', Path(p).read_bytes()) for p in image_paths
            ]
            resp = await self.cv_client.post('/compute_similarity', files=files)

        df = arrow_load(io.BytesIO(resp.raise_for_status().content), 'arrow', hint='table')
        df.index = image_paths
        logger.debug('name=%r cv_metric_f=\n%s', name, df.to_csv(sep='\t'))
        return df.assign(method='cv')

    @logfire.instrument(record_return=True)
    async def get_result(self) -> LocatorResult:
        r"""流水线第 5 步：基于视觉指标投票定位拐点 CR。

        对每个场景:
            1. 调用 ``locate_cr_by_voting`` 投票确定拐点 ``cr_index``。
            2. 按需生成 Excel 报告 (``dump_and_upload_excel``)。
            3. 按需上传参考图片到 S3 (``upload_images_to_s3``)。

        如果存在歧义或支持度不足，收集告警消息，最终抛出 ``LocatorFail``
        (但 ``result`` 字段仍包含可用结果)。
        """

        ret = dict[ScenarioIdType, LocatorScenarioResult]()
        messages = list[str]()

        for scenario_id, df in self.cr_metric_sc_f.groupby(level='scenario_id'):
            scenario_id = tp.cast(ScenarioIdType, scenario_id)
            cr_infos: list[CRInfo] = self.locator_data.result[scenario_id]
            cr_metric_sc_f = self.reorder_end_cr(df.droplevel('scenario_id'))
            fob_sc_f, outlier_sc_f = get_fob_and_outliers(cr_metric_sc_f)
            res_vote = locate_cr_by_voting(fob_sc_f, outlier_sc_f)
            logger.info(
                'locator_id=%r scenario_id=%r locate_cr_by_voting res=%r',
                self.locator_id,
                scenario_id,
                res_vote,
            )
            fob_sc_s = fob_sc_f.mean(axis=1)
            res_var = locate_cr_by_variance_minimization(fob_sc_s)
            logger.info(
                'locator_id=%r scenario_id=%r locate_cr_by_variance_minimization res=%r',
                self.locator_id,
                scenario_id,
                res_var,
            )

            if res_vote.crs != res_var.crs:
                logger.warning(
                    'locator_id=%r scenario_id=%r locate_cr by voting and variance res differ: %r vs %r',
                    self.locator_id,
                    scenario_id,
                    res_vote,
                    res_var,
                )

            res = res_var

            crs: list[CRInfo] = [cr_infos[i - 1] for i in res.crs]
            cr_index: int = 1
            cr: CRInfo = cr_infos[0]

            if len(res.crs) == 0:
                messages.append(f'{scenario_id} - No CR located: {res!r}')
            else:
                cr_index = res.crs[0]
                cr = crs[0]

            if 1 in res.crs:
                messages.append(f'{scenario_id} - First CR located: {res!r}')

            excels = list[str]()
            if self.config.return_excels:
                excels_ = {
                    "cr_metric_sc_f": cr_metric_sc_f,
                    "fob_sc_f": fob_sc_f,
                    "outlier_sc_f": outlier_sc_f,
                }
                series = pf.Series(
                    data={
                        'cr_indices': ','.join(map(str, res.crs)),
                        'commits': ','.join(c.commit.commit for c in crs),
                        'cr_index': cr_index,
                        'commit': cr.commit.commit,
                    }
                )
                excels_["result_f"] = series.to_frame()
                excels = [await self.dump_and_upload_excel(scenario_id, **excels_)]

            images = list[SampleImageInfo]()
            if self.config.return_images:
                indices = [self.base_task_index, self.feat_task_index, cr_index, cr_index - 1]
                df = self.image_info_f
                df = df.loc[df.scenario_id.eq(scenario_id)]
                df = df.loc[df.cr_index.isin(indices)]
                df = await self.upload_images_to_s3(df)
                images = [
                    SampleImageInfo(
                        cr_index=r.cr_index,
                        cr_desc=r.cr_desc,
                        window_index=r.window_index,
                        window_desc=r.window_desc,
                        sample_index=r.sample_index,
                        sample_desc=r.sample_desc,
                        image_url=r.file_url,
                    )
                    for r in df.itertuples(index=False)
                ]

            ret[scenario_id] = LocatorScenarioResult(
                cr_indices=res.crs,
                commits=crs,
                cr_index=cr_index,
                commit=cr,
                images=images,
                excels=excels,
            )

        if len(messages) > 0:
            raise LocatorFail(
                locator_id=self.locator_id,
                message='\n'.join(messages),
                result=ret,
            )

        logger.debug('ret=%r', ret)
        return ret


class CRProcessTask:
    r"""单个 CR 对应的图片采样子任务。

    负责:
        1. 从 Orion 拉取 DPE 事件数据 → ``event_f``。
        2. 通过 FFmpeg 从动画视频中裁剪采样帧 → ``image_sample_f``。

    生命周期: 由 ``LocatorTask`` 创建和关闭；``close()`` 清理临时图片目录。
    """

    http_client: tp.ClassVar = httpx.AsyncClient()
    network_semaphore: tp.ClassVar = asyncio.Semaphore(value=min(16, CONCURRENCY * 4))
    process_semaphore: tp.ClassVar = asyncio.Semaphore(
        value=min(64, CONCURRENCY * 4, os.cpu_count() or 16),
    )

    @classmethod
    @alru_cache(ttl=300)
    @retry(stop=STOP_POLICY, reraise=True)
    @logfire.instrument
    async def get_dpe_events_data(cls, task_id: TaskIdType) -> tuple[TaskData, tp.Any]:
        r"""获取指定任务的 DPE 输出数据 (带 TTL 缓存)。"""
        task_data: TaskData = await get_orion_task_data(task_id)
        url = task_data.dpe_output_url
        if url is None: raise ValueError(f'Missing DPE output on {task_id=}')  # fmt: skip
        res = (await cls.http_client.get(url)).raise_for_status().json()
        return (task_data, res)

    def __init__(
        self,
        task_id: TaskIdType,
        cr_index: int,
        scenario_id: ScenarioIdType,
        locator_task: LocatorTask,
    ):
        self.task_id: TaskIdType = task_id
        self.cr_index: int = cr_index
        self.scenario_id: ScenarioIdType = scenario_id
        self.locator_task: LocatorTask = locator_task
        self.sample_xy: tuple[int, int] = self.locator_task.config.sample_xy
        self.animation_url_override: tp.Optional[str] = None
        session_id: SessionIdType = Session.current().id
        self.image_dir: Path = CACHE_DIR / hash_func(f'{session_id}/{self.task_id}'.encode())
        logger.debug('self=%r', self)
        self.image_dir.mkdir(parents=True)

    def __del__(self):
        try: self.close()  # fmt: skip
        except: pass  # noqa # fmt: skip

    def __repr__(self) -> str:
        return (
            f'{self.__class__.__name__}(task_id={self.task_id!r}'
            f', cr_index={self.cr_index!r}'
            f', scenario_id={self.scenario_id!r}'
            f', image_dir={self.image_dir!r}'
            ')'
        )

    @logfire.instrument
    def close(self):
        shutil.rmtree(self.image_dir)

    def override_sample_xy(self, value: tuple[int, int]) -> tp.Self:
        self.sample_xy = value
        return self

    def override_animation_url(self, value: tp.Optional[str]) -> tp.Self:
        if value is None:
            raise ValueError(
                f'No VLM animation for {self.locator_task.locator_id=} {self.task_id=}',
            )
        self.animation_url_override = value
        return self

    @logfire.instrument
    async def get_dpe_events(self) -> tp.Self:
        r"""拉取并解析 DPE 事件时间序列，产生 ``event_f`` DataFrame。"""
        async with self.network_semaphore:
            self.task_data, res = await self.get_dpe_events_data(self.task_id)
        _, self.event_f = normalize_dpe_output(
            res,
            metric_names=self.locator_task.event_names,
            start_time_ms=self.task_data.result.animation_time_range_ms[0],
        )  # type: Series, DataFrame
        return self

    @retry(stop=STOP_POLICY, reraise=True)
    @logfire.instrument
    async def get_sample_images(self, end_times: tp.Sequence[int]) -> tp.Self:
        r"""通过 FFmpeg 从动画视频中裁剪指定窗口的采样帧。

        对每个窗口时间段调用 FFmpeg 裁剪指定区域的帧序列，输出到临时目录。
        产生 ``image_sample_f`` DataFrame，包含 image_path / window_index / sample_index。
        """
        animation_url: str
        if self.animation_url_override is not None:
            animation_url = self.animation_url_override
        elif self.task_data.animation_url is not None:
            animation_url = self.task_data.animation_url
        else:
            raise ValueError(f'Missing animation on {self.task_id=}')

        config: LocatorConfig = self.locator_task.config
        x, y = self.sample_xy
        w, h = config.sample_wh
        l, t = x - w // 2, y - h // 2

        async with self.network_semaphore:
            resource: Resource = await HTTPStorage(url=animation_url).to_resource(
                f'{self.task_id}/animation',
                mime_type='video/mp4',
            )
            storage: FileStorage = await resource.get(FileStorage)

        async with self.process_semaphore:
            for window_index, end_time in enumerate(end_times, start=1):
                out_file: Path = self.image_dir / f'{window_index:02d}-%02d.jpg'
                args = [
                    'ffmpeg',
                    '-hide_banner',
                    '-threads',
                    '1',
                    '-loglevel',
                    'error',
                    '-i',
                    storage.path.as_posix(),
                    '-ss',
                    f'{(end_time + config.window_offset - config.window_duration) * 1e-3}',
                    '-to',
                    f'{(end_time + config.window_offset) * 1e-3}',
                    '-r',
                    f'{1e3 / config.sample_interval}',
                    '-vf',
                    f'crop={w}:{h}:{l}:{t}',
                    out_file.as_posix(),
                ]
                with logfire.span(
                    f'Run FFMPEG: {args=}',
                    window_index=window_index,
                    end_time=end_time,
                ):
                    proc: asyncio.subprocess.Process = (
                        await asyncio.subprocess.create_subprocess_exec(*args)
                    )
                    try:
                        await proc.communicate()
                    finally:
                        if proc.returncode is None:
                            proc.kill()
                            await proc.wait()
                    if proc.returncode != 0:
                        raise RuntimeError(
                            f'During processing animation of {self.task_id=}, '
                            f'ffmpeg returned non-zero exit status {proc.returncode}',
                        )

        self.image_sample_f = df = pf.DataFrame(
            data=sorted(f.as_posix() for f in self.image_dir.glob('??-??.jpg')),
            columns=['image_path'],
        )
        df_ = df.image_path.str.extract(r'(\d{2})-(\d{2}).jpg$')
        df['window_index'] = df_[0]
        df['sample_index'] = df_[1]

        logger.info('task_id=%r video_url=%r nsamples=%r', self.task_id, animation_url, len(df))
        return self


@dc.dataclass(frozen=True)
class LocatorContext:
    r"""Session 上下文数据，绑定当前正在执行的 LocatorTask。"""

    locator_task: LocatorTask


class LocatorService:
    r"""视觉拐点定位服务入口。

    提供两个异步接口:
        - ``locate``: 完整定位流水线 → ``LocatorResult``。
        - ``get_annotation_info``: 仅获取标注所需数据 → ``AnnotationInfo``。

    并发控制: 通过 ``semaphore`` 限制同时执行的定位任务数 (默认 = CONCURRENCY)。
    """

    semaphore: tp.ClassVar = asyncio.Semaphore(value=CONCURRENCY)

    @logfire.instrument(record_return=True)
    async def get_annotation_info(
        self,
        locator_id: CRLocatorIdType,
        *,
        config: LocatorConfig = LocatorConfig(),
    ) -> AnnotationInfo:
        r"""获取标注网格数据: 图片 URL + 元信息 + Excel 链接。

        不执行视觉指标计算和拐点定位，仅完成图片采样和上传。
        供标注前端使用。
        """
        locator_task = LocatorTask(locator_id, config=config)
        async with self.semaphore:
            with SessionContextManager[LocatorContext](
                LocatorContext(locator_task=locator_task)
            ):
                await locator_task.get_tasks()

                if config.return_images or config.return_excels:
                    await locator_task.cluster_event_windows()
                    await locator_task.get_sample_images()

                excels = dict[ScenarioIdType, list[str]]()
                if config.return_excels:
                    for scenario_id in locator_task.locator_data.result:
                        excels[scenario_id] = [
                            await locator_task.dump_and_upload_excel(scenario_id),
                        ]

                images = dict[ScenarioIdType, list[SampleImageInfo]]()
                if config.return_images:
                    df = await locator_task.upload_images_to_s3(locator_task.image_info_f)
                    for scenario_id, group in df.groupby(by='scenario_id'):
                        images[scenario_id] = [
                            SampleImageInfo(
                                cr_index=r.cr_index,
                                cr_desc=r.cr_desc,
                                window_index=r.window_index,
                                window_desc=r.window_desc,
                                sample_index=r.sample_index,
                                sample_desc=r.sample_desc,
                                image_url=r.file_url,
                            )
                            for r in group.itertuples(index=False)
                        ]

                return AnnotationInfo(
                    locator_id=locator_id,
                    locator_url=locator_task.locator_url,
                    metrics=locator_task.locator_data.metrics,
                    events=locator_task.event_names,
                    diff_type=locator_task.locator_data.diff_data.diff_type,
                    diff_url=locator_task.diff_url,
                    base_task_id=locator_task.base_task_id,
                    feat_task_id=locator_task.feat_task_id,
                    images=images,
                    excels=excels,
                )

    @logfire.instrument(record_return=True)
    async def locate(
        self,
        locator_id: CRLocatorIdType,
        *,
        config: LocatorConfig = LocatorConfig(),
        session_id: tp.Optional[SessionIdType] = None,
    ) -> LocatorResult:
        r"""执行完整的视觉拐点定位流水线。

        依次执行 get_tasks → cluster_event_windows → get_sample_images
        → compute_visual_metrics → get_result。

        Args:
            locator_id: CR Locator 任务 ID。
            config: 采样和输出配置。
            session_id: 可选的 session ID，用于资源隔离。

        Returns:
            每个场景的定位结果映射。

        Raises:
            LocatorFail: 定位完成但存在告警 (result 仍可用)。
        """
        locator_task = LocatorTask(locator_id, config=config)
        kwds = dict()
        if session_id is not None: kwds['id'] = session_id  # fmt: skip
        async with self.semaphore:
            with SessionContextManager[LocatorContext](
                LocatorContext(locator_task=locator_task), **kwds
            ):
                await locator_task.get_tasks()
                await locator_task.cluster_event_windows()
                await locator_task.get_sample_images()
                await locator_task.compute_visual_metrics()
                return await locator_task.get_result()


async def test_get_annotation_info():
    try:
        service = LocatorService()

        if 1:
            res = await service.get_annotation_info(
                4769625,
                config=LocatorConfig(return_images=True, return_excels=True),
            )
            assert res.locator_id == 4769625, res
            print(f'HIL: check res={res.model_copy(update=dict(images=None, excels=None))!r}')
            print(f'HIL: check images={res.images!r}')
            print(f'HIL: check excels={res.excels!r}')

    finally:
        if __name__ == '__main__': globals().update(locals())  # fmt: skip


async def test_locate():
    try:
        service = LocatorService()

        if 1:
            res = await service.locate(
                4769625,
                config=LocatorConfig(return_images=True, return_excels=True),
            )
            assert sorted(res) == ['7698998'], res
            cr_res = res['7698998']
            assert cr_res.cr_index == 13, cr_res
            assert cr_res.commit.commit.commit == 'c0a9fb4592297c49494d7033f053f82fdad1e9f9', (
                cr_res
            )
            assert cr_res.images, cr_res

    finally:
        if __name__ == '__main__': globals().update(locals())  # fmt: skip


async def test_locate_with_text():
    r"""
    测试不同 text 参数下的 visual CR locator 流程。

    验证 text 参数从 LocatorConfig 正确透传到 embedding API 调用链路。
    BEV 动画场景涉及 box 碰撞/相交，使用对应语义文本。

    注意: 当前默认 model_ids 为纯视觉模型，非空 text 路由到 VLEmbeddingExtractor
    会因 processor 无 chat template 失败。此处仅验证 text='' 的默认行为一致性。
    """
    try:
        service = LocatorService()

        if 1:
            for text in [
                'box collision in BEV',
                'vehicle intersection scenario',
                'bounding box overlap',
            ]:
                res = await service.locate(4769625, config=LocatorConfig(text=text))
                assert sorted(res) == ['7698998'], res
                cr_res = res['7698998']
                assert 13 in cr_res.cr_indices
                print(f'HIL: check res={res!r}')

    finally:
        if __name__ == '__main__': globals().update(locals())  # fmt: skip


if __name__ == '__main__':
    from conflog import configure_logging, configure_auto_tracing

    configure_logging(env='test')
    configure_auto_tracing(env='test')

    from ..tools.resources import resource_context

    with asyncio.Runner(debug=True) as runner:
        with resource_context():
            runner.run(test_get_annotation_info())
            runner.run(test_locate())
            runner.run(test_locate_with_text())

    service = self = LocatorService()
