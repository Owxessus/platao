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
    # MEDIUM, matching Python's `except Exception: pass`: an empty JS/Go/… catch is a broad silent
    # swallow — a real smell, but a widely-accepted best-effort idiom (`try { require(x) } catch {}`),
    # so it's advisory, not a hard CI fail. (Python's bare `except:` is HIGH only because it also eats
    # KeyboardInterrupt/SystemExit; a catch in these languages has no such interrupt to swallow.)
    PolyglotCheck("swallowed_error", "robustness", Severity.MEDIUM,
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


def _mask_noise(src: str) -> str:
    """Blank out ``//``/``/* */`` comments and ``'``/``"`` string bodies (spaces, newlines kept).

    A regex is not a parser, so a mention of ``eval()`` in a *comment* or a ``catch {}`` in a *string*
    would otherwise be a false positive (seen in the wild: vite's ``// Most eval() calls…``). Masking
    to equal-length whitespace keeps every offset and line number intact, so findings still point at
    the right place. Deliberately does not touch ``#`` (it's a private-field sigil in JS/TS, not always
    a comment) nor backtick templates (their ``${…}`` holds real code) — comments and quoted strings
    are where the false matches actually live.
    """
    out = list(src)
    i, n = 0, len(src)
    state: str | None = None  # None | "line" | "block" | "'" | '"'
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if state is None:
            if c == "/" and nxt == "/":
                state, out[i], out[i + 1] = "line", " ", " "; i += 2; continue
            if c == "/" and nxt == "*":
                state, out[i], out[i + 1] = "block", " ", " "; i += 2; continue
            if c in ("'", '"'):
                state, out[i] = c, " "; i += 1; continue
            i += 1
        elif state == "line":
            if c == "\n":
                state = None
            else:
                out[i] = " "
            i += 1
        elif state == "block":
            if c == "*" and nxt == "/":
                out[i], out[i + 1], state = " ", " ", None; i += 2; continue
            if c != "\n":
                out[i] = " "
            i += 1
        else:  # inside a '…' or "…" string
            if c == "\\":
                out[i] = " "
                if i + 1 < n and src[i + 1] != "\n":
                    out[i + 1] = " "
                i += 2; continue
            if c == state:
                out[i], state = " ", None
            elif c != "\n":
                out[i] = " "
            i += 1
    return "".join(out)


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

    # The code-pattern checks run on a comment/string-masked view so `eval()` in a comment or
    # `catch {}` in a string isn't a false match. Offsets are preserved, so `source` gives the snippet.
    code = _mask_noise(source)

    for m in _EMPTY_CATCH.finditer(code):
        out.append(_finding(_BY_ID["swallowed_error"], path, source, m.start()))

    for m in _DYNAMIC.finditer(code):
        out.append(_finding(_BY_ID["dangerous_dynamic"], path, source, m.start()))

    debugger = _BY_ID["debug_leftover"]
    for m in _DEBUGGER.finditer(code):
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
