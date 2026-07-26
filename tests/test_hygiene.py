"""Proofs for hygiene checks."""

from __future__ import annotations

from platao import analyze_source


def ids(source: str, path: str = "module.py") -> set[str]:
    return {f.check_id for f in analyze_source(path, source)}


# ── debt_tracked ──────────────────────────────────────────────────────────────────

def test_debt_tracked__bare_todo_is_caught():
    assert "debt_tracked" in ids("x = 1  # TODO fix this later\n")


def test_debt_tracked__bare_fixme_is_caught():
    assert "debt_tracked" in ids("x = 1  # FIXME broken\n")


def test_debt_tracked__owner_ref_is_silent():  # negative control
    assert "debt_tracked" not in ids("x = 1  # TODO(alice) fix this\n")


def test_debt_tracked__issue_ref_is_silent():
    assert "debt_tracked" not in ids("x = 1  # TODO fix this, tracked in #42\n")


def test_debt_tracked__paren_issue_is_silent():
    assert "debt_tracked" not in ids("x = 1  # TODO(#42): fix this\n")


# ── debug_leftover ────────────────────────────────────────────────────────────────

def test_debug_leftover__breakpoint_is_caught():
    assert "debug_leftover" in ids("def f():\n    breakpoint()\n    return 1\n")


def test_debug_leftover__pdb_set_trace_is_caught():
    src = "import pdb\ndef f():\n    pdb.set_trace()\n    return 1\n"
    assert "debug_leftover" in ids(src)


def test_debug_leftover__print_is_silent():  # negative control — print is legitimate
    assert "debug_leftover" not in ids("def f():\n    print('hello')\n    return 1\n")
