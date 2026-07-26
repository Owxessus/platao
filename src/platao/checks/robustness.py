"""Robustness & safety checks — "does it hold up, and is it safe?"

Three of the most universally-agreed defects in any codebase: an exception swallowed in silence
(the error that never surfaces until it's a production mystery), dynamic code execution
(``eval``/``exec``/``shell=True``) — an injection surface that is almost always avoidable — and a
mutable default argument that the function then mutates (state that silently leaks across every call).
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


# Methods that mutate the object they're called on (list/dict/set/deque).
_MUTATING_METHODS = frozenset({
    "append", "extend", "insert", "remove", "pop", "clear", "sort", "reverse",
    "add", "discard", "update", "setdefault", "popitem",
    "appendleft", "appendright", "extendleft", "popleft", "rotate",
})


def _mutable_default_kind(node: ast.expr) -> str | None:
    """Name the mutable default this expression is (``[]``/``{}``/``set()``/…), or ``None``."""
    if isinstance(node, ast.List):
        return "[]"
    if isinstance(node, ast.Dict):
        return "{}"
    if isinstance(node, ast.Set):
        return "set literal"
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in (
        "list", "dict", "set", "bytearray", "defaultdict", "OrderedDict", "deque", "Counter",
    ):
        return f"{node.func.id}()"
    return None


def _param_is_mutated(name: str, fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Does the function body mutate the parameter ``name`` in place?

    Looks for ``name.append(...)`` (and friends), ``name[...] = ...``, ``name += ...``, ``del
    name[...]``. This is the calibration that keeps false positives near zero: a mutable default that
    is only *read* is a smell, not the aliasing bug — we flag only when it is actually mutated.
    """
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            tgt = node.func.value
            if node.func.attr in _MUTATING_METHODS and isinstance(tgt, ast.Name) and tgt.id == name:
                return True
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) \
                        and target.value.id == name:
                    return True
        elif isinstance(node, ast.AugAssign):
            target = node.target
            if isinstance(target, ast.Name) and target.id == name:
                return True
            if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) \
                    and target.value.id == name:
                return True
        elif isinstance(node, ast.Delete):
            for target in node.targets:
                if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) \
                        and target.value.id == name:
                    return True
    return False


@register("mutable_default", "robustness", Severity.MEDIUM)
def mutable_default(ctx: FileContext) -> Iterable[tuple[int, str]]:
    """A parameter with a mutable default (``def f(x=[])``) that the body then mutates.

    The default is created *once*, at definition time, and shared by every call that relies on it —
    so a mutation on one call leaks into the next. The classic Python aliasing bug. We flag only when
    the parameter is actually mutated in place (``x.append``, ``x[k]=``, ``x +=``); a mutable default
    that is merely read is a smell, not this bug, so it stays quiet — that's what keeps this near
    zero false-positive.
    """
    for fn in ast.walk(ctx.tree):
        if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        args = fn.args
        positional = args.posonlyargs + args.args
        pairs: list[tuple[ast.arg, ast.expr]] = []
        if args.defaults:
            pairs.extend(zip(positional[len(positional) - len(args.defaults):], args.defaults,
                             strict=False))
        pairs.extend((a, d) for a, d in zip(args.kwonlyargs, args.kw_defaults, strict=False)
                     if d is not None)
        for param, default in pairs:
            kind = _mutable_default_kind(default)
            if kind is not None and _param_is_mutated(param.arg, fn):
                yield (
                    fn.lineno,
                    f"parameter '{param.arg}' has a mutable default ({kind}) that the body mutates — "
                    f"it is created once and shared across calls (state leaks between them)",
                )
