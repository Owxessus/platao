"""Project-wide checks — "does this connect to anything?"

Two questions a single file can't answer: is this module imported by anyone (or is it a dead
island?), and does each ``from x import y`` actually resolve to something that exists? Both read the
:class:`~platao.project.ProjectIndex`. Both are written to be quiet on the shapes that legitimately
look unconnected — package ``__init__``, ``__main__``, entry points, test files — so "island code"
means island code, not "a library public surface".
"""

from __future__ import annotations

from collections.abc import Iterable

from platao.checks import project_check
from platao.finding import Finding, Severity
from platao.project import ProjectIndex

# Files that are unconnected by design — never flag them as islands.
_WIRED_EXEMPT_BASENAMES = frozenset({"__init__.py", "__main__.py", "conftest.py", "setup.py"})

# Dunders the interpreter puts on every module implicitly — `from pkg import __doc__` is valid even
# though nothing assigns them in the source. Importing one is never a broken import.
_IMPLICIT_MODULE_DUNDERS = frozenset({
    "__doc__", "__name__", "__file__", "__loader__", "__spec__",
    "__package__", "__builtins__", "__dict__", "__path__",
})


@project_check("unwired", "connectivity", Severity.LOW)
def unwired(index: ProjectIndex) -> Iterable[Finding]:
    """A module nobody in the scanned tree imports — possibly dead, possibly public API.

    Exemptions keep it honest: test files, package ``__init__``/``__main__``/``conftest``/``setup``,
    and anything with an ``if __name__ == "__main__"`` guard or living under ``scripts``/``bin`` are
    entry points, not islands. A module re-exported by its package's ``__init__`` counts as imported
    (that shows up as an import target in the index), so public API *that is re-exported* isn't misread.

    Kept at **LOW**: for a library, a public submodule imported only by downstream code (e.g.
    ``click.testing``) is genuinely unimported *inside* the repo yet not dead — a fact no in-tree
    analysis can settle. So this is an advisory hint to eyeball, not a defect that fails CI. Only runs
    over a scanned tree — auditing a single named file can't see who imports it.
    """
    if not index.whole_project:
        return
    for m in index.modules.values():
        if m.is_test or m.is_pkg_init or m.is_entrypoint:
            continue
        if m.path.name in _WIRED_EXEMPT_BASENAMES:
            continue
        if m.module in index.imported_targets:
            continue
        yield index.finding(
            m, "unwired", "connectivity", Severity.LOW, 1,
            f"module '{m.module}' is imported by nobody in the scanned tree — dead code, or public "
            f"API used only by downstream consumers (eyeball it)",
        )


@project_check("dangling_import", "correctness", Severity.HIGH)
def dangling_import(index: ProjectIndex) -> Iterable[Finding]:
    """``from <a repo module> import <name>`` where ``<name>`` doesn't exist there — a broken import.

    Only fires when the base module is one we fully parsed (so we *know* what it exposes) and the
    name is neither defined nor re-exported there, nor a submodule of it. External modules and
    modules with a ``*`` import are left alone — we never claim absence we can't prove.
    """
    for m in index.modules.values():
        for line, base, name in m.from_imports:
            target = index.modules.get(base)
            if target is None or target.has_star_import:
                continue  # external, or we can't see everything it re-exports
            if name in _IMPLICIT_MODULE_DUNDERS:
                continue  # `from pkg import __doc__` — the interpreter provides it, not the source
            if name in target.bound_names:
                continue
            if f"{base}.{name}" in index.modules:
                continue  # it's a submodule, imported as a name
            yield index.finding(
                m, "dangling_import", "correctness", Severity.HIGH, line,
                f"`from {base} import {name}` — '{name}' is not defined or re-exported in "
                f"module '{base}'",
            )
