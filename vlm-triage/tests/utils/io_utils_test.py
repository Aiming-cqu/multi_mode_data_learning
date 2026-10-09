#!/usr/bin/env -S pixi run -- test

from __future__ import absolute_import, annotations

import pytest

import io, sys

from pathlib import Path

from lib.utils.io_utils import ensure_seekable_input, is_path_stdio, open_maybe_stdio


class _NonSeekableBinary:
    def __init__(self, data: bytes):
        self._buffer = io.BytesIO(data)

    def read(self, size: int = -1) -> bytes:
        return self._buffer.read(size)

    def seekable(self) -> bool:
        return False


@pytest.mark.functional
def test__functional__is_path_stdio():
    r"""
    测试 stdio 路径判断。

    验证:
        - '-' 被识别为 stdio
        - 普通路径不会被识别为 stdio

    Parameters:
        -
    """
    assert is_path_stdio('-') is True
    assert is_path_stdio('/tmp/output.txt') is False


@pytest.mark.functional
def test__functional__open_maybe_stdio__file(tmp_path: Path):
    r"""
    测试 open_maybe_stdio 对普通文件路径的读写。

    验证:
        - 写模式会自动创建父目录
        - 读回内容与写入一致

    Parameters:
        -
    """
    file_path = tmp_path / 'nested' / 'demo.txt'

    with open_maybe_stdio(file_path, 'w', encoding='utf-8') as f:
        _ = f.write('hello')

    with open_maybe_stdio(file_path, 'r', encoding='utf-8') as f:
        assert f.read() == 'hello'


@pytest.mark.functional
def test__functional__open_maybe_stdio__stdio(monkeypatch: pytest.MonkeyPatch):
    r"""
    测试 open_maybe_stdio 对标准输入输出的映射。

    验证:
        - '-' 读模式返回 sys.stdin
        - '-' 写模式返回 sys.stdout

    Parameters:
        -
    """
    stdin = io.StringIO('from-stdin')
    stdout = io.StringIO()
    monkeypatch.setattr(sys, 'stdin', stdin)
    monkeypatch.setattr(sys, 'stdout', stdout)

    with open_maybe_stdio('-', 'r', encoding='utf-8') as f:
        assert f.read() == 'from-stdin'

    with open_maybe_stdio('-', 'w', encoding='utf-8') as f:
        _ = f.write('to-stdout')

    assert stdout.getvalue() == 'to-stdout'


@pytest.mark.functional
def test__functional__ensure_seekable_input():
    r"""
    测试 ensure_seekable_input 可将不可 seek 流包装成可 seek 流。

    验证:
        - 返回流可 seek
        - 读取内容与原始输入一致

    Parameters:
        -
    """
    with ensure_seekable_input(_NonSeekableBinary(b'abc123')) as f:
        assert f.seekable() is True
        assert f.read() == b'abc123'
