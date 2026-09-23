"""Hygiene checks — the small, cheap tells that work was left mid-thought.

An untracked ``TODO`` (a promise with no owner) and a debugger left in the source. Both are
low-severity by design: they don't break behavior, but they're the fingerprints of unfinished work,
and an agent leaves them constantly.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from collections.abc import Iterable

from platao.checks import register
from platao.checks._ast import dotted_name
from platao.context import FileContext
from platao.finding import Severity
from platao.patterns import is_debt_marker

# A debt marker at the start of a comment, optionally with a `(owner/id)`.
_DEBT = re.compile(r"^#\s*(TODO|FIXME|XXX|HACK)\b(\([^)]*\))?", re.IGNORECASE)
_ISSUE_REF = re.compile(r"#\d+")


@register("debt_tracked", "hygiene", Severity.LOW)
def debt_tracked(ctx: FileContext) -> Iterable[tuple[int, str]]:
    """A ``TODO``/``FIXME`` with no owner or issue reference — a promise nobody can chase.

    Tracked debt is fine: ``TODO(alice)`` or ``TODO(#123)`` or a trailing ``#123`` all count. What
    we flag is the bare marker with nothing to route it back to.

    Scanned over real COMMENT tokens only (via ``tokenize``), never over source text — so a
    ``# TODO`` sitting inside a *string literal* (fixture data, an example in a docstring) is not a
    false debt. The tool must not trip over its own auditing.
    """
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(ctx.source).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return  # parsed as AST but not tokenizable — degrade quietly
    for tok in tokens:
        if tok.type != tokenize.COMMENT:
            continue
        match = _DEBT.search(tok.string.strip())
        if match is None:
            continue
        if match.group(2):  # has a (owner/id)
            continue
        rest = tok.string.strip()[match.end():]
        if not is_debt_marker(match.group(1), rest):  # "# Todo arquivo…" — a pt/es word, not a debt
            continue
        if _ISSUE_REF.search(rest):  # a #123 later in the comment
            continue
        marker = match.group(1).upper()
        yield (tok.start[0], f"untracked {marker} — add an owner or issue ref, e.g. {marker}(#123)")


# The unambiguous "I forgot to remove my breakpoint" calls. NOT the bare `import pdb` — that's a
# legitimate dependency (a CLI or test util that manages the debugger), and NOT `post_mortem`, which
# is a real "drop into the debugger on crash" feature. Only a stray `set_trace`/`breakpoint()` call
# is nearly-always an accident, which is what keeps this check near-zero false-positive.
_DEBUG_CALLS = frozenset({"set_trace"})


@register("debug_leftover", "hygiene", Severity.LOW)
def debug_leftover(ctx: FileContext) -> Iterable[tuple[int, str]]:
    """A debugger *call* left in the source: ``breakpoint()`` or ``pdb.set_trace()`` / ``ipdb.set_trace()``.

    Deliberately narrow — ``print`` is legitimate in a CLI and too noisy to flag; a bare ``import pdb``
    is a real dependency (``click.testing`` uses it to manage the debugger), not a leftover; and
    ``pdb.post_mortem()`` is a genuine feature. Only the stray breakpoint call is flagged, so this
    stays near-zero false-positive.
    """
    for node in ast.walk(ctx.tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "breakpoint":
            yield (node.lineno, "`breakpoint()` left in the code")
        elif isinstance(func, ast.Attribute) and func.attr in _DEBUG_CALLS:
            yield (node.lineno, f"debugger `{dotted_name(func) or func.attr}()` left in the code")
