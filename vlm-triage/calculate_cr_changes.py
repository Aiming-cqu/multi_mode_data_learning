#!/usr/bin/env python3

import pandas as pd
import numpy as np
import os
import glob


def get_predicates_and_outliers(cr_metric_f: pd.DataFrame):
    """Extract predicate and outlier dataframes from CR metrics."""
    sb_f = cr_metric_f.xs("base", axis="columns", level="end")  # 获取与base图像的相似度
    sf_f = cr_metric_f.xs("feature", axis="columns", level="end")  # 获取与feature图像的相似度
    s_e2e_s = sf_f.iloc[0]  # base_version对feature_version的相似度
    predicate_f = sb_f.iloc[1:-1] < sf_f.iloc[1:-1]
    predicate_a = sb_f.iloc[1:-1] - sf_f.iloc[1:-1]
    outlier_f = (sb_f.iloc[1:-1] < s_e2e_s) & (sf_f.iloc[1:-1] < s_e2e_s)
    return (predicate_f, outlier_f, predicate_a)


def calculate_cr_changes(predicate_a: pd.DataFrame):
    """Calculate the mean of predicate_a for each CR index."""
    cr_changes = predicate_a.mean(axis=1)
    return cr_changes


def process_csv_file(file_path: str):
    """Process a single CSV file and return CR changes."""
    print(f"Processing {file_path}")

    # Read CSV with multi-level headers
    cr_metric_f = pd.read_csv(
        file_path,
        header=list(range(5)),
        index_col=0,
    )

    # Get predicates and outliers
    predicate_f, outlier_f, predicate_a = get_predicates_and_outliers(cr_metric_f)

    # Calculate CR changes (mean of predicate_a for each row)
    cr_changes = calculate_cr_changes(predicate_a)

    return cr_changes


def main():
    # Get all converted CSV files in the directory
    data_dir = "/Users/didi/workspace/vlm_triage/vlm-triage/tests/data/cr_locator"
    csv_files = glob.glob(os.path.join(data_dir, "*_converted.csv"))

    # Extract just the filenames from the full paths
    csv_files = [os.path.basename(f) for f in csv_files]

    # Dictionary to store results
    results = {}

    # Process each file
    for csv_file in csv_files:
        file_path = os.path.join(data_dir, csv_file)
        cr_index = csv_file.split('_')[2].split('.')[0]  # Extract CR index from filename
        cr_changes = process_csv_file(file_path)
        results[cr_index] = cr_changes

    # Create output DataFrame
    output_df = pd.DataFrame(results)
    output_df.index.name = 'cr_index'

    # Print results in the required format
    print("cr_index", end="")
    for cr_index in results.keys():
        print(f" {cr_index}_change_mean", end="")
    print()

    for idx in output_df.index:
        print(f"{idx}", end="")
        for col in output_df.columns:
            print(f" {output_df.loc[idx, col]:.6f}", end="")
        print()


if __name__ == "__main__":
    main()
