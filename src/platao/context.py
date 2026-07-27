"""The unit of analysis: one parsed file.

``FileContext`` is built once per file and handed to every check. Parsing happens exactly once
here, not per check. This is also the seam where other languages plug in later: a check receives a
context, and a future ``TreeSitterContext`` can satisfy the same shape for JS/Go/Rust without any
check knowing the difference. For now there is one implementation, backed by Python's stdlib ``ast``.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

# Directory names that mark a test tree, and filename markers that mark a test/fixture file. The
# filename markers cover conventions beyond pytest — JS/TS suites and helpers (`foo.suite.ts`,
# `x-test-helpers.ts`, `contract-suites.ts`), Jest/Vitest (`*.test.*`, `*.spec.*`), e2e and fixtures.
# Real competitor codebases (OpenClaw, Odysseus) name test fixtures this way; without them a hardcoded
# test token reads as a HIGH production secret. See patterns.py for the value-side calibration.
_TEST_DIRS = frozenset({"tests", "test", "__tests__", "fixtures", "__fixtures__", "e2e", "testdata"})
_TEST_BASE_MARKERS = (
    ".test.", ".spec.", ".e2e.", ".suite.", "-suite.", ".fixture", "-test-helpers", "-test-utils",
    "-test-harness", "test-helpers", "test-utils", "test-harness", "contract-suites", "-fixtures.",
)


def _looks_like_test(path: str) -> bool:
    """True if ``path`` is a test or fixture file — by test dir, ``test_*``/``*_test`` name, or a
    JS/TS test-file convention (``*.test.*``, ``*.suite.ts``, ``*-test-helpers.ts``, …).

    Deliberately path-based (no parsing) so it works for any language. Broadened beyond pytest because
    test-only checks run *only* when this is true, and production-only checks (secrets) downgrade when
    it is — a fixture's fake credential must not read as a HIGH production leak.
    """
    parts = path.replace("\\", "/").lower().split("/")
    base = parts[-1]
    if _TEST_DIRS & set(parts[:-1]):
        return True
    if base.startswith("test_") or base.endswith(("_test.py", "_test.go", "_test.rb")):
        return True
    return any(mk in base for mk in _TEST_BASE_MARKERS)


@dataclass(slots=True)
class FileContext:
    """A single file, parsed once and ready for every check to read.

    Raises:
        SyntaxError: if the source does not parse. The engine catches this and turns it into a
            ``parse_error`` finding rather than crashing the run.
    """

    path: str
    source: str
    lines: list[str]
    tree: ast.Module
    is_test: bool

    @classmethod
    def from_source(cls, path: str, source: str) -> FileContext:
        """Parse ``source`` and build a context. The single place ``ast.parse`` is called."""
        tree = ast.parse(source, filename=path)
        return cls(
            path=path,
            source=source,
            lines=source.splitlines(),
            tree=tree,
            is_test=_looks_like_test(path),
        )

    def snippet(self, line: int) -> str:
        """The source at ``line`` (1-based), trimmed to 160 chars. Empty if out of range."""
        idx = line - 1
        if 0 <= idx < len(self.lines):
            return self.lines[idx].strip()[:160]
        return ""
