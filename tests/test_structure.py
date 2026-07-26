"""Proofs for structure checks."""

from __future__ import annotations

from platao import analyze_source


def ids(source: str, path: str = "module.py") -> set[str]:
    return {f.check_id for f in analyze_source(path, source)}


def test_not_god_function__long_function_is_caught():
    body = "\n".join(f"    x{i} = {i}" for i in range(130))
    assert "not_god_function" in ids(f"def huge():\n{body}\n")


def test_not_god_function__short_function_is_silent():  # negative control
    assert "not_god_function" not in ids("def small():\n    return 1 + 2\n")


def test_not_god_function__two_small_functions_are_silent():
    src = "def a():\n    return 1\n\ndef b():\n    return 2\n"
    assert "not_god_function" not in ids(src)
