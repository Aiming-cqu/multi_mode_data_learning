#!/bin/sh
""":"
exec pixi run -- test -s "$0" "$@"
"""
#!/usr/bin/env -S pixi run -- test -s

from __future__ import absolute_import, annotations

import pytest

import tempfile
import pandas as pf

from lib.utils.excel_utils import (
    FORMAT_TEXT_UNDER_IMAGE,
    CellFormat,
    apply_cell_format,
    apply_data_validation,
    embed_images,
    write_df,
)

from tests.common import TEST_DATA_DIR


def test_embed_images():
    r"""
    测试 embed_images 的所有布局模式，写入同一个 workbook 的不同 sheet。

    场景：3 行（scene 01/02/03）x 3 列图（base/cr/feature）+ label 列。

    验证:
        - 所有布局模式均无报错
        - 输出 xlsx 文件非空
        - 覆盖：text_under_image、text_above_image、overlay_none、overlay_centered

    Parameters:
        -
    """

    images_dir = (TEST_DATA_DIR / 'cr_locator/images').as_posix()
    images_size = (300, 400)
    groups = ['01', '02', '03']

    df = pf.DataFrame(
        {
            'scene': groups,
            'image_base': [f'{images_dir}/{g}/base-no-collision.png' for g in groups],
            'image_cr': [f'{images_dir}/{g}/cr-collision.png' for g in groups],
            'image_feature': [f'{images_dir}/{g}/feature-collision.png' for g in groups],
            'label_base': [None, None, None],
            'label_cr': [None, 'F2P', None],
            'label_feature': [None, None, 'P2F'],
        }
    )
    df.index.name = 'id'
    image_cols = ['image_base', 'image_cr', 'image_feature']
    label_cols = ['label_base', 'label_cr', 'label_feature']
    image_f = df[['scene'] + image_cols]
    label_f = df[['scene'] + label_cols]

    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
        print(f'test_embed_images: save to {f.name!r}')

        with pf.ExcelWriter(f.name, engine="xlsxwriter") as writer:
            for sheet_name, desc, cell_format, padding in [
                (
                    'text_under_image',
                    'Image at top, text at bottom (FORMAT_TEXT_UNDER_IMAGE)',
                    FORMAT_TEXT_UNDER_IMAGE,
                    0,
                ),
                (
                    'text_above_image',
                    'Image at bottom, text at top',
                    CellFormat(align="center", valign="top"),
                    8,
                ),
                ('overlay_none', 'Overlay: fmt=None, no cell resize', None, 0),
                (
                    'overlay_centered',
                    'Overlay: fully-centred fmt, no cell resize',
                    CellFormat(align="center", valign="vcenter"),
                    8,
                ),
            ]:
                write_df(writer, sheet_name, label_f)
                embed_images(
                    writer,
                    sheet_name,
                    image_f,
                    images_size,
                    columns=image_cols,
                    cell_format=cell_format,
                    padding=padding,
                )
                if cell_format:
                    apply_cell_format(
                        writer,
                        sheet_name,
                        label_f,
                        cell_format,
                        columns=['scene'],
                    )
                apply_data_validation(writer, sheet_name, label_f)

        print(f'HIL: check created file: {f.name!r}')
