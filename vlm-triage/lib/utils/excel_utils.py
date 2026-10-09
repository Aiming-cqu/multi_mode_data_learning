#!/usr/bin/env -S pixi run -- test -s

from __future__ import absolute_import, annotations

import typing as tp
import pandas as pf

if tp.TYPE_CHECKING:
    from xlsxwriter import Workbook
    from xlsxwriter.format import Format
    from xlsxwriter.worksheet import Worksheet, CellStringTuple


# ---------------------------------------------------------------------------
# Config structs
# ---------------------------------------------------------------------------


class CellFormat(tp.TypedDict, total=False):
    r"""单元格格式，字段直接对应 xlsxwriter add_format() 参数，按需设置部分属性。"""

    bg_color: str
    font_color: str
    align: str
    valign: str


class Condition(tp.TypedDict, total=False):
    r"""条件格式触发条件，字段直接对应 xlsxwriter conditional_format() 参数。"""

    type: str
    criteria: str
    value: tp.Any

    min_type: str
    min_value: tp.Any
    mid_type: str
    mid_value: tp.Any
    max_type: str
    max_value: tp.Any
    min_color: str
    mid_color: str
    max_color: str


class DataValidation(tp.TypedDict, total=True):
    r"""数据验证配置，字段直接对应 xlsxwriter data_validation() 参数。"""

    validate: tp.Literal["list"]
    source: tp.Sequence[str]


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

FORMAT_TEXT_ON_GREEN: CellFormat = CellFormat(bg_color='#C6EFCE', font_color='#2A2A2A')
FORMAT_TEXT_UNDER_IMAGE: CellFormat = CellFormat(align="center", valign="bottom")

CONDITION_FOREVER_TRUE: Condition = Condition(type="formula", criteria='=1=1')
CONDITION_EQ_TRUE: Condition = Condition(type="cell", criteria='equal to', value="TRUE")
# Numeric gradient (3-color scale) commonly used for numeric columns
CONDITION_NUMERIC_GRADIENT: Condition = Condition(
    type="3_color_scale",
    min_type="min",
    mid_type="percentile",
    mid_value=50,
    max_type="max",
    min_color='#63BE7B',
    mid_color='#FFEB84',
    max_color='#F8696B',
)

VALIDATION_DIFF_TYPE: DataValidation = DataValidation(validate="list", source=["P2F", "F2P"])

_PX_TO_PT: float = 0.75  # row height: pixels → points
_PX_TO_CH: float = 0.14  # col width:  pixels → character units


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _data_range(df: pf.DataFrame, closed: bool = False) -> tuple[int, int, int, int]:
    r"""Return (row1, col1, row2, col2) of the data cell area (0-indexed)."""
    startrow: int = len(df.columns.names)
    startcol: int = len(df.index.names)
    startrow += startrow > 1
    endrow: int = startrow + len(df.index) - closed
    endcol: int = startcol + len(df.columns) - closed
    return (startrow, startcol, endrow, endcol)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def write_df(writer: pf.ExcelWriter, sheet_name: str, df: pf.DataFrame, **to_excel_kwds):
    r"""Write DataFrame to a sheet with freeze panes at the data start."""
    r0, c0, _, _ = _data_range(df)
    df.to_excel(
        writer,
        sheet_name=sheet_name,
        columns=None,
        header=True,
        index=True,
        startrow=0,
        startcol=0,
        freeze_panes=(r0, c0),
        **to_excel_kwds
    )


def apply_cell_format(
    writer: pf.ExcelWriter,
    sheet_name: str,
    df: pf.DataFrame,
    cell_format: CellFormat,
    columns: tp.Optional[list[tp.Hashable]] = None,
    na_value: tp.Optional[str] = None,
):
    r"""
    TODO: update
    """
    book: 'Workbook' = writer.book
    fmt: 'Format' = book.add_format(cell_format)
    sheet: 'Worksheet' = writer.sheets[sheet_name]
    r0, c0, r1, _ = _data_range(df)
    col_indices: tp.Sequence[int]
    if columns is None: col_indices = range(c0, c0 + len(df.columns))  # fmt: skip
    else: col_indices = c0 + df.columns.get_indexer(columns)  # fmt: skip
    for row_idx in range(r0, r1):
        if row := sheet.table.get(row_idx):
            for col_idx in col_indices:
                if cell := row.get(col_idx):
                    row[col_idx] = cell._replace(format=fmt)
                elif na_value is not None:
                    sheet.write_string(row_idx, col_idx, na_value, cell_format=fmt)


def apply_conditional_format(
    writer: pf.ExcelWriter,
    sheet_name: str,
    df: pf.DataFrame,
    condition: Condition = CONDITION_EQ_TRUE,
    cell_format: tp.Optional[CellFormat] = FORMAT_TEXT_ON_GREEN,
    column: tp.Optional[tp.Union[tp.Hashable, list[tp.Hashable]]] = None,
):
    r"""Apply a conditional format rule to the data area of a sheet."""

    fmt: tp.Optional['Format'] = None
    if cell_format:
        book: 'Workbook' = writer.book
        fmt = book.add_format(cell_format)

    sheet: 'Worksheet' = writer.sheets[sheet_name]
    r0, c0, r1, _ = _data_range(df, closed=True)
    if column is None: c_from, c_to = c0, c0 + len(df.columns) - 1  # fmt: skip
    elif isinstance(column, list): c_from, c_to = c0 + df.columns.get_indexer(column)  # fmt: skip
    else: c_from = c_to = c0 + df.columns.get_loc(column)  # fmt: skip
    ret: int = sheet.conditional_format(
        r0,
        c_from,
        r1,
        c_to,
        options={**condition, 'format': fmt} if fmt else condition,
    )
    if ret != 0:
        raise RuntimeError(f'apply_conditional_format failed on {sheet_name=}: {ret}')


def apply_data_validation(
    writer: pf.ExcelWriter,
    sheet_name: str,
    df: pf.DataFrame,
    validation: DataValidation = VALIDATION_DIFF_TYPE,
    column: tp.Optional[tp.Union[tp.Hashable, list[tp.Hashable]]] = None,
):
    r"""
    Apply dropdown-list validation to a contiguous column range in a sheet.

    Args:
        column: single column name, or (first_col, last_col) for a range.
    """
    sheet: 'Worksheet' = writer.sheets[sheet_name]
    r0, c0, r1, _ = _data_range(df, closed=True)
    if column is None: c_from, c_to = c0, c0 + len(df.columns) - 1  # fmt: skip
    elif isinstance(column, list): c_from, c_to = c0 + df.columns.get_indexer(column)  # fmt: skip
    else: c_from = c_to = c0 + df.columns.get_loc(column)  # fmt: skip
    ret: int = sheet.data_validation(r0, c_from, r1, c_to, options=validation)
    if ret != 0:
        raise RuntimeError(f'data_validation failed on {sheet_name=}: {ret}')


def embed_images(
    writer: pf.ExcelWriter,
    sheet_name: str,
    df: pf.DataFrame,
    image_size: tuple[int, int],
    columns: tp.Optional[list[tp.Hashable]] = None,
    cell_format: tp.Optional[CellFormat] = FORMAT_TEXT_UNDER_IMAGE,
    padding: int = 0,
):
    r"""
    Embed images from path-valued columns into Excel cells.

    Layout is driven by ``cell_format``:

    - ``fmt=None``: overlay mode — image inserted at ``(padding, padding)`` with no
      cell resizing or text formatting.
    - Fully-centred ``fmt`` (``align="center"`` + ``valign="center"/"vcenter"``):
      same as overlay mode.
    - Any other ``fmt``: cell is resized to fit both image and a text row.
      ``valign`` controls which side the text occupies:

      - ``valign="bottom"`` (default, ``FORMAT_TEXT_UNDER_IMAGE``): image at top,
        text at bottom. ``y_offset = padding``.
      - ``valign="top"``: text at top, image below. ``y_offset = default_text_h + padding``.

      Row height = ``(img_h + 2*padding) * pt_per_px + default_text_h_pt``.
      Column width ≥ ``(img_w + 2*padding) * ch_per_px``.

    Args:
        writer: ExcelWriter (xlsxwriter engine).
        df: DataFrame whose image columns contain file-system paths.
        sheet_name: Target worksheet name.
        image_size: ``(width, height)`` in pixels; all images assumed the same size.
        columns: Column names holding image paths. Defaults to all columns.
        fmt: Cell text format. Drives layout logic (see above).
        padding: Extra pixel padding around the image.
    """
    book: 'Workbook' = writer.book
    sheet: 'Worksheet' = writer.sheets[sheet_name]
    r0, c0, _, _ = _data_range(df)
    col_indices: tp.Sequence[int]
    if columns is None:
        col_indices = range(c0, c0 + len(df.columns))
    else:
        col_indices = c0 + df.columns.get_indexer(columns)
        df = df[columns]

    # BUG: x padding cause image sacled and don't know why
    img_w_px, img_h_px = image_size
    padded_h_pt: float = (img_h_px + 2 * padding) * _PX_TO_PT
    padded_w_ch: float = img_w_px * _PX_TO_CH
    fmt: tp.Optional['Format'] = None
    text_align = text_valign = None
    if cell_format is not None:
        fmt = book.add_format(cell_format)
        text_align = cell_format.get("align")
        text_valign = cell_format.get("valign")

    for row_idx, (_, row) in enumerate(df.iterrows(), start=r0):
        cell_h_pt: float = sheet.row_sizes.get(row_idx, sheet.default_row_height)
        img_opts: dict[str, tp.Any] = {
            "y_offset": padding + (cell_h_pt if text_valign == "top" else 0) / _PX_TO_PT,
        }
        cell_h_pt = (
            cell_h_pt + padded_h_pt
            if text_valign in ("top", "bottom")
            else max(cell_h_pt, padded_h_pt)
        )
        sheet.set_row(row_idx, height=cell_h_pt)
        row_: tp.Optional[dict[int, 'CellStringTuple']] = sheet.table.get(row_idx)
        for col_idx, img_path, is_na in zip(col_indices, row, pf.isna(row), strict=True):
            if fmt and row_:
                if cell := row_.get(col_idx): row_[col_idx] = cell._replace(format=fmt)  # fmt: skip
                else: sheet.write_string(row_idx, col_idx, '', cell_format=fmt)  # fmt: skip
            if is_na: continue  # fmt: skip
            # cell_w_ch: float = sheet.col_info.get(col_idx, (sheet.default_col_width,))[0]
            # img_opts["x_offset"] = padding + (
            #     cell_w_ch if text_align == "left" else 0
            # ) / _PX_TO_CH
            img_opts["description"] = img_path
            sheet.insert_image(row_idx, col_idx, img_path, options=img_opts)

    for col_idx in col_indices:
        # cell_w_ch: float = sheet.col_info.get(col_idx, (sheet.default_col_width,))[0]
        # cell_w_ch = (
        #     cell_w_ch + padded_w_ch
        #     if text_align in ("left", "right")
        #     else max(cell_w_ch, padded_w_ch)
        # )
        sheet.set_column(col_idx, col_idx, width=padded_w_ch)

    return


# ---------------------------------------------------------------------------
# Tests (human-in-loop: open the generated .xlsx to verify visual output)
# ---------------------------------------------------------------------------

def test_write_with_format():
    r"""
    测试 write_df + apply_conditional_format + apply_cell_format + apply_data_validation 组合。

    验证:
        - 各种 DataFrame 结构（简单、命名索引、多级索引、多级列）写入无报错
        - 条件格式（equal TRUE 绿色高亮）和基础格式（=1=1 全量绿色）应用无报错
        - label 列下拉列表验证应用无报错
        - 输出文件路径打印至 stdout 供人工验证

    Parameters:
        -
    """
    import tempfile

    try:
        simple_f = pf.DataFrame(
            {
                'bool': [True, False, False, True],
                'int': [1, 2, 3, 4],
                'float': [1.1, 2.2, 3.3, 4.4],
                'label': [None, "F2P", "P2F", None],
            }
        )
        named_f = simple_f.copy()
        named_f.index.name = 'index'
        named_f.columns.name = 'columns'
        multi_index_f = pf.concat([named_f, named_f], keys=['R1', 'R2'])
        multi_columns_f = pf.concat([named_f, named_f], axis="columns", keys=['C1', 'C2'])

        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            print(f'test_write_with_format: save to {f.name!r}')

            with pf.ExcelWriter(f.name, engine="xlsxwriter") as writer:
                for sheet_name, df in [
                    ('simple_f', simple_f),
                    ('named_f', named_f),
                    ('multi_index_f', multi_index_f),
                    ('multi_columns_f', multi_columns_f),
                ]:
                    write_df(writer, sheet_name, df)
                    apply_cell_format(
                        writer,
                        sheet_name,
                        df,
                        {**FORMAT_TEXT_ON_GREEN, "bg_color": '#EFC6CE', "align": "center"},
                        na_value='',
                    )
                    apply_conditional_format(writer, sheet_name, df)
                    apply_conditional_format(
                        writer,
                        sheet_name,
                        df,
                        condition=CONDITION_NUMERIC_GRADIENT,
                        cell_format=None,
                    )
                    if 'label' in df.columns:
                        apply_data_validation(writer, sheet_name, df, column='label')

            print(f'HIL: check created file: {f.name!r}')

    finally:
        if __name__ == '__main__': globals().update(locals())  # fmt: skip


if __name__ == '__main__':
    from conflog import configure_logging

    configure_logging(env="test")

    test_write_with_format()
