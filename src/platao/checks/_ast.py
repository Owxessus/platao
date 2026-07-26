"""Small, pure AST helpers shared by the checks. No I/O, trivially unit-testable.

Every function here answers one narrow structural question about a node, so the checks read like
prose and the tricky predicates live in one place with one owner.
"""

from __future__ import annotations

import ast

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef

# Verbs whose presence in a function name promises a side effect. A function named `execute` /
# `save` / `deploy` that does nothing is a placebo; a function named `parse` that returns a value
# is not, so we only cross-examine the ones that claim to *act*.
ACTION_VERBS = frozenset({
    "execute", "run", "apply", "perform", "dispatch", "commit", "process", "handle",
    "launch", "trigger", "remediate", "repair", "mutate", "act", "send", "deliver",
    "provision", "deploy", "save", "delete", "sync", "publish", "heal", "cure",
    "fix", "patch", "rollback", "upload", "submit", "flush", "persist",
})

# Names that ANNOUNCE they don't do work — honest, not placebo. A `noop` is telling the truth.
HONEST_STUB_MARKERS = ("noop", "no_op", "stub", "fake", "dummy", "mock", "spy", "placeholder", "_null")

# Strings that stand in for "it worked" when returned or compared against.
SUCCESS_WORDS = frozenset({
    "success", "ok", "done", "completed", "complete", "executed", "passed",
    "approved", "valid", "allow", "allowed", "green", "finished", "succeeded",
})
FAILURE_WORDS = frozenset({
    "failed", "failure", "error", "denied", "blocked", "deny", "partial", "invalid", "rejected",
})

# Attributes that hold a self-reported outcome (the thing a placebo test asserts on).
SUCCESS_ATTRS = frozenset({"success", "passed", "ok", "succeeded", "is_success", "valid", "successful"})
STATUS_ATTRS = frozenset({"status", "state", "result", "outcome", "decision", "verdict"})


def name_tokens(name: str) -> list[str]:
    """``run_the_job`` -> ``['run', 'the', 'job']`` (underscores and dunders split)."""
    return [t for t in name.lower().replace("__", "_").split("_") if t]


def is_action_name(name: str) -> bool:
    """Does this function name promise a side effect?"""
    return any(tok in ACTION_VERBS for tok in name_tokens(name))


def has_honest_stub_name(name: str) -> bool:
    """Is the function openly named as a non-doer (noop/stub/fake/…)?"""
    low = name.lower()
    return any(marker in low for marker in HONEST_STUB_MARKERS)


def body_without_docstring(node: FunctionNode) -> list[ast.stmt]:
    """The function body with a leading docstring stripped (so a docstring-only body reads as empty)."""
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        return body[1:]
    return body


def is_ellipsis(stmt: ast.stmt) -> bool:
    """``...`` on its own — the honest "declared, not implemented here" idiom."""
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and stmt.value.value is Ellipsis
    )


def is_notimplemented(stmt: ast.stmt) -> bool:
    """``raise NotImplementedError`` (with or without a message) — honest, not placebo."""
    if not isinstance(stmt, ast.Raise) or stmt.exc is None:
        return False
    exc = stmt.exc.func if isinstance(stmt.exc, ast.Call) else stmt.exc
    return isinstance(exc, ast.Name) and exc.id == "NotImplementedError"


def is_success_literal(node: ast.expr) -> bool:
    """Does this expression mean "it worked"? (``True``, a success string, or ``{'status': 'ok'}``.)"""
    if isinstance(node, ast.Constant):
        if node.value is True:
            return True
        if isinstance(node.value, str) and node.value.lower() in SUCCESS_WORDS:
            return True
    if isinstance(node, ast.Dict):
        for key, value in zip(node.keys, node.values, strict=True):
            if (
                isinstance(key, ast.Constant)
                and str(key.value).lower() in STATUS_ATTRS
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
                and value.value.lower() in SUCCESS_WORDS
            ):
                return True
    return False


def is_failure_literal(node: ast.expr) -> bool:
    """Does this expression signal failure? (``False`` / ``None`` / an error string.)"""
    if isinstance(node, ast.Constant):
        if node.value is False or node.value is None:
            return True
        if isinstance(node.value, str) and node.value.lower() in FAILURE_WORDS:
            return True
    return False


def has_decorator(node: FunctionNode, names: tuple[str, ...]) -> bool:
    """Is the function decorated with any of ``names`` (matched on the final dotted segment)?"""
    for dec in node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Name) and target.id in names:
            return True
        if isinstance(target, ast.Attribute) and target.attr in names:
            return True
    return False


def dotted_name(node: ast.expr) -> str:
    """``os.path.join`` from an Attribute/Name chain; ``""`` if it isn't a plain dotted name."""
    parts: list[str] = []
    cur: ast.expr | None = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return ""


def except_name(handler: ast.ExceptHandler) -> str:
    """A readable name for what an ``except`` clause catches (``"bare except"`` if it catches all)."""
    if handler.type is None:
        return "bare except"
    if isinstance(handler.type, ast.Tuple):
        names = [dotted_name(e) or "?" for e in handler.type.elts]
        return "except (" + ", ".join(names) + ")"
    return "except " + (dotted_name(handler.type) or "?")


# The catch-alls: a handler on one of these swallows *everything*, including the bugs you never
# meant to hide. A handler on a specific exception (`except KeyError`, `except (ImportError,
# AttributeError)`) is a deliberate "I expect this one and it's fine" — the dominant idiom in mature
# code (optional imports, feature detection, generator exhaustion), and flagging it cries wolf.
_BROAD_EXCEPTIONS = frozenset({"Exception", "BaseException"})


def is_broad_except(handler: ast.ExceptHandler) -> bool:
    """Does this ``except`` catch *everything* — bare, or ``Exception``/``BaseException``?

    Broad catches are where a silent ``pass`` is genuinely dangerous (a real bug vanishes with no
    trace). Narrow, specific catches are almost always an intentional "expected, ignore it", so we
    don't treat them as defects.
    """
    if handler.type is None:
        return True
    elts = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return any(dotted_name(e).rsplit(".", 1)[-1] in _BROAD_EXCEPTIONS for e in elts)


def catches_interrupts(handler: ast.ExceptHandler) -> bool:
    """Does this catch-all also swallow ``SystemExit`` / ``KeyboardInterrupt``?

    A bare ``except:`` or ``except BaseException:`` eats the interrupt signals too — swallowing one
    silently means Ctrl-C and ``sys.exit()`` stop working, a genuine bug. ``except Exception:`` does
    *not* catch those (they derive from ``BaseException``, not ``Exception``), so a silent pass there
    is a smell but not dangerous — worth a lower severity.
    """
    if handler.type is None:
        return True
    elts = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return any(dotted_name(e).rsplit(".", 1)[-1] == "BaseException" for e in elts)
