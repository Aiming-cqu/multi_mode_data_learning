r"""
Pydantic v1/v2 compatibility types.

Provides ``HttpUrlStr`` — a validated HTTP URL type that is a ``str`` at runtime.
In Pydantic v2, ``HttpUrl`` is **not** a ``str`` subclass, which breaks downstream
code expecting plain strings. ``HttpUrlStr`` uses ``BeforeValidator`` to validate
via ``HttpUrl`` then coerce back to ``str``, so static type checkers see ``str``.
In Pydantic v1, ``HttpUrl`` already inherits from ``str``, so ``HttpUrlStr`` is
simply an alias.
"""

from __future__ import absolute_import, annotations

import typing as tp

if tp.TYPE_CHECKING:
    HttpUrlStr: tp.TypeAlias = str
else:
    from pydantic import HttpUrl

    try:
        from pydantic import BeforeValidator, TypeAdapter

        _http_url_ta = TypeAdapter(HttpUrl)

        def _validate_http_url(v: tp.Any) -> str:
            return str(_http_url_ta.validate_python(v))

        HttpUrlStr: tp.TypeAlias = tp.Annotated[str, BeforeValidator(_validate_http_url)]
    except ImportError:
        HttpUrlStr: tp.TypeAlias = HttpUrl  # pydantic v1: HttpUrl is str
