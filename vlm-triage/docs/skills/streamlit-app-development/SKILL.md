---
name: streamlit-app-development
description: 在 vlm-triage 项目中开发 Streamlit 可视化应用，包括快速搭建界面、会话状态管理、资源访问等。
---

# Streamlit App Development Skill

Act 类技能：在 vlm-triage 项目中开发 Streamlit 可视化应用。

## 何时使用

需要快速搭建可视化界面（展示图像/视频分析结果、交互调试、演示）时使用。

## 快速开始

```bash
pixi run serve-fe apps/<name>/main.py
```

应用统一放在 `apps/<name>/` 目录下。`serve-fe` 任务等价于 `streamlit run --server.headless true --server.port "$TRIAGE_FE_PORT"`。

## 应用目录结构

### 单页应用

```
apps/my_app/
└── main.py           # 入口 + 全部逻辑
```

### 多页应用（推荐）

```
apps/my_app/
├── main.py           # 入口：set_page_config + 页面路由
├── _shared.py        # 共享配置、缓存函数、工具函数
├── _page_foo.py      # 子页面 A
└── _page_bar.py      # 子页面 B
```

`main.py` 负责路由：

```python
from lib.utils.streamlit_utils import st_paramed_selectbox
from _page_foo import page_foo
from _page_bar import page_bar

_TASKS = ['🔍 任务 A', '🏷️ 任务 B']

def main():
    st.set_page_config(page_title='工具集', page_icon='🔍', layout='wide')
    with st.sidebar:
        task = st_paramed_selectbox('task', '🗂 任务', _TASKS)
    if task == _TASKS[0]:
        page_foo()
    else:
        page_bar()
```

`_shared.py` 放模块级单例和复用逻辑：

```python
api_client: httpx.Client = httpx.Client(base_url=API_BASE_URL, timeout=600.0)

@st.cache_data(ttl=3600, show_spinner=False)
def _cached_fetch(locator_id: int, config: MyConfig) -> MyResponse:
    resp = api_client.post('/endpoint', json=config.model_dump())
    resp.raise_for_status()
    return MyResponse.model_validate(resp.json())
```

## Shebang 模板

每个 `main.py` 使用 polyglot shebang 以支持直接执行：

```python
#!/bin/sh
''':'
exec pixi run -e prod -- serve-fe "$0" "$@"
# Streamlit 应用：简短描述
':'''
#!/usr/bin/env -S pixi run -e prod -- serve-fe

from __future__ import absolute_import, annotations

import os
NAME: str = os.environ.setdefault('OTEL_SERVICE_NAME', 'my-app-name')
```

`OTEL_SERVICE_NAME` 必须在 **任何 lib 模块 import 之前** 设置。

## URL Query Params 同步

使用 `st_paramed` 将控件值双向同步到 URL query params，实现可分享链接：

```python
from lib.utils.streamlit_utils import st_paramed, st_paramed_selectbox

# 字符串类型（默认 is_string_type=True）
locator_ids_str: str = st_paramed(
    'locator_ids', st.text_input, '输入 ID', value='4551391',
)

# 非字符串类型：json.loads/dumps 自动转换
max_windows = st_paramed(
    'max_windows', st.number_input, '最大窗口数',
    value=3, is_string_type=False, min_value=1,
)

# selectbox 专用封装
task = st_paramed_selectbox('task', '任务', ['A', 'B'])
```

## 从 Pydantic 模型自动生成表单

`st_config_fields` 根据模型字段类型自动渲染控件（int → number_input, bool → checkbox, tuple[int,int] → 两列 number_input），所有控件通过 `st_paramed` 持久化到 URL：

```python
from _shared import st_config_fields

main_cfg = st_config_fields(
    LocatorConfig,
    fields=['use_vlm_animation', 'max_windows', 'window_duration'],
)

with st.expander('高级参数'):
    advanced_cfg = st_config_fields(
        LocatorConfig,
        fields=['sample_wh', 'sample_xy'],
    )

config = LocatorConfig(**main_cfg, **advanced_cfg, return_images=True)
```

## HTTP 请求与缓存

### 模块级 httpx.Client

API 地址在进程生命周期内不变，使用模块级 `httpx.Client` 复用连接池：

```python
API_BASE_URL: str = os.getenv('MY_API_URL', 'http://localhost:8080')
api_client: httpx.Client = httpx.Client(base_url=API_BASE_URL, timeout=600.0)
```

### @st.cache_data + Pydantic frozen model

`LocatorConfig(frozen=True)` 是 hashable 的，可直接作为 `@st.cache_data` 参数——不需要先序列化为 JSON 字符串：

```python
@st.cache_data(ttl=3600, show_spinner=False)
def _cached_locate(locator_id: int, config: LocatorConfig) -> LocatorResponse:
    resp = api_client.post(
        '/locate',
        params={'locator_id': locator_id},
        json=config.model_dump(),
        timeout=300.0,  # 按需覆盖默认超时
    )
    resp.raise_for_status()
    data = LocatorResponse.model_validate(resp.json())
    if data.result is None:
        raise ValueError(f'No result: {data.message}')  # 异常不缓存
    return data
```

!!! warning "抛异常 = 不缓存"
    `@st.cache_data` 只缓存正常返回值。对"还没准备好"的结果（如 pending 状态），抛出异常可防止缓存无效数据。

### 请求体

使用 `json=config.model_dump()` 发送请求体。**不要** 用 `content=config.model_dump_json()`，后者会丢失 Content-Type header。

## 按钮状态管理

Streamlit 按钮点击后下次 rerun 不保留状态。用 `st.session_state` 保持"已点击"状态：

```python
run_button = st.button('🚀 运行', type='primary')

if run_button:
    st.session_state['ran'] = True

if not st.session_state.get('ran'):
    st.info('👈 请点击运行')
    return

# 下面是运行后的渲染逻辑
```

## 多 ID 分 Tab 展示

```python
locator_ids = _parse_locator_ids(ids_str)

if len(locator_ids) == 1:
    _run(locator_ids[0], config)
else:
    tabs = st.tabs([str(lid) for lid in locator_ids])
    for tab, lid in zip(tabs, locator_ids, strict=True):
        with tab:
            _run(lid, config)
```

## 图片网格渲染

标准模式：按维度分组 → tabs → rows × columns。

```python
def render_image_grid(images: list[SampleImageInfo]):
    # 1. group by window_index
    by_window: dict[str, list[SampleImageInfo]] = {}
    for img in images:
        by_window.setdefault(img.window_index, []).append(img)

    # 2. 每个 window 一个 tab
    sorted_windows = sorted(by_window.items(), key=lambda kv: kv[0])
    tabs = st.tabs([items[0].window_desc for _, items in sorted_windows])

    for tab, (_win_idx, cells) in zip(tabs, sorted_windows, strict=True):
        with tab:
            # 3. 行 = unique (cr_index, cr_desc)，按自定义排序
            rows = sorted(
                {(c.cr_index, c.cr_desc) for c in cells},
                key=lambda r: _row_sort_key(r[0]),
            )
            sample_indices = sorted({c.sample_index for c in cells})

            # 4. 预建 lookup map，避免嵌套循环
            url_map = {(c.cr_index, c.sample_index): c.image_url for c in cells}

            # 5. 行 × 列渲染
            for cr_index, cr_desc in rows:
                st.markdown(f'**{ROW_LABEL_MAP.get(cr_index, f"CR {cr_index}")}** — `{cr_desc}`')
                cols = st.columns(len(sample_indices))
                for ci, samp_idx in enumerate(sample_indices):
                    with cols[ci]:
                        img_url = url_map.get((cr_index, samp_idx))
                        if img_url:
                            st.image(img_url, use_container_width=True)
```

## 标注存储

标注文件使用确定性路径，无随机数，存储在 S3 挂载盘 `DATA_DIR`：

```python
DATA_DIR: Path = Path(os.environ['TRIAGE_DATA_DIR'])

def _annotation_path(locator_id: int, scenario_id: str, config: LocatorConfig) -> Path:
    partition = dt.date.today().strftime('%Y%m%d')
    h = hashlib.md5(config.model_dump_json().encode()).hexdigest()[:12]
    return DATA_DIR / NAME / partition / f'locator_id={locator_id}-scenario_id={scenario_id}.{h}.json'
```

保存时将 Pydantic model 元数据一并写入，方便离线分析：

```python
def save_annotations(locator_id, scenario_id, config, annotations, *, info, cells):
    data = {'locator_id': locator_id, 'scenario_id': scenario_id}
    data['base_task_id'] = info.base_task_id   # 直接取，不判空
    data['diff_type'] = info.diff_type
    # ... 遍历 annotations 构建 ann_list
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
```

## st_report 反馈按钮

在侧边栏添加一个 Report 弹窗按钮，方便用户提交反馈：

```python
from lib.utils.streamlit_utils import st_report

with st.sidebar:
    if st.button('📝 Report'):
        st_report(
            {'locator_id': lid, 'locator_url': url, 'config': config.model_dump()},
            type_options=('Error', 'Badcase', 'Goodcase'),
        )
```

## Sticky Tabs CSS

让外层 tabs 在页面滚动时固定在顶部：

```python
_STICKY_TABS_CSS = """
<style>
[data-testid="stTabs"] > div:first-child > div:first-child {
    position: sticky;
    top: 3.5rem;
    z-index: 999;
}
[data-testid="stTabs"] [data-testid="stTabs"] > div:first-child > div:first-child {
    top: 6.3rem;
}
</style>
"""

st.markdown(_STICKY_TABS_CSS, unsafe_allow_html=True)
```

## 类型使用规范

### HttpUrlStr 是 str

`lib.utils.pydantic_compat.HttpUrlStr` 在运行时就是 `str`。不要用 `str()` 包装：

```python
# ✅ 正确
st.image(cell.image_url, use_container_width=True)
st.link_button('下载', url)
data['locator_url'] = info.locator_url

# ❌ 多余
st.image(str(cell.image_url))
st.link_button('下载', str(url))
data['locator_url'] = str(info.locator_url)
```

### 不要对非 Optional 字段判空

Pydantic model 的必填字段永远不为 None。不需要 `if model:` 或 `if field:` 的防御性判断：

```python
# ✅ 直接使用
data['base_task_id'] = info.base_task_id
data['diff_type'] = info.diff_type

# ❌ 多余判空（info: AnnotationInfo 是必填参数，不可能为 None）
if info:
    data['base_task_id'] = info.base_task_id

# ✅ Optional 字段才需要判空
if result.images:     # images: Optional[list[SampleImageInfo]]
    render_image_grid(result.images)
```

### dict 初始化风格

```python
# ✅
ann_state: dict[str, str] = {}
result: dict[str, str] = {}

# ❌ 虽然合法但不清晰
ann_state = dict[str, str]()
```

## DO / DON'T

**DO**

- 用 `st_paramed` 同步控件值到 URL query params
- 用 `@st.cache_data` + frozen Pydantic model 缓存 API 请求
- 用模块级 `httpx.Client` 复用连接池
- 用 `st.session_state` 保持按钮点击状态
- 用 `st.spinner` 处理耗时操作
- 用 `st.container(border=True)` 分隔逻辑卡片
- 先构建 lookup map 再渲染网格（避免 O(n²) 嵌套遍历）

**DON'T**

- 不在 pixi 环境外直接运行（`streamlit run` 要通过 `pixi run`）
- 不在顶层直接调用耗时操作（用 `@st.cache_data` 或懒加载）
- 不对 `HttpUrlStr` 用 `str()` 包装
- 不对非 Optional 的 Pydantic 字段做判空
- 不用 `content=json_str` 发 HTTP 请求（用 `json=dict`）
- 不把 `httpx.Client` 作为 `@st.cache_data` 函数参数传递（不可 hash）

## 参考实现

| 应用 | 路径 | 特点 |
|------|------|------|
| CR Locator 工具集 | `apps/visual_cr_locator_fe/` | 多页路由、`_shared.py`、`st_config_fields`、图片网格 |
| Aurora 场景标注 | `apps/aurora_scenario_labeling/` | 资源访问、session_context 模式 |

## See Also

- `lib/utils/streamlit_utils.py` — `st_paramed`、`st_paramed_selectbox`、`st_report`
- `lib/utils/pydantic_compat.py` — `HttpUrlStr` 类型定义
- `pyproject.toml` 中 `serve-fe` 任务定义
