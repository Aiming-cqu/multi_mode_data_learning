#!/usr/bin/env -S pixi run -- default

r"""
批量调用 Visual CR Locator API 并输出 CSV 报告。

Usage::

    # 从文件读取 locator_id 列表
    python scripts/batch_locate.py -i ids.txt

    # 从 stdin 读取
    echo "4769625" | python scripts/batch_locate.py -o result.csv

    # 覆盖单个 LocatorConfig 参数
    python scripts/batch_locate.py -i ids.txt --max-windows 5 --window-duration 5000

    # JSON 批量覆盖
    python scripts/batch_locate.py -i ids.txt --config '{"max_windows": 5}'

    # 下载 Excel 报告
    python scripts/batch_locate.py -i ids.txt --return-excels --download-excels

    # 指定 API 和并发
    python scripts/batch_locate.py -i ids.txt -a http://10.152.28.24:8061 -w 8
"""

from __future__ import annotations

import csv
import json
import logging
import os
import typing as tp
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
import typer

from lib.utils.io_utils import (
    PathLikeStr,
    is_path_stdio,
    open_maybe_stdio,
)
from lib.services.visual_cr_locator_types import (
    LocatorConfig,
    LocatorResponse,
    LocatorScenarioResult,
)

logger = logging.getLogger(__name__)

DEFAULT_API_URL: str = os.environ['TRIAGE_LOCATOR_API_URL']

CSV_COLUMNS: list[str] = [
    'locator_id',
    'ticket',
    'status',
    'message',
    'scenario_id',
    'cr_index',
    'commit',
    'excel_urls',
]


def read_locator_ids(input_path: PathLikeStr) -> list[int]:
    r"""从文件或 stdin 读取 locator_id 列表。"""
    ids: list[int] = []
    with open_maybe_stdio(input_path, encoding='utf-8') as source:
        for line in source:
            line = line.strip()
            if line and not line.startswith('#'):
                try:
                    ids.append(int(line))
                except ValueError:
                    typer.echo(f'跳过无效 ID: {line}', err=True)
    return ids


def call_locate(
    locator_id: int,
    config: LocatorConfig,
    *,
    api_url: str,
    timeout: float,
) -> LocatorResponse:
    r"""调用同步定位接口，返回 LocatorResponse。"""
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(
            f'{api_url}/locate',
            params={'locator_id': locator_id},
            json=config.model_dump(),
        )
        resp.raise_for_status()
        return LocatorResponse.model_validate(resp.json())


def download_excel(url: str, output_path: Path, *, timeout: float = 60.0) -> bool:
    r"""下载单个 Excel 文件，返回是否成功。"""
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
            resp.raise_for_status()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(resp.content)
            return True
    except Exception:
        logger.exception('download failed: %s', url)
        return False


def flatten_response(
    locator_id: int,
    response: LocatorResponse,
) -> list[dict[str, tp.Any]]:
    r"""将 LocatorResponse 展平为每个 scenario 一行的 dict 列表。"""
    if not response.result:
        return [
            {
                'locator_id': locator_id,
                'ticket': response.ticket,
                'status': response.status,
                'message': response.message,
                'scenario_id': '',
                'cr_index': '',
                'commit': '',
                'excel_urls': '',
            },
        ]

    rows = []
    for scenario_id, sr in response.result.items():
        rows.append(
            {
                'locator_id': locator_id,
                'ticket': response.ticket,
                'status': response.status,
                'message': response.message,
                'scenario_id': scenario_id,
                'cr_index': sr.cr_index,
                'commit': sr.commit.commit if sr.commit else '',
                'excel_urls': ' '.join(sr.excels) if sr.excels else '',
            },
        )
    return rows


def process_one(
    locator_id: int,
    config: LocatorConfig,
    *,
    api_url: str,
    timeout: float,
    download_excels: bool,
    output_dir: Path,
) -> list[dict[str, tp.Any]]:
    r"""处理单个 locator_id：调用 API → 可选下载 Excel → 返回行记录。"""
    try:
        response = call_locate(locator_id, config, api_url=api_url, timeout=timeout)
    except Exception as exc:
        return [
            {
                'locator_id': locator_id,
                'ticket': '',
                'status': 'error',
                'message': repr(exc),
                'scenario_id': '',
                'cr_index': '',
                'commit': '',
                'excel_urls': '',
            },
        ]

    rows = flatten_response(locator_id, response)

    if download_excels and response.result:
        excel_dir = output_dir / 'excels' / str(locator_id)
        for scenario_id, sr in response.result.items():
            for i, url in enumerate(sr.excels or []):
                fname = f'{scenario_id}_{i}.xlsx'
                download_excel(url, excel_dir / fname)

    return rows


def _parse_int_pair(value: tp.Optional[str]) -> tp.Optional[tuple[int, int]]:
    r"""解析 'w,h' 格式的整数对。"""
    if value is None:
        return None
    a, b = value.split(',')
    return (int(a.strip()), int(b.strip()))


def write_csv_rows(
    output_path: PathLikeStr,
    rows: list[dict[str, tp.Any]],
):
    r"""将结果写到 CSV 文件或 stdout。"""
    with open_maybe_stdio(output_path, 'w', encoding='utf-8', newline='') as output_file:
        writer = csv.DictWriter(output_file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


app = typer.Typer(help='批量调用 Visual CR Locator API 并输出 CSV 报告。')


@app.command()
def main(
    # --- 脚本参数 ---
    input_path: tp.Annotated[
        str,
        typer.Option('--input', '-i', help="输入文件路径；默认 stdin；传 '-' 显式指定 stdin"),
    ] = '-',
    output_path: tp.Annotated[
        str,
        typer.Option(
            '--output',
            '-o',
            help="CSV 输出路径；传 '-' 输出到 stdout (默认: {input}.result.csv)",
        ),
    ] = '-',
    api_url: tp.Annotated[
        str,
        typer.Option('--api-url', '-a', help='API 基础 URL'),
    ] = DEFAULT_API_URL,
    workers: tp.Annotated[int, typer.Option('--workers', '-w', help='并发数')] = 4,
    timeout: tp.Annotated[float, typer.Option('--timeout', '-t', help='API 超时 (秒)')] = 300.0,
    config_json: tp.Annotated[
        tp.Optional[str],
        typer.Option('--config', '-c', help='LocatorConfig JSON 覆盖 (合并到默认值)'),
    ] = None,
    # --- LocatorConfig 参数 (每个都可单独覆盖) ---
    max_windows: tp.Annotated[tp.Optional[int], typer.Option(help='最大采样窗口数')] = None,
    window_duration: tp.Annotated[
        tp.Optional[int], typer.Option(help='窗口采样时长 (ms)')
    ] = None,
    window_offset: tp.Annotated[tp.Optional[int], typer.Option(help='窗口偏移 (ms)')] = None,
    sample_interval: tp.Annotated[tp.Optional[int], typer.Option(help='采样间隔 (ms)')] = None,
    sample_wh: tp.Annotated[tp.Optional[str], typer.Option(help='图像采样宽高 (w,h)')] = None,
    sample_xy: tp.Annotated[tp.Optional[str], typer.Option(help='图像采样中心点 (x,y)')] = None,
    sample_xy_e2e: tp.Annotated[
        tp.Optional[str], typer.Option(help='端到端采样中心点 (x,y)')
    ] = None,
    use_vlm_animation: tp.Annotated[
        tp.Optional[bool],
        typer.Option('--use-vlm-animation/--no-vlm-animation', help='使用 VLM 动画'),
    ] = None,
    return_images: tp.Annotated[
        tp.Optional[bool],
        typer.Option('--return-images/--no-return-images', help='是否返回图片'),
    ] = None,
    return_excels: tp.Annotated[
        tp.Optional[bool],
        typer.Option('--return-excels/--no-return-excels', help='是否返回 Excel URL'),
    ] = None,
    download_excels: tp.Annotated[
        bool,
        typer.Option('--download-excels/--no-download-excels', help='是否下载 Excel 文件'),
    ] = False,
) -> None:
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')

    # --- 读取 locator_ids ---
    locator_ids = read_locator_ids(input_path)
    if not locator_ids:
        typer.echo('未找到有效的 locator_id', err=True)
        raise typer.Exit(code=1)

    # --- 构建 LocatorConfig ---
    overrides: dict[str, tp.Any] = {}
    if config_json:
        overrides.update(json.loads(config_json))
    # 单独参数覆盖 JSON 中的同名字段
    if max_windows is not None:
        overrides['max_windows'] = max_windows
    if window_duration is not None:
        overrides['window_duration'] = window_duration
    if window_offset is not None:
        overrides['window_offset'] = window_offset
    if sample_interval is not None:
        overrides['sample_interval'] = sample_interval
    if sample_wh is not None:
        overrides['sample_wh'] = _parse_int_pair(sample_wh)
    if sample_xy is not None:
        overrides['sample_xy'] = _parse_int_pair(sample_xy)
    if sample_xy_e2e is not None:
        overrides['sample_xy_e2e'] = _parse_int_pair(sample_xy_e2e)
    if use_vlm_animation is not None:
        overrides['use_vlm_animation'] = use_vlm_animation
    if return_images is not None:
        overrides['return_images'] = return_images
    if return_excels is not None:
        overrides['return_excels'] = return_excels
    if download_excels:
        overrides.setdefault('return_excels', True)
    config = LocatorConfig(**overrides)

    # --- 输出路径 ---
    output_is_stdout = is_path_stdio(output_path)
    out_dir = Path('.') if output_is_stdout else Path(output_path).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    def echo_status(message: str):
        typer.echo(message, err=output_is_stdout)

    echo_status(f'输入: {len(locator_ids)} 个 locator_id')
    echo_status(f'API: {api_url}')
    echo_status(f'Config: {config.model_dump_json()}')
    echo_status(f'并发: {workers}, 超时: {timeout}s')
    echo_status(f'输出: {"stdout" if output_is_stdout else output_path}')

    # --- 并发执行 ---
    all_rows: list[dict[str, tp.Any]] = []
    success = 0
    fail = 0

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                process_one,
                lid,
                config,
                api_url=api_url,
                timeout=timeout,
                download_excels=download_excels,
                output_dir=out_dir,
            ): lid
            for lid in locator_ids
        }
        for future in as_completed(futures):
            lid = futures[future]
            try:
                rows = future.result()
                all_rows.extend(rows)
                status = rows[0]['status'] if rows else 'error'
                if status == 'success':
                    success += 1
                    echo_status(f'  ✓ {lid}')
                else:
                    fail += 1
                    msg = rows[0].get('message', '')[:80] if rows else ''
                    echo_status(f'  ✗ {lid}: {msg}')
            except Exception as exc:
                fail += 1
                echo_status(f'  ✗ {lid}: {exc!r}')
                all_rows.append(
                    {
                        'locator_id': lid,
                        'ticket': '',
                        'status': 'error',
                        'message': repr(exc),
                        'scenario_id': '',
                        'cr_index': '',
                        'commit': '',
                        'excel_urls': '',
                    },
                )

    # --- 按输入顺序排序 ---
    id_order = {lid: i for i, lid in enumerate(locator_ids)}
    all_rows.sort(key=lambda r: id_order.get(r['locator_id'], len(locator_ids)))

    # --- 写入 CSV ---
    write_csv_rows(output_path, all_rows)

    echo_status(f'\n完成: 成功={success}, 失败={fail}, 总行数={len(all_rows)}')
    echo_status(f'CSV: {"stdout" if output_is_stdout else output_path}')
    if download_excels:
        echo_status(f'Excel: {out_dir / "excels"}/')

    if fail > 0:
        raise typer.Exit(code=2)


if __name__ == '__main__':
    app()
