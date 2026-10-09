"""Cooper MCP Server — 提供 cooper_read 工具供 MCP 客户端调用。

Usage:
    python -m apps.skill_demo.cooper_mcp_server

This server exposes Cooper document reading as an MCP tool,
enabling any MCP-compatible Agent to discover and use it dynamically.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
_project_root = str(Path(__file__).resolve().parents[2])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


async def _cooper_read(url: str) -> str:
    """Export + normalize + convert a Cooper document to Markdown."""
    proc = await asyncio.create_subprocess_exec(
        'pixi',
        'run',
        '--as-is',
        'cooper-read',
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=_project_root,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        msg = stderr.decode()
        return f'Error: cooper-read failed (exit {proc.returncode}): {msg}'
    return stdout.decode('utf-8')


def main():
    """Run the Cooper MCP Server via stdio."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        print(
            'Error: mcp package not installed. Install with: pixi add --pypi mcp --feature prod',
            file=sys.stderr,
        )
        sys.exit(1)

    server = FastMCP(
        'Cooper Document Server',
        instructions=(
            '提供 Cooper 协作文档的读取能力。可以导出、转换并返回 Cooper 文档的 Markdown 内容。'
        ),
    )

    @server.tool()
    async def cooper_read(url: str) -> str:
        """读取 Cooper 协作文档，返回 Markdown 内容。

        将 Cooper 文档导出为 DOCX，归一化样式后转换为 Markdown。

        Args:
            url: Cooper 文档 URL，格式如
                 https://cooper.didichuxing.com/docs2/document/{resource_id}
        """
        return await _cooper_read(url)

    server.run(transport='stdio')


if __name__ == '__main__':
    main()
