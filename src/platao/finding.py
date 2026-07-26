"""The verdict types Platão speaks in.

A ``Finding`` is a single answer to a single question about a single line. It is a pure value —
no I/O, no formatting, no severity logic beyond ordering. Everything downstream (the report, the
CLI exit code, the MCP payload) is derived from a list of these.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    """How much a finding should worry you. String-valued so it serializes cleanly to JSON."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Sort order: most severe first, then by line. Kept here so ``Finding`` and the engine agree.
_ORDER = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}

# Severity threshold ranks (lower = more severe). ``"never"`` is the "nothing fails" sentinel.
# Shared by the CLI exit code and the MCP payload so "does this pass?" means one thing everywhere.
RANK: dict[str, int] = {"high": 0, "medium": 1, "low": 2, "never": 99}


@dataclass(frozen=True, slots=True)
class Finding:
    """One deterministic answer about one line of code.

    Attributes:
        check_id: stable id of the check that produced it (e.g. ``"not_stub"``).
        category: coarse group for reporting (e.g. ``"placebo"``, ``"robustness"``).
        severity: :class:`Severity`.
        path: display path of the file (repo-relative when known).
        line: 1-based line number the finding anchors to.
        message: one sentence, stated as a defect, not a suggestion.
        snippet: the offending source line, trimmed (may be empty).
    """

    check_id: str
    category: str
    severity: Severity
    path: str
    line: int
    message: str
    snippet: str = ""

    @property
    def sort_key(self) -> tuple[int, str, int]:
        """Most-severe-first, then by file, then by line."""
        return (_ORDER[self.severity], self.path, self.line)

    def to_dict(self) -> dict[str, object]:
        """Plain dict for JSON output / the MCP tool payload."""
        return {
            "check_id": self.check_id,
            "category": self.category,
            "severity": self.severity.value,
            "path": self.path,
            "line": self.line,
            "message": self.message,
            "snippet": self.snippet,
        }
