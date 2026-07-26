"""The unit of analysis: one parsed file.

``FileContext`` is built once per file and handed to every check. Parsing happens exactly once
here, not per check. This is also the seam where other languages plug in later: a check receives a
context, and a future ``TreeSitterContext`` can satisfy the same shape for JS/Go/Rust without any
check knowing the difference. For now there is one implementation, backed by Python's stdlib ``ast``.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass


def _looks_like_test(path: str) -> bool:
    """A path is a test file if it lives under a ``tests`` dir or is named ``test_*`` / ``*_test.py``.

    Test-only checks (``assert_selfreport``, ``no_negative_control``) run only when this is true, so
    the rule is deliberately conservative and path-based — the same convention pytest uses.
    """
    parts = path.replace("\\", "/").lower().split("/")
    base = parts[-1]
    return "tests" in parts or base.startswith("test_") or base.endswith("_test.py")


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
