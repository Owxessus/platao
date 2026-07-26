"""Proofs for the project-wide checks. These build a real package tree in tmp_path and audit it."""

from __future__ import annotations

from pathlib import Path

from platao import analyze_paths


def _pkg(root: Path, files: dict[str, str]) -> None:
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")


def findings_by_id(root: Path) -> dict[str, list[str]]:
    """Map check_id -> list of display paths it fired on, for the whole tree under root."""
    out: dict[str, list[str]] = {}
    for f in analyze_paths([root], root=root):
        out.setdefault(f.check_id, []).append(f.path)
    return out


# ── unwired ───────────────────────────────────────────────────────────────────────

def test_unwired__island_is_caught_used_and_entrypoint_are_not(tmp_path: Path):
    _pkg(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/core.py": "def f():\n    return 1\n",                       # imported by app -> wired
        "pkg/app.py": "from pkg.core import f\nif __name__ == '__main__':\n    f()\n",  # entrypoint
        "pkg/island.py": "def g():\n    return 2\n",                     # imported by nobody
    })
    by_id = findings_by_id(tmp_path)
    unwired = by_id.get("unwired", [])
    assert "pkg/island.py" in unwired          # prove_effect
    assert "pkg/core.py" not in unwired         # imported -> wired
    assert "pkg/app.py" not in unwired          # entry point (negative control)
    assert "pkg/__init__.py" not in unwired     # package init exempt


def test_unwired__test_files_are_exempt(tmp_path: Path):
    _pkg(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/thing.py": "def f():\n    return 1\n",
        "tests/test_thing.py": "from pkg.thing import f\ndef test_it():\n    assert f() == 1\n",
    })
    by_id = findings_by_id(tmp_path)
    # thing is imported by the test, and the test file itself is exempt -> no unwired at all.
    assert "unwired" not in by_id


def test_unwired__reexported_module_is_wired(tmp_path: Path):
    # A module referenced only by the package __init__ (public API) must not be called an island.
    _pkg(tmp_path, {
        "pkg/__init__.py": "from pkg.api import public\n",
        "pkg/api.py": "def public():\n    return 1\n",
    })
    assert "unwired" not in findings_by_id(tmp_path)


# ── dangling_import ───────────────────────────────────────────────────────────────

def test_dangling_import__missing_name_is_caught(tmp_path: Path):
    _pkg(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/mod.py": "def real():\n    return 1\n",
        "pkg/user.py": "from pkg.mod import ghost\n",   # ghost is not defined in mod
    })
    by_id = findings_by_id(tmp_path)
    assert "pkg/user.py" in by_id.get("dangling_import", [])


def test_dangling_import__existing_name_is_silent(tmp_path: Path):  # negative control
    _pkg(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/mod.py": "def real():\n    return 1\n",
        "pkg/user.py": "from pkg.mod import real\n",
    })
    assert "dangling_import" not in findings_by_id(tmp_path)


def test_dangling_import__external_module_is_silent(tmp_path: Path):
    # We only judge modules we can see. `from os import path` is not ours to second-guess.
    _pkg(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/user.py": "from os import path\n",
    })
    assert "dangling_import" not in findings_by_id(tmp_path)


def test_dangling_import__submodule_import_is_silent(tmp_path: Path):
    # `from pkg import sub` where pkg/sub.py exists is valid even if __init__ doesn't name it.
    _pkg(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/sub.py": "VALUE = 1\n",
        "pkg/user.py": "from pkg import sub\n",
    })
    assert "dangling_import" not in findings_by_id(tmp_path)
