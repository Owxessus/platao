"""Platão — a deterministic completeness auditor. It reads the AST; it doesn't guess.

Public API:
    >>> from platao import analyze_source
    >>> findings = analyze_source("service.py", open("service.py").read())
    >>> [f.check_id for f in findings]

Everything else is an implementation detail. The checks self-register on import.
"""

from __future__ import annotations

__version__ = "0.1.0"

from platao.engine import analyze_file, analyze_paths, analyze_source
from platao.finding import Finding, Severity

__all__ = [
    "Finding",
    "Severity",
    "analyze_source",
    "analyze_file",
    "analyze_paths",
    "__version__",
]
