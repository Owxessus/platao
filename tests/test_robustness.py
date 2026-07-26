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
