"""Proofs for robustness & security checks."""

from __future__ import annotations

from platao import analyze_source
from platao.finding import Severity


def ids(source: str, path: str = "module.py") -> set[str]:
    return {f.check_id for f in analyze_source(path, source)}


def _sev(source: str, check_id: str, path: str = "module.py") -> Severity | None:
    for f in analyze_source(path, source):
        if f.check_id == check_id:
            return f.severity
    return None


# ── swallowed_error ───────────────────────────────────────────────────────────────

def test_swallowed_error__except_exception_pass_is_medium():
    # A real smell but a widely-accepted best-effort idiom — advisory, not a hard CI fail.
    src = "def f():\n    try:\n        risky()\n    except Exception:\n        pass\n"
    assert _sev(src, "swallowed_error") is Severity.MEDIUM


def test_swallowed_error__bare_except_pass_is_high():
    # Bare except eats SystemExit/KeyboardInterrupt too — genuinely dangerous.
    src = "def f():\n    try:\n        risky()\n    except:\n        pass\n"
    assert _sev(src, "swallowed_error") is Severity.HIGH


def test_swallowed_error__logged_and_reraised_is_silent():  # negative control
    src = (
        "def f():\n    try:\n        risky()\n"
        "    except Exception:\n        logger.exception('boom')\n        raise\n"
    )
    assert "swallowed_error" not in ids(src)


def test_swallowed_error__handled_with_default_is_silent():
    # Returning a default is a deliberate choice, not a swallowed error.
    src = "def f():\n    try:\n        return risky()\n    except Exception:\n        return None\n"
    assert "swallowed_error" not in ids(src)


def test_swallowed_error__narrow_specific_catch_is_silent():  # FP guard (from psf/requests)
    # `except StopIteration: pass` is a deliberate "expected, ignore it" idiom — not a dropped bug.
    src = "def f():\n    try:\n        next(it)\n    except StopIteration:\n        pass\n"
    assert "swallowed_error" not in ids(src)


def test_swallowed_error__narrow_tuple_catch_is_silent():  # FP guard (optional-import idiom)
    src = (
        "def f():\n    try:\n        import fast\n"
        "    except (ImportError, AttributeError):\n        pass\n"
    )
    assert "swallowed_error" not in ids(src)


def test_swallowed_error__base_exception_pass_is_high():
    # BaseException also catches SystemExit/KeyboardInterrupt — same danger as a bare except.
    src = "def f():\n    try:\n        risky()\n    except BaseException:\n        pass\n"
    assert _sev(src, "swallowed_error") is Severity.HIGH


# ── dangerous_dynamic ─────────────────────────────────────────────────────────────

def test_dangerous_dynamic__eval_is_caught():
    assert "dangerous_dynamic" in ids("def f(s):\n    return eval(s)\n")


def test_dangerous_dynamic__os_system_is_caught():
    assert "dangerous_dynamic" in ids("import os\ndef f(c):\n    os.system(c)\n")


def test_dangerous_dynamic__shell_true_is_caught():
    src = "import subprocess\ndef f(c):\n    subprocess.run(c, shell=True)\n"
    assert "dangerous_dynamic" in ids(src)


def test_dangerous_dynamic__literal_eval_is_silent():  # negative control — literal_eval is safe
    src = "import ast\ndef f(s):\n    return ast.literal_eval(s)\n"
    assert "dangerous_dynamic" not in ids(src)


def test_dangerous_dynamic__shell_false_is_silent():
    src = "import subprocess\ndef f(c):\n    subprocess.run(c, shell=False)\n"
    assert "dangerous_dynamic" not in ids(src)


# ── mutable_default (brought from Athena's lynceus, calibrated: only if mutated) ────

def test_mutable_default__list_mutated_is_caught():
    src = "def add(item, acc=[]):\n    acc.append(item)\n    return acc\n"
    assert "mutable_default" in ids(src)


def test_mutable_default__dict_subscript_assign_is_caught():
    src = "def put(k, v, cache={}):\n    cache[k] = v\n    return cache\n"
    assert "mutable_default" in ids(src)


def test_mutable_default__aug_assign_is_caught():
    src = "def grow(x, acc=[]):\n    acc += [x]\n    return acc\n"
    assert "mutable_default" in ids(src)


def test_mutable_default__read_only_is_silent():  # negative control — the calibration
    # A mutable default that is only READ is a smell, not the aliasing bug — don't cry wolf.
    src = "def first(acc=[]):\n    return acc[0] if acc else None\n"
    assert "mutable_default" not in ids(src)


def test_mutable_default__none_default_is_silent():  # the correct idiom
    src = "def add(item, acc=None):\n    acc = acc or []\n    acc.append(item)\n    return acc\n"
    assert "mutable_default" not in ids(src)


def test_mutable_default__immutable_default_is_silent():
    src = "def f(x, n=0):\n    return x + n\n"
    assert "mutable_default" not in ids(src)
