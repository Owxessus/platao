"""Robustness & safety checks — "does it hold up, and is it safe?"

Two of the most universally-agreed defects in any codebase: an exception swallowed in silence
(the error that never surfaces until it's a production mystery), and dynamic code execution
(``eval``/``exec``/``shell=True``) — an injection surface that is almost always avoidable.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable

from platao.checks import register
from platao.checks._ast import except_name, is_ellipsis
from platao.context import FileContext
from platao.finding import Severity


@register("swallowed_error", "robustness", Severity.HIGH)
def swallowed_error(ctx: FileContext) -> Iterable[tuple[int, str]]:
    """An ``except`` whose entire body is ``pass`` (or ``...``) — the error vanishes with no trace.

    We flag only the truly-empty handler. ``except X: return default`` is a choice; ``except X:
    logger.exception(...)`` is handled; ``except X: pass`` is an error dropped on the floor, and
    the single hardest failure to diagnose later.
    """
    for node in ast.walk(ctx.tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        body = node.body
        if len(body) == 1 and (isinstance(body[0], ast.Pass) or is_ellipsis(body[0])):
            yield (
                node.lineno,
                f"{except_name(node)} swallows the error silently (body is just `pass`) — "
                f"no log, no re-raise",
            )


@register("dangerous_dynamic", "security", Severity.HIGH)
def dangerous_dynamic(ctx: FileContext) -> Iterable[tuple[int, str]]:
    """Dynamic execution: ``eval()``, ``exec()``, ``os.system()``, or a call with ``shell=True``.

    ``ast.literal_eval`` is safe and not matched (it's an attribute, not the ``eval`` builtin). Each
    call is reported once, with the most specific reason.
    """
    for node in ast.walk(ctx.tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in ("eval", "exec"):
            yield (node.lineno, f"dynamic code execution via `{func.id}()`")
            continue
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "system"
            and isinstance(func.value, ast.Name)
            and func.value.id == "os"
        ):
            yield (node.lineno, "shell execution via `os.system()`")
            continue
        for kw in node.keywords:
            if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                yield (node.lineno, "subprocess call with `shell=True` — a shell-injection surface")
                break
