"""polyglot — the language-agnostic layer.

Platão's deep checks (placebo, completeness, the import graph) read Python's AST, so they are
Python-only. This module is the honest breadth layer: the subset of checks that hold in *any*
language, matched by robust line/regex patterns rather than a parser — an empty ``catch`` that
swallows an error, dynamic ``eval``, a debugger left in the code, an untracked ``TODO``. It runs on
non-Python source (JS/TS/Go/Ruby/PHP/Java/…).

Shallow by design — a regex is not an AST, so this catches the universal smells, not the deep ones.
Full per-language deep analysis (via tree-sitter) is a separate, larger step; this is what lets
``platao check app.ts`` mean something today instead of "Python only".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from platao.finding import Finding, Severity

# Non-Python code files this layer scans. Python goes through the deep AST checks, never here.
POLYGLOT_EXTS = frozenset({
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".rb", ".php", ".java",
    ".cs", ".rs", ".kt", ".kts", ".swift", ".scala", ".c", ".cc", ".cpp", ".dart",
    ".vue", ".svelte",
})


@dataclass(frozen=True, slots=True)
class PolyglotCheck:
    """One universal pattern: what it is, and how bad it is."""

    check_id: str
    category: str
    severity: Severity
    message: str


# Metadata for `list-checks` (the patterns themselves live below).
POLYGLOT_CHECKS: list[PolyglotCheck] = [
    PolyglotCheck("swallowed_error", "robustness", Severity.HIGH,
                  "empty catch block swallows the error silently — no log, no re-raise"),
    PolyglotCheck("dangerous_dynamic", "security", Severity.HIGH,
                  "dynamic code execution (`eval` / `new Function`)"),
    PolyglotCheck("debug_leftover", "hygiene", Severity.LOW, "a debugger was left in the code"),
    PolyglotCheck("debt_tracked", "hygiene", Severity.LOW,
                  "untracked TODO/FIXME — add an owner or issue ref"),
]

# `\s` spans newlines, so this matches `catch (e) {}` and `catch (e) {\n   \n}` alike.
_EMPTY_CATCH = re.compile(r"\bcatch\s*(?:\([^)]*\))?\s*\{\s*\}")
_DYNAMIC = re.compile(r"\beval\s*\(|\bnew\s+Function\s*\(")
_DEBUGGER = re.compile(r"\bdebugger\b|\bbinding\.pry\b|\bbyebug\b")
_DEBT = re.compile(r"(?://|#|--)\s*(TODO|FIXME|XXX|HACK)\b(\([^)]*\))?", re.IGNORECASE)
_ISSUE_REF = re.compile(r"#\d+")


def _finding(check: PolyglotCheck, path: str, source: str, offset: int,
             message: str | None = None) -> Finding:
    line = source.count("\n", 0, offset) + 1
    start = source.rfind("\n", 0, offset) + 1
    end = source.find("\n", offset)
    end = len(source) if end < 0 else end
    snippet = source[start:end].strip()[:160]
    return Finding(check.check_id, check.category, check.severity, path, line,
                   message or check.message, snippet)


_BY_ID = {c.check_id: c for c in POLYGLOT_CHECKS}


def scan(path: str, source: str) -> list[Finding]:
    """Run the universal patterns over one non-Python source file."""
    out: list[Finding] = []

    for m in _EMPTY_CATCH.finditer(source):
        out.append(_finding(_BY_ID["swallowed_error"], path, source, m.start()))

    for m in _DYNAMIC.finditer(source):
        out.append(_finding(_BY_ID["dangerous_dynamic"], path, source, m.start()))

    debugger = _BY_ID["debug_leftover"]
    for m in _DEBUGGER.finditer(source):
        out.append(_finding(debugger, path, source, m.start(),
                            f"a debugger was left in the code (`{m.group(0)}`)"))

    debt = _BY_ID["debt_tracked"]
    for m in _DEBT.finditer(source):
        if m.group(2):  # has (owner/id)
            continue
        line_end = source.find("\n", m.start())
        line_end = len(source) if line_end < 0 else line_end
        rest = source[m.end():line_end]
        if _ISSUE_REF.search(rest):  # a #123 later on the line
            continue
        marker = m.group(1).upper()
        out.append(_finding(debt, path, source, m.start(),
                            f"untracked {marker} — add an owner or issue ref, e.g. {marker}(#123)"))

    out.sort(key=lambda f: f.sort_key)
    return out
