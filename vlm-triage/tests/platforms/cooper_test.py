#!/bin/sh
""":"
exec pixi run -- test -s "$0" "$@"
"""
#!/usr/bin/env -S pixi run -- test -s

from __future__ import absolute_import, annotations

import pytest

import io, typing as tp, zipfile

from pathlib import Path

from lib.platforms.ep.cooper import (
    CooperClient,
    get_team_file_url,
    normalize_docx_file,
    normalize_styles_xml,
)
from lib.platforms.ep.cooper_types import FileInfo
from lib.utils.io_utils import copy_to

from tests.common import TEST_DATA_DIR


# Real Cooper folder used by the team
# https://cooper.didichuxing.com/team-file/2199094698523/2207369729546
GROUP_ID = 2199094698523
PARENT_ID = 2207369729546
COOPERATE_DOC_ID = 2207460511730


FILE_PATHS = [
    'cr_locator/images/01/base-no-collision.png',
    'cr_locator/images/01/cr-collision.png',
    'cr_locator/releases/0313-collision.tsv',
]


async def iter_bytes(chunks: list[bytes]) -> tp.AsyncIterator[bytes]:
    r"""
    Yield byte chunks for Cooper stream helper tests.

    Args:
        chunks: Byte chunks to yield in order.

    Parameters:
        -
    """
    for chunk in chunks:
        yield chunk


# ---------------------------------------------------------------------------
# upload_file
# ---------------------------------------------------------------------------


@pytest.mark.parametrize('file_path', FILE_PATHS)
@pytest.mark.parametrize(
    'case',
    [
        pytest.param("file-object", id="file-object"),
        pytest.param("explicit-naming", id="explicit-naming"),
        pytest.param("bytes", id="bytes"),
    ],
)
async def test_upload_file(case: str, file_path: str):
    r"""
    集成测试：以不同方式单文件上传到 Cooper，验证返回结果正确。

    前置条件:
        - 环境变量 COOPER_USERNAME 已设置（os.environ["COOPER_USERNAME"]）
        - 可访问内网 Cooper API

    验证:
        - 返回非空 FileInfo 列表
        - 每个条目都有 id

    Parameters:
        case: 上传方式；"file-object" 裸文件对象、"explicit-naming" 自定义文件名、
            "bytes" 内存字节流。
        file_path: 相对于 tests/data 的文件路径。
    """

    client = CooperClient()
    file_path_ = TEST_DATA_DIR / file_path

    match case:
        case "file-object":
            with file_path_.open("rb") as f:
                res = await client.upload_file(GROUP_ID, PARENT_ID, f)

        case "explicit-naming":
            with file_path_.open("rb") as f:
                res = await client.upload_file(
                    GROUP_ID, PARENT_ID, (file_path_.stem + '.renamed' + file_path_.suffix, f)
                )

        case "bytes":
            data = file_path_.read_bytes()
            res = await client.upload_file(
                GROUP_ID, PARENT_ID, (file_path_.stem + '.bytes' + file_path_.suffix, data)
            )

        case _:
            raise ValueError(f'Unknown case: {case}')

    assert isinstance(res, FileInfo)
    assert res.id

    print(f'HIL: checked upload_file {case=} {file_path=} -> {res=}')
    print(f'HIL: checked in dir: {get_team_file_url(GROUP_ID, PARENT_ID)}')


# ---------------------------------------------------------------------------
# export_cooperate
# ---------------------------------------------------------------------------


async def test_export_cooperate(tmp_path: Path):
    r"""
    集成测试：导出 Cooper 协作文档为 Office 格式文件流。

    前置条件:
        - 环境变量 COOPER_USERNAME 已设置（os.environ["COOPER_USERNAME"]）
        - 可访问内网 Cooper API
        - COOPERATE_DOC_ID 指向真实的 Cooper 在线文档（Word）

    验证:
        - 返回的文件路径存在
        - 文件大小 > 0
        - 文件内容以 PK 开头（OOXML / ZIP 格式签名，docx/xlsx 均适用）
    """

    client = CooperClient()
    file_path = tmp_path / 'exported.docx'
    await client.export(COOPERATE_DOC_ID, file_path)
    assert file_path.exists()
    assert file_path.stat().st_size > 0

    header = file_path.read_bytes()[:2]
    assert header == b'PK', f'Expected OOXML (PK) header, got {header!r}'

    print(
        f'HIL: checked export_cooperate cooperate_doc_id={COOPERATE_DOC_ID}'
        f' -> {file_path} ({file_path.stat().st_size} bytes)',
    )


async def test_download_to_output_stdout(monkeypatch: pytest.MonkeyPatch):
    r"""
    单元测试：download_to_output 支持将字节流写到 stdout。

    验证:
        - output path 为 `'-'` 时写入 `sys.stdout.buffer`
        - 输出内容按 chunk 顺序拼接

    Parameters:
        monkeypatch: pytest monkeypatch fixture.
    """

    class StdoutStub:
        def __init__(self):
            self.buffer = io.BytesIO()

        def flush(self):
            self.buffer.flush()

    stdout_stub = StdoutStub()
    monkeypatch.setattr('sys.stdout', stdout_stub)

    await copy_to(iter_bytes([b'PK', b'\x03\x04']), '-')

    assert stdout_stub.buffer.getvalue() == b'PK\x03\x04'


def test_normalize_styles_xml():
    r"""
    单元测试：normalize_styles_xml 为缺失 `w:type` 的样式补默认值。

    验证:
        - 仅补齐缺失 `w:type` 的 `<w:style>`
        - 已存在的 `w:type` 保持不变

    Parameters:
        -
    """

    styles_xml = (
        '<w:styles>'
        '<w:style w:styleId="shimo normal" w:customStyle="1"></w:style>'
        '<w:style w:type="character" w:styleId="Emphasis"></w:style>'
        '</w:styles>'
    )

    normalized_styles_xml, patched_count = normalize_styles_xml(styles_xml)

    assert patched_count == 1
    assert 'w:styleId="shimo normal" w:customStyle="1" w:type="paragraph"' in normalized_styles_xml
    assert normalized_styles_xml.count('w:type="character"') == 1


def test_normalize_docx_file():
    r"""
    单元测试：normalize_docx_file 只修改 styles.xml 并保留其他 DOCX 内容。

    验证:
        - 返回的 DOCX 可重新读取
        - `word/styles.xml` 中缺失的 `w:type` 被补齐
        - 其他 ZIP entry 内容保持不变

    Parameters:
        -
    """

    input_io = io.BytesIO()
    with zipfile.ZipFile(input_io, mode='w') as input_zip:
        input_zip.writestr('[Content_Types].xml', '<Types/>')
        input_zip.writestr(
            'word/styles.xml',
            '<w:styles><w:style w:styleId="shimo normal"></w:style></w:styles>',
        )
        input_zip.writestr('word/document.xml', '<w:document/>')

    output_io = io.BytesIO()
    patched_count = normalize_docx_file(input_io, output_io)

    with zipfile.ZipFile(output_io) as output_zip:
        styles_xml = output_zip.read('word/styles.xml').decode()
        document_xml = output_zip.read('word/document.xml').decode()

    assert patched_count == 1
    assert 'w:type="paragraph"' in styles_xml
    assert document_xml == '<w:document/>'
