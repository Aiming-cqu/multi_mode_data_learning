"""本阶段的本地单图 JSONL 预检；不执行尺寸过滤或图像去重。"""
import argparse
import json
from pathlib import Path

from PIL import Image


def check_rows(source):
    """返回合格记录、异常记录；相对图片路径以输入清单目录为基准。"""
    source = Path(source).resolve()
    good, errors, seen = [], [], set()
    with source.open(encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            row = None
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError("记录必须是 JSON 对象")
                sample_id = row.get("index")
                if not isinstance(sample_id, str) or not sample_id.strip():
                    raise ValueError("index 必须是非空字符串")
                if sample_id in seen:
                    raise ValueError("index 重复：保留第一次出现的 ID，后续同 ID 记录隔离")
                # 即使第一次记录图片损坏，也不让后续同 ID 悄悄替换它。
                seen.add(sample_id)
                if not isinstance(row.get("text"), str) or not row["text"].strip():
                    raise ValueError("本实验要求 text 为非空字符串")
                paths = row.get("images")
                if not isinstance(paths, list) or len(paths) != 1:
                    raise ValueError("本实验要求 images 恰好包含一张本地图片")
                if not isinstance(paths[0], str) or not paths[0].strip():
                    raise ValueError("图片路径必须是非空字符串")
                path = Path(paths[0]).expanduser()
                if not path.is_absolute():
                    path = source.parent / path
                path = path.resolve()
                if not path.is_file():
                    raise FileNotFoundError(f"图片文件不存在或不是普通文件：{path}")
                # open 只读头部还不够；load 强制实际解码像素。
                with Image.open(path) as img:
                    img.load()
                clean = dict(row)
                clean["images"] = [str(path)]
                good.append(clean)
            except (ValueError, OSError, Image.DecompressionBombError) as exc:
                errors.append({
                    "line": line_no,
                    "index": row.get("index") if isinstance(row, dict) else None,
                    "images": row.get("images") if isinstance(row, dict) else None,
                    "error_type": type(exc).__name__,
                    "reason": str(exc),
                    "record": row if row is not None else line.rstrip("\n"),
                })
    return good, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path,
                        help="必须是尚不存在的新目录，避免覆盖证据")
    args = parser.parse_args()
    good, errors = check_rows(args.input)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    for filename, rows in [("valid.jsonl", good), ("invalid.jsonl", errors)]:
        with (args.output_dir / filename).open("x", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {"input": str(args.input.resolve()), "total": len(good) + len(errors),
               "valid": len(good), "invalid": len(errors)}
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    # 成功执行分流返回 0；存在隔离记录不等同于预检程序失败。


if __name__ == "__main__":
    main()
