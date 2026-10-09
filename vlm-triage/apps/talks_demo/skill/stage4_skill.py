"""Stage 4: Skill — 模型自主发现并执行 Skill。"""

from __future__ import annotations

import dataclasses as dc
import os
import subprocess
import time
import typing as tp
from pathlib import Path

import logfire
import streamlit as st
from pydantic_ai import Agent, RunContext

from _shared import DemoConfig, DEMO_QUESTIONS, get_model, render_message_log, run_async

PROJECT_ROOT: str = os.environ.get(
    'PROJECT_ROOT',
    str(Path(__file__).resolve().parents[2]),
)
SKILLS_DIR: str = os.path.join(PROJECT_ROOT, 'docs', 'skills')


@dc.dataclass
class SkillDeps:
    """Agent dependencies for Skill-based execution."""

    cooper_url: str
    project_root: str
    log: tp.Callable[[str], None]


def _build_skill_agent(config: DemoConfig) -> Agent[SkillDeps, str]:
    """Build a pydantic-ai Agent with skill discovery + shell execution."""
    agent = Agent(
        get_model(config),
        deps_type=SkillDeps,
        system_prompt=(
            '你是一个智能文档助手。当你需要读取外部文档时，请：\n'
            '1. 先用 list_skills 查看可用技能\n'
            '2. 用 read_skill 读取相关技能的说明文档\n'
            '3. 按文档中的步骤，用 run_command 逐步执行\n'
            '4. 基于获取的内容回答用户问题\n\n'
            '你有自主发现和学习新技能的能力。不要猜测，按 Skill 文档操作。'
        ),
    )

    @agent.tool
    async def list_skills(ctx: RunContext[SkillDeps]) -> str:
        """列出所有可用的 Skill 目录。

        返回 skills 目录下的子目录列表，每个子目录包含一个 SKILL.md。
        """
        ctx.deps.log('📂 发现技能目录...')
        skills_dir = os.path.join(ctx.deps.project_root, 'docs', 'skills')
        if not os.path.isdir(skills_dir):
            return f'技能目录不存在: {skills_dir}'

        entries: list[str] = []
        for name in sorted(os.listdir(skills_dir)):
            skill_path = os.path.join(skills_dir, name, 'SKILL.md')
            if os.path.isfile(skill_path):
                entries.append(name)

        ctx.deps.log(f'✅ 发现 {len(entries)} 个技能: {", ".join(entries)}')
        return '\n'.join(f'- {e}' for e in entries)

    @agent.tool
    async def read_skill(ctx: RunContext[SkillDeps], skill_name: str) -> str:
        """读取指定 Skill 的 SKILL.md 文档内容。

        Args:
            skill_name: 技能名称（对应 docs/skills/ 下的目录名）。
        """
        ctx.deps.log(f'📖 读取技能文档: {skill_name}')
        skill_path = os.path.join(
            ctx.deps.project_root,
            'docs',
            'skills',
            skill_name,
            'SKILL.md',
        )
        if not os.path.isfile(skill_path):
            return f'技能 {skill_name} 不存在（路径: {skill_path}）'

        content = Path(skill_path).read_text(encoding='utf-8')
        ctx.deps.log(f'✅ 技能文档读取成功，共 {len(content)} 字符')
        # 截断超长文档
        if len(content) > 15000:
            content = content[:15000] + '\n\n...(文档已截断)...'
        return content

    @agent.tool
    async def run_command(ctx: RunContext[SkillDeps], command: str) -> str:
        """在项目根目录下执行 shell 命令。

        用于按照 Skill 文档中的步骤执行操作，例如导出文档、转换格式等。
        命令在项目根目录下执行，可以使用 pixi run 等工具。

        Args:
            command: 要执行的 shell 命令。
        """
        ctx.deps.log(f'🔨 执行命令: `{command}`')

        # 注入 Cooper URL 变量
        env = os.environ.copy()
        env['COOPER_DOC_URL'] = ctx.deps.cooper_url

        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=ctx.deps.project_root,
                env=env,
            )
        except subprocess.TimeoutExpired:
            ctx.deps.log('⏰ 命令超时（60s）')
            return '命令执行超时（60 秒限制）'

        output = proc.stdout
        if proc.returncode != 0:
            ctx.deps.log(f'⚠️ 命令退出码: {proc.returncode}')
            output = (
                f'[exit code: {proc.returncode}]\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}'
            )
        else:
            ctx.deps.log(f'✅ 命令执行成功，输出 {len(output)} 字符')

        # 截断过长输出
        if len(output) > 30000:
            output = output[:30000] + '\n\n...(输出已截断)...'
        return output

    return agent


def render(config: DemoConfig):
    """Render Stage 4 demo page."""
    st.header('📜 Stage 4: Skill 系统')
    st.markdown(
        '> 模型**自主发现**可用技能 → 读取 SKILL.md → 按步骤执行。\n'
        '> 无需预定义工具，新能力只需添加一个 `.md` 文件。',
    )

    question = st.selectbox('选择问题', DEMO_QUESTIONS, key='s4_question')
    custom_q = st.text_input('或自定义问题', key='s4_custom', placeholder='输入你的问题...')
    if custom_q:
        question = custom_q

    full_prompt = f'{question}\n\n文档链接: {config.cooper_url}'

    # 展示 Skills 目录
    with st.expander('📂 可用 Skills', expanded=False):
        if os.path.isdir(SKILLS_DIR):
            for name in sorted(os.listdir(SKILLS_DIR)):
                skill_path = os.path.join(SKILLS_DIR, name, 'SKILL.md')
                if os.path.isfile(skill_path):
                    st.markdown(f'- `{name}/SKILL.md`')
        else:
            st.warning(f'Skills 目录不存在: {SKILLS_DIR}')

    if not st.button('🚀 发送', key='s4_run'):
        with st.expander('ℹ️ 原理说明', expanded=True):
            st.markdown(
                '**Skill 系统的三个通用工具**：\n\n'
                '| 工具 | 作用 |\n'
                '|:-----|:-----|\n'
                '| `list_skills` | 列出 `docs/skills/` 下所有技能目录 |\n'
                '| `read_skill` | 读取某个技能的 `SKILL.md` |\n'
                '| `run_command` | 按文档步骤执行 shell 命令 |\n\n'
                '**关键区别**：\n'
                '- Stage 2 的工具是**特定于 Cooper** 的（`read_cooper_document`）\n'
                '- Stage 4 的工具是**通用的**（list + read + execute）\n'
                '- Cooper 的知识存在 SKILL.md 中，不在代码中\n\n'
                '```\n'
                '新能力 = 新 SKILL.md 文件\n'
                '无需改代码，无需重新部署\n'
                '```',
            )
        return

    log_container = st.container()
    logs: list[str] = []

    def log_fn(msg: str):
        logs.append(msg)

    with st.status('正在执行 Skill Agent...', expanded=True) as status:
        st.write(f'📤 **Prompt**: {full_prompt[:200]}...')
        st.write(f'🤖 **Model**: `{config.model}`')
        st.write('🔧 **Tools**: `list_skills`, `read_skill`, `run_command`')
        st.write('📂 **Skills dir**: `docs/skills/`')

        agent = _build_skill_agent(config)
        deps = SkillDeps(
            cooper_url=config.cooper_url,
            project_root=PROJECT_ROOT,
            log=log_fn,
        )

        t0 = time.monotonic()
        try:
            result = run_async(agent.run(full_prompt, deps=deps))
            elapsed = time.monotonic() - t0
            status.update(label=f'✅ Skill Agent 完成 ({elapsed:.1f}s)', state='complete')
        except Exception as exc:
            logfire.error('stage4 failed', _exc_info=exc)
            status.update(label='❌ Skill Agent 执行失败', state='error')
            st.exception(exc)
            return

    with log_container:
        st.markdown('### 📋 执行日志')
        for i, msg in enumerate(logs):
            st.write(f'{i + 1}. {msg}')

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown('### 📝 模型输出')
        st.markdown(result.output)
    with col2:
        st.markdown('### ✅ 判定')
        st.success('🟢 **准确 + 自主**')
        st.markdown(
            '模型**自主发现**了\n'
            '`reading-cooper-documents`\n'
            '技能，读取 SKILL.md\n'
            '后按步骤执行。\n\n'
            '**无需预定义工具**。',
        )

    with st.expander('🔍 Skill 执行详情'):
        st.markdown(
            '**Agent 决策链**：\n\n'
            '1. `list_skills()` → 发现可用技能列表\n'
            '2. 识别 `reading-cooper-documents` 与任务相关\n'
            '3. `read_skill("reading-cooper-documents")` → 读取 SKILL.md\n'
            '4. 理解文档中的操作步骤\n'
            '5. `run_command("pixi run -e prod cooper-read <url>")` → 获取文档\n'
            '6. 基于真实内容回答用户问题\n\n'
            '**关键洞察**：\n'
            '- 三个工具（list/read/run）是**完全通用**的\n'
            '- Cooper 的知识存在 Markdown 文件中\n'
            '- 增加新能力 = 增加一个 SKILL.md\n'
            '- 任何模型（GPT、Claude、Qwen）都能使用同一套 Skills',
        )

    with st.expander('🌟 与 Stage 2 的对比'):
        st.markdown(
            '| | Stage 2 (Tool Call) | Stage 4 (Skill) |\n'
            '|:--|:--|:--|\n'
            '| 工具数量 | 1 个专用工具 | 3 个通用工具 |\n'
            '| 添加能力 | 改代码 + 部署 | 添加 .md 文件 |\n'
            '| 知识载体 | Python 代码 | 自然语言文档 |\n'
            '| 创建者 | 必须是开发者 | 可以是模型自己 |\n'
            '| 跨框架 | ❌ 绑定 pydantic-ai | ✅ 任何 Agent |\n'
            '| 跨模型 | ❌ 需迁移代码 | ✅ 复制文件即可 |',
        )

    render_message_log(result.all_messages(), key='s4')
