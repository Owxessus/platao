"""Structure checks — "is this one thing, or did it grow into a god?"

A function that has swollen past a couple of screens is almost never doing one thing — it's the place
bugs hide and reviewers skim. This is a size smell, not a correctness bug, so it's advisory (MEDIUM)
and the threshold is deliberately generous: we flag the genuinely-oversized, not the merely-long.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable

from platao.checks import register
from platao.context import FileContext
from platao.finding import Severity

# A function longer than this many physical lines has almost certainly earned an extraction. Kept
# generous on purpose — mature code has legitimately long dispatchers, and this must not cry wolf.
_MAX_LINES = 120


@register("not_god_function", "structure", Severity.MEDIUM)
def not_god_function(ctx: FileContext) -> Iterable[tuple[int, str]]:
    """A function/method whose body spans more than ~120 lines — a god-function forming.

    Measured on the real span (``end_lineno - lineno``). Only the innermost count matters, so a big
    module isn't blamed on its functions and vice versa. Advisory: length is a smell, not a defect —
    but past this size "one function, one job" is almost always already broken.
    """
    for node in ast.walk(ctx.tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        end = getattr(node, "end_lineno", None)
        if end is None:
            continue
        span = end - node.lineno + 1
        if span > _MAX_LINES:
            yield (
                node.lineno,
                f"'{node.name}' is {span} lines long (> {_MAX_LINES}) — a god-function; "
                f"split it into stages, each doing one thing",
            )
