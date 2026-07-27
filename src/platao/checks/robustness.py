"""Robustness & safety checks — "does it hold up, and is it safe?"

Three of the most universally-agreed defects in any codebase: an exception swallowed in silence
(the error that never surfaces until it's a production mystery), dynamic code execution
(``eval``/``exec``/``shell=True``) — an injection surface that is almost always avoidable — and a
mutable default argument that the function then mutates (state that silently leaks across every call).
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable

from platao.checks import register
from platao.checks._ast import (
    catches_interrupts,
    except_name,
    is_broad_except,
    is_ellipsis,
    is_success_literal,
)
from platao.context import FileContext
from platao.finding import Finding, Severity
from platao.patterns import MIN_SECRET_LEN, PLACEHOLDER, SECRET_NAME

# A function whose name says it makes a security / validation / access decision. Only these are held
# to "fail closed" — the name is the proxy for "this is a gate", which keeps `fail_closed` from firing
# on ordinary functions that happen to return True in an except. Matched by TOKEN (snake_case /
# camelCase split), so `is_authorized` and `checkPermission` match while `get_author` / `checkout` —
# which merely share a prefix — do not.
_GUARD_TOKENS = frozenset({
    "auth", "authorize", "authorized", "authenticate", "authenticated", "authorization",
    "valid", "validate", "allow", "allowed", "permit", "permitted", "permission",
    "access", "grant", "granted", "eligible", "verify", "verified", "guard", "login", "credential",
})
_GUARD_PREFIXES = ("authoriz", "authenticat", "valid", "permit", "permiss", "allow",
                   "access", "grant", "eligib", "verif", "guard", "credential")


def _is_guard_name(name: str) -> bool:
    """Does the function name read as an access/validation decision (token-wise)?"""
    for token in re.findall(r"[A-Za-z][a-z]*", name):
        low = token.lower()
        if low in _GUARD_TOKENS or any(low.startswith(p) for p in _GUARD_PREFIXES):
            return True
    return False


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


@register("fail_closed", "security", Severity.HIGH)
def fail_closed(ctx: FileContext) -> Iterable[tuple[int, str]]:
    """A guard/auth/validation function that fails OPEN — a broad ``except`` returns a permissive value.

    The dangerous shape: ``def is_authorized(...): try: ...  except Exception: return True``. When the
    real check errors, the function grants access instead of denying it — a security decision that
    defaults to "yes" on failure. A gate must fail *closed* (deny/raise on error), never open.

    Held only to functions whose name says they make an access/validation decision (``is_authorized``,
    ``validate_token``, ``check_permission``) — an ordinary function returning ``True`` in an ``except``
    is not a gate. And only when the caught type is broad and the handler returns a success/permissive
    literal (``True`` / ``"allow"`` / ``{"status": "ok"}``); a narrow catch or a ``return False`` /
    ``raise`` is failing closed, and stays silent.
    """
    for fn in ast.walk(ctx.tree):
        if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if not _is_guard_name(fn.name):
            continue
        for handler in ast.walk(fn):
            if not isinstance(handler, ast.ExceptHandler) or not is_broad_except(handler):
                continue
            for stmt in ast.walk(handler):
                if isinstance(stmt, ast.Return) and stmt.value is not None \
                        and is_success_literal(stmt.value):
                    yield (
                        handler.lineno,
                        f"guard '{fn.name}' fails OPEN — a broad {except_name(handler)} returns a "
                        f"success/permissive value, so an error is treated as a pass instead of a "
                        f"failure (a gate must deny or raise on error)",
                    )
                    break


@register("hardcoded_secret", "security", Severity.HIGH)
def hardcoded_secret(ctx: FileContext) -> Iterable[Finding]:
    """A secret-named variable assigned a string literal — a key/token/password baked into source.

    Flags ``API_KEY = "…"`` / ``token: str = "…"`` where the name reads as a credential and the value
    is a real-length string. The correct pattern — ``API_KEY = os.environ["API_KEY"]`` — has a
    non-literal value and is never matched. The secret's value is **never** put in the message or the
    snippet (the snippet is redacted to the name). A placeholder value (``test``/``example``/``<...>``)
    downgrades to MEDIUM — likely a fixture — rather than being silenced.
    """
    for node in ast.walk(ctx.tree):
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names, value = [node.target.id], node.value
        else:
            continue
        if not (isinstance(value, ast.Constant) and isinstance(value.value, str)):
            continue
        if len(value.value) < MIN_SECRET_LEN:
            continue
        for name in names:
            if not SECRET_NAME.search(name):
                continue
            placeholder = bool(PLACEHOLDER.search(value.value))
            severity = Severity.MEDIUM if placeholder else Severity.HIGH
            hint = " (looks like a placeholder/fixture)" if placeholder else ""
            yield Finding(
                "hardcoded_secret", "security", severity, ctx.path, node.lineno,
                f"'{name}' is assigned a hardcoded secret{hint} — move it to config/env, never in source",
                f"{name} = <redacted>",
            )


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
