"""Anti-placebo checks — "is this real, or does it just look done?"

These are Platão's flagship: the ways work claims to be finished without being finished. A function
that announces an action and does nothing; a pipeline structurally unable to fail; a test that
asserts on the code's own report of itself instead of an independent oracle; a test suite that never
exercises a failure. Each is high-signal and low false-positive by construction — we only cross-
examine functions that *promise* to act, and only flag tests that assert on a self-report.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable

from platao.checks import register
from platao.checks._ast import (
    STATUS_ATTRS,
    SUCCESS_ATTRS,
    SUCCESS_WORDS,
    body_without_docstring,
    has_decorator,
    has_honest_stub_name,
    is_action_name,
    is_ellipsis,
    is_failure_literal,
    is_notimplemented,
    is_success_literal,
)
from platao.context import FileContext
from platao.finding import Severity


def _functions(tree: ast.AST) -> Iterable[ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            yield node


def _is_literalish(node: ast.expr) -> bool:
    """A literal value the test wrote itself (constant or a container literal) — not a call/name.

    ``d[k] = 5`` / ``d[k] = [1, 2]`` is the test's own setup; ``d[k] = compute()`` stores the SUT's
    output, which is a real thing to assert on. Only the former makes an assert a self-report.
    """
    return isinstance(node, ast.Constant | ast.List | ast.Dict | ast.Tuple | ast.Set)


@register("not_stub", "placebo", Severity.HIGH)
def not_stub(ctx: FileContext) -> Iterable[tuple[int, str]]:
    """An action-named function whose body does nothing — the archetypal placebo.

    Honest non-doers are exempt: ``...`` and ``raise NotImplementedError`` say "not implemented
    here", and names like ``noop``/``stub``/``fake`` announce it. What we flag is the function that
    *claims* to act and quietly doesn't: ``pass``, a bare ``return``, or ``return True``.
    """
    for fn in _functions(ctx.tree):
        if not is_action_name(fn.name) or has_honest_stub_name(fn.name):
            continue
        if has_decorator(fn, ("abstractmethod", "overload", "override", "overrides")):
            continue  # abstract / typed-overload / explicit override — an intentional no-op, not a placebo
        body = body_without_docstring(fn)
        if not body:
            yield (fn.lineno, f"'{fn.name}' has only a docstring — the announced action is unimplemented")
            continue
        if len(body) != 1:
            continue
        stmt = body[0]
        if is_ellipsis(stmt) or is_notimplemented(stmt):
            continue  # honest
        if isinstance(stmt, ast.Pass):
            yield (fn.lineno, f"'{fn.name}' body is just `pass` — the announced action does nothing")
        elif isinstance(stmt, ast.Return):
            if stmt.value is None:
                yield (fn.lineno, f"'{fn.name}' only `return`s — no value and no side effect")
            elif is_success_literal(stmt.value):
                yield (fn.lineno, f"'{fn.name}' just returns success without doing the work")


@register("always_succeeds", "placebo", Severity.MEDIUM)
def always_succeeds(ctx: FileContext) -> Iterable[tuple[int, str]]:
    """A non-trivial action that returns success and structurally *cannot* fail.

    If a function returns a success value but contains no ``raise``, no failure return, and no
    branch (``if``/``try``/``for``/``while``/``match``), then every path reports success — the
    definition of a test that will always pass and a pipeline that can never surface an error.
    Trivial bodies are left to ``not_stub``; this looks only at functions with real length.
    """
    for fn in _functions(ctx.tree):
        if not is_action_name(fn.name):
            continue
        if len(body_without_docstring(fn)) < 3:
            continue
        returns_success = False
        can_fail = False
        for node in ast.walk(fn):
            if isinstance(node, ast.Raise | ast.If | ast.Try | ast.For | ast.While | ast.Match):
                can_fail = True
            elif isinstance(node, ast.Return) and node.value is not None:
                if is_success_literal(node.value):
                    returns_success = True
                if is_failure_literal(node.value):
                    can_fail = True
        if returns_success and not can_fail:
            yield (
                fn.lineno,
                f"'{fn.name}' always returns success — no raise, no failure return, no branch: "
                f"it cannot fail",
            )


def _is_self_report(test: ast.expr) -> bool:
    """Is this assert test reading the code's own success flag rather than a real effect?

    Matches ``x.success`` / ``x.passed`` etc., and ``x.status == "ok"`` style comparisons.
    """
    if isinstance(test, ast.Attribute) and test.attr in SUCCESS_ATTRS:
        return True
    if isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq | ast.Is):
        operands = [test.left, *test.comparators]
        has_status = any(isinstance(o, ast.Attribute) and o.attr in STATUS_ATTRS for o in operands)
        has_success_word = any(
            isinstance(o, ast.Constant) and isinstance(o.value, str) and o.value.lower() in SUCCESS_WORDS
            for o in operands
        )
        return has_status and has_success_word
    return False


@register("oracle_independent", "placebo", Severity.MEDIUM, test_only=True)
def oracle_independent(ctx: FileContext) -> Iterable[tuple[int, str]]:
    """A test that asserts on a dict *it wrote itself* — validating its own setup, not a real effect.

    ``state = {}; state["ok"] = True; assert state["ok"]`` proves nothing about the code under test —
    the test wrote the value it then checks. The fix is to assert on something the SUT produced.

    The calibration that keeps this honest: writes inside a **nested function / lambda** (a spy or mock
    callback) don't count — there the SUT is the one writing, when it calls the callback, so asserting
    on what the spy captured is a legitimate oracle of real behavior, not a placebo.
    """
    for fn in _functions(ctx.tree):
        if not fn.name.lower().startswith("test"):
            continue
        nested_ids: set[int] = set()
        for inner in ast.walk(fn):
            if inner is fn:
                continue
            if isinstance(inner, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
                nested_ids.update(id(d) for d in ast.walk(inner))
        # Only *plain* dicts the test itself creates as ad-hoc state — `d = {}` / `d = dict()`. A
        # domain object (`d = CaseInsensitiveDict()`, a cookie jar) is often the thing under test, and
        # writing-then-reading it exercises real behavior, so it must NOT count.
        plain_dicts: set[str] = set()
        for node in ast.walk(fn):
            if id(node) in nested_ids:
                continue
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name):
                value = node.value
                if isinstance(value, ast.Dict) or (isinstance(value, ast.Call)
                        and isinstance(value.func, ast.Name) and value.func.id == "dict"):
                    plain_dicts.add(node.targets[0].id)
        # …and only when a LITERAL is written into it. `d[k] = sut()` stores the SUT's output — reading
        # it back is a real oracle; `d[k] = 5` then `assert d[k] == 5` proves only the test's own setup.
        written: set[str] = set()
        for node in ast.walk(fn):
            if id(node) in nested_ids or not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) \
                        and target.value.id in plain_dicts and _is_literalish(node.value):
                    written.add(target.value.id)
        if not written:
            continue
        seen: set[int] = set()
        for node in ast.walk(fn):
            if not isinstance(node, ast.Assert):
                continue
            for sub in ast.walk(node.test):
                if isinstance(sub, ast.Subscript) and isinstance(sub.value, ast.Name) \
                        and sub.value.id in written and node.lineno not in seen:
                    seen.add(node.lineno)
                    yield (
                        node.lineno,
                        f"asserts on '{sub.value.id}[…]' that the test itself wrote a few lines up — "
                        f"no independent oracle of the real effect",
                    )


@register("assert_selfreport", "placebo", Severity.MEDIUM, test_only=True)
def assert_selfreport(ctx: FileContext) -> Iterable[tuple[int, str]]:
    """A test that asserts on the pipeline's own report of success, not an independent oracle.

    ``assert result.success`` proves the code *said* it worked, not that it *did*. The fix is to
    assert on the observable effect (a file written, a row inserted, a value returned) checked by
    something other than the code under test.
    """
    for node in ast.walk(ctx.tree):
        if isinstance(node, ast.Assert) and _is_self_report(node.test):
            yield (
                node.lineno,
                "assert reads the code's own self-report (e.g. `.success` / `status == 'ok'`), "
                "not an independent oracle of the real effect",
            )


# Names that reveal a test module exercises failure, not just the happy path.
_NEGATIVE_MARKERS = (
    "negativ", "failure", "fails", "should_fail", "reject", "denied", "deny", "invalid",
    "blocked", "error", "raises", "missing", "empty", "refuse", "red",
)


@register("no_negative_control", "placebo", Severity.MEDIUM, test_only=True)
def no_negative_control(ctx: FileContext) -> Iterable[tuple[int, str]]:
    """A test module that only ever asserts success — no failure case, no ``pytest.raises``.

    Deliberately narrow to stay high-signal: it fires only when the module *also* asserts on a
    self-report (the ``assert_selfreport`` pattern). A suite that both trusts the code's word and
    never checks the failure path is proving almost nothing.
    """
    tests = [fn for fn in _functions(ctx.tree) if fn.name.lower().startswith("test")]
    if not tests:
        return
    asserts_self_report = any(
        _is_self_report(node.test)
        for fn in tests
        for node in ast.walk(fn)
        if isinstance(node, ast.Assert)
    )
    if not asserts_self_report:
        return
    has_negative = any(any(m in fn.name.lower() for m in _NEGATIVE_MARKERS) for fn in tests)
    if not has_negative:
        has_negative = any(
            isinstance(n, ast.Attribute) and n.attr == "raises" for n in ast.walk(ctx.tree)
        )
    if not has_negative:
        yield (
            tests[0].lineno,
            "test module only exercises the happy path via self-report — no failure case, "
            "no `pytest.raises`, no negative control",
        )
