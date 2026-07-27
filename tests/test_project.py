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


def test_dangling_import__try_guarded_definition_is_silent(tmp_path: Path):  # FP guard (psf/requests)
    # `is_urllib3_1` is defined in both branches of a top-level try/except — a real module attribute.
    _pkg(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/compat.py": (
            "try:\n    is_v1 = detect() == 1\n"
            "except (TypeError, AttributeError):\n    is_v1 = True\n"
        ),
        "pkg/user.py": "from pkg.compat import is_v1\n",
    })
    assert "dangling_import" not in findings_by_id(tmp_path)


def test_dangling_import__implicit_dunder_is_silent(tmp_path: Path):  # FP guard (httpie/cli)
    # `from pkg import __doc__` is valid — the interpreter provides __doc__ on every module.
    _pkg(tmp_path, {
        "pkg/__init__.py": "'a package docstring'\n",
        "pkg/user.py": "from pkg import __doc__, __name__\n",
    })
    assert "dangling_import" not in findings_by_id(tmp_path)


def test_dangling_import__if_guarded_and_unpacked_definition_is_silent(tmp_path: Path):
    # Conditional def under `if`, plus tuple-unpacked names — both are exposed module attributes.
    _pkg(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/compat.py": (
            "import sys\n"
            "if sys.version_info >= (3, 12):\n    def newapi():\n        return 1\n"
            "else:\n    def newapi():\n        return 2\n"
            "A, B = 1, 2\n"
        ),
        "pkg/user.py": "from pkg.compat import newapi, A, B\n",
    })
    assert "dangling_import" not in findings_by_id(tmp_path)


def test_dangling_import__with_as_binding_is_silent(tmp_path: Path):  # FP guard from gradio
    # `with gr.Blocks() as demo:` at module scope binds `demo` as a module attribute — importing it
    # is valid. Gradio/ML modules use this idiom; missing it was a false dangling_import.
    _pkg(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/dash.py": "import cm\nwith cm.ctx() as demo:\n    pass\n",
        "pkg/user.py": "from pkg.dash import demo\n",
    })
    assert "dangling_import" not in findings_by_id(tmp_path)


def test_dangling_import__module_getattr_suppresses(tmp_path: Path):  # FP guard from jax
    # A module-level __getattr__ (PEP 562) can resolve any name lazily — jax/core.py uses the
    # assignment form for deprecation shims. Both `def` and `=` forms land in bound_names.
    for form in ("def __getattr__(n):\n    raise AttributeError(n)\n", "__getattr__ = _mk()\n"):
        _pkg(tmp_path, {
            "pkg/__init__.py": "",
            "pkg/shim.py": form,
            "pkg/user.py": "from pkg.shim import AnythingGoes\n",
        })
        assert "dangling_import" not in findings_by_id(tmp_path), form


def test_dangling_import__try_except_guarded_is_silent(tmp_path: Path):  # FP guard from jax
    # `try: from x import y \n except ImportError:` is the optional-import idiom — the name is allowed
    # to be absent (jax does this for a not-yet-existing `repro` module). Not a broken import.
    _pkg(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/mod.py": "def real():\n    return 1\n",
        "pkg/user.py": "try:\n    from pkg.mod import ghost\nexcept ImportError:\n    ghost = None\n",
    })
    assert "dangling_import" not in findings_by_id(tmp_path)


def test_dangling_import__unguarded_still_caught(tmp_path: Path):  # negative control
    _pkg(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/mod.py": "def real():\n    return 1\n",
        "pkg/user.py": "from pkg.mod import ghost\n",  # no try/except → real broken import
    })
    assert "pkg/user.py" in findings_by_id(tmp_path).get("dangling_import", [])


def test_dangling_import__stdlib_base_is_silent(tmp_path: Path):  # FP guard from pytorch
    # A repo file named bisect.py in a no-__init__ dir must not shadow stdlib `bisect` into a false
    # dangling for `from bisect import bisect_right`.
    _pkg(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/user.py": "from bisect import bisect_right\nfrom os.path import join\n",
    })
    assert "dangling_import" not in findings_by_id(tmp_path)


def test_dangling_import__generated_artifacts_are_silent(tmp_path: Path):  # FP guard from tensorflow
    # `_pywrap_*` (compiled pybind/SWIG) and `*_pb2` (protobuf) are generated at build, absent from
    # source — importing them is not a dangling import.
    _pkg(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/client/__init__.py": "",
        "pkg/user.py": "from pkg.client import _pywrap_device_lib\nfrom pkg.client import model_pb2\n",
    })
    assert "dangling_import" not in findings_by_id(tmp_path)


def test_dangling_import__cython_extension_submodule_is_silent(tmp_path: Path):  # FP guard from pandas
    # `from pkg._libs import lib` where lib is a Cython module (lib.pyx / lib.pyi shipped, compiled to
    # .so at build) — a valid compiled submodule, not a dangling import.
    _pkg(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/_libs/__init__.py": "",
        "pkg/_libs/lib.pyx": "# cython source\n",
        "pkg/_libs/lib.pyi": "def f() -> int: ...\n",
        "pkg/user.py": "from pkg._libs import lib\n",
    })
    assert "dangling_import" not in findings_by_id(tmp_path)
