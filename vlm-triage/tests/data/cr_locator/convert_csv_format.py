#!/usr/bin/env python3
"""
CSV格式转换脚本

将层次化CSV格式转换为扁平化列格式，与cr_locator-4391943-embedding_metric.csv格式一致。

使用方法:
python convert_csv_format.py <input_file> <output_file>

示例:
python convert_csv_format.py cr_locator_4541405.csv cr_locator_4541405_converted.csv
"""

import csv
import sys
from typing import List, Dict, Tuple


def parse_header_structure(header_rows: List[List[str]]) -> List[Dict[str, str]]:
    """
    解析源文件的层次化头部结构，生成扁平化的列配置

    Args:
        header_rows: 5行头部数据，每行的第一个元素是列名标识符

    Returns:
        List of column configurations with keys: model_id, metric_name, end, window_index, sample_index
    """
    # 跳过第一列（列名标识符），从第二列开始处理数据
    model_ids = header_rows[0][1:]
    metric_names = header_rows[1][1:]
    ends = header_rows[2][1:]
    window_indices = header_rows[3][1:]
    sample_indices = header_rows[4][1:]

    columns = []
    current_model = ""
    current_metric = ""
    current_end = ""
    current_window = ""

    for i in range(len(sample_indices)):
        # 更新当前的model_id（如果非空）
        if model_ids[i].strip():
            current_model = model_ids[i].strip()

        # 更新当前的metric_name（如果非空）
        if metric_names[i].strip():
            current_metric = metric_names[i].strip()

        # 更新当前的end（如果非空）
        if ends[i].strip():
            current_end = ends[i].strip()

        # 更新当前的window_index（如果非空）
        if window_indices[i].strip():
            current_window = window_indices[i].strip()

        # sample_index应该总是有值
        sample_idx = sample_indices[i].strip()

        if sample_idx:  # 只处理有sample_index的列
            columns.append(
                {
                    'model_id': current_model,
                    'metric_name': current_metric,
                    'end': current_end,
                    'window_index': current_window,
                    'sample_index': sample_idx,
                }
            )

    return columns


def convert_csv_format(input_file: str, output_file: str):
    """
    转换CSV文件格式

    Args:
        input_file: 输入文件路径
        output_file: 输出文件路径
    """
    # 读取输入文件
    with open(input_file, 'r', newline='') as f:
        reader = csv.reader(f)
        rows = list(reader)

    if len(rows) < 5:
        raise ValueError("输入文件至少需要5行头部信息")

    # 提取头部信息
    header_rows = rows[:5]

    # 解析列结构
    columns = parse_header_structure(header_rows)

    # 提取数据行（跳过cr_index行，即第6行）
    data_rows = rows[6:] if len(rows) > 6 else []

    # 准备输出的头部
    output_headers = [
        ['model_id'] + [col['model_id'] for col in columns],
        ['metric_name'] + [col['metric_name'] for col in columns],
        ['end'] + [col['end'] for col in columns],
        ['window_index'] + [col['window_index'] for col in columns],
        ['sample_index'] + [col['sample_index'] for col in columns],
        ['cr_index'] + [''] * len(columns),  # cr_index行为空
    ]

    # 准备输出的数据行
    output_data = []
    for row in data_rows:
        if len(row) > 0:
            # 第一列是cr_index值
            cr_index = row[0] if row[0] else ''
            # 剩余列是数据值（跳过第一列的标识符）
            data_values = row[1:]
            # 确保数据长度匹配
            if len(data_values) < len(columns):
                # 如果数据不足，用空字符串填充
                data_values.extend([''] * (len(columns) - len(data_values)))
            elif len(data_values) > len(columns):
                # 如果数据过多，截断
                data_values = data_values[: len(columns)]

            output_row = [cr_index] + data_values
            output_data.append(output_row)

    # 写入输出文件
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        # 写入头部
        for header_row in output_headers:
            writer.writerow(header_row)
        # 写入数据
        for data_row in output_data:
            writer.writerow(data_row)

    print(f"转换完成！输出文件: {output_file}")
    print(f"原始列数: {len(header_rows[4])}")
    print(f"转换后列数: {len(columns)}")


def main():
    if len(sys.argv) != 3:
        print("使用方法: python convert_csv_format.py <input_file> <output_file>")
        print(
            "示例: python convert_csv_format.py cr_locator_4541405.csv cr_locator_4541405_converted.csv"
        )
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    try:
        convert_csv_format(input_file, output_file)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
