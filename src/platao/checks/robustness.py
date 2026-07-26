"""Robustness & safety checks — "does it hold up, and is it safe?"

Two of the most universally-agreed defects in any codebase: an exception swallowed in silence
(the error that never surfaces until it's a production mystery), and dynamic code execution
(``eval``/``exec``/``shell=True``) — an injection surface that is almost always avoidable.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable

from platao.checks import register
from platao.checks._ast import catches_interrupts, except_name, is_broad_except, is_ellipsis
from platao.context import FileContext
from platao.finding import Severity


@register("swallowed_error", "robustness", Severity.MEDIUM)
def swallowed_error(ctx: FileContext) -> Iterable[tuple[int, str] | tuple[int, str, Severity]]:
    """A *broad* ``except`` whose entire body is ``pass`` (or ``...``) — the error vanishes silently.

    We flag only the catch-all shape and split it by real danger:

    * **HIGH** — a bare ``except:`` or ``except BaseException:``. These swallow ``SystemExit`` and
      ``KeyboardInterrupt`` too, so a silent ``pass`` quietly breaks Ctrl-C and ``sys.exit()`` — a bug.
    * **MEDIUM** — ``except Exception: pass``. A real smell (an error dropped with no log or re-raise),
      but a widely-accepted best-effort idiom in mature code, so it's advisory rather than a hard fail.

    A *narrow*, specific catch (``except StopIteration: pass``, ``except (ImportError, AttributeError):
    pass``) is the deliberate "I expect this exact thing and it's fine" idiom — flagging it would cry
    wolf, so we leave it alone. ``except X: return default`` and ``except X: logger.exception`` are
    handled, not swallowed, and never matched.
    """
    for node in ast.walk(ctx.tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        body = node.body
        if not (len(body) == 1 and (isinstance(body[0], ast.Pass) or is_ellipsis(body[0]))):
            continue
        if not is_broad_except(node):
            continue  # narrow specific catch — an intentional idiom, not a dropped error
        if catches_interrupts(node):
            yield (
                node.lineno,
                f"{except_name(node)} swallows every error — including SystemExit/KeyboardInterrupt "
                f"(Ctrl-C) — with no log or re-raise",
                Severity.HIGH,
            )
        else:
            yield (
                node.lineno,
                f"{except_name(node)} swallows the error silently (body is just `pass`) — "
                f"no log, no re-raise",
                Severity.MEDIUM,
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
