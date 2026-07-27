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


# ── hardcoded_secret (Python AST; value NEVER emitted) ─────────────────────────────

def _findings(source, path="module.py"):
    return analyze_source(path, source)


def test_hardcoded_secret__literal_is_caught():
    assert "hardcoded_secret" in ids('API_KEY = "sk-live-abcdef123456"\n')


def test_hardcoded_secret__value_is_never_emitted():  # segredo nunca em output
    fs = [f for f in _findings('password = "hunter2-supersecret"\n') if f.check_id == "hardcoded_secret"]
    assert fs
    blob = (fs[0].message + " " + fs[0].snippet).lower()
    assert "hunter2" not in blob and "supersecret" not in blob
    assert "<redacted>" in fs[0].snippet


def test_hardcoded_secret__env_lookup_is_silent():  # the correct idiom
    assert "hardcoded_secret" not in ids('import os\nAPI_KEY = os.environ["API_KEY"]\n')


def test_hardcoded_secret__placeholder_is_medium_not_high():
    fs = [f for f in _findings('api_key = "your-api-key-here"\n') if f.check_id == "hardcoded_secret"]
    assert fs and fs[0].severity is Severity.MEDIUM


def test_hardcoded_secret__non_secret_name_is_silent():
    assert "hardcoded_secret" not in ids('greeting = "hello there friend"\n')


def test_hardcoded_secret__short_value_is_silent():
    assert "hardcoded_secret" not in ids('token = "abc"\n')


# ── fail_closed (guard that fails OPEN on error) ───────────────────────────────────

def test_fail_closed__guard_returns_true_on_except_is_caught():
    src = ("def is_authorized(user):\n    try:\n        return check(user)\n"
           "    except Exception:\n        return True\n")
    assert "fail_closed" in ids(src)


def test_fail_closed__validate_returning_ok_on_except_is_caught():
    src = ('def validate_token(t):\n    try:\n        return verify(t)\n'
           '    except Exception:\n        return "allow"\n')
    assert "fail_closed" in ids(src)


def test_fail_closed__guard_returns_false_is_silent():  # fails closed = correct
    src = ("def is_authorized(user):\n    try:\n        return check(user)\n"
           "    except Exception:\n        return False\n")
    assert "fail_closed" not in ids(src)


def test_fail_closed__guard_reraises_is_silent():
    src = ("def is_authorized(user):\n    try:\n        return check(user)\n"
           "    except Exception:\n        raise\n")
    assert "fail_closed" not in ids(src)


def test_fail_closed__non_guard_name_is_silent():  # not a gate — the name proxy
    src = ("def load_cache(user):\n    try:\n        return fetch(user)\n"
           "    except Exception:\n        return True\n")
    assert "fail_closed" not in ids(src)


def test_fail_closed__narrow_except_is_silent():
    src = ("def is_authorized(user):\n    try:\n        return check(user)\n"
           "    except KeyError:\n        return True\n")
    assert "fail_closed" not in ids(src)


def test_hardcoded_secret__label_word_is_not_a_secret():  # FP guard (hermes-agent CREDENTIAL="credential")
    assert "hardcoded_secret" not in ids('CREDENTIAL = "credential"\n')
    assert "hardcoded_secret" not in ids('token = "placeholder"\n')  # plain word, no entropy


def test_fail_closed__value_resolver_returning_true_is_silent():  # FP guard (hermes _resolve_aux_verify)
    # Returns a TLS-verify SETTING where True is the secure value — it fails closed, not open.
    src = ("def _resolve_aux_verify(url):\n    try:\n        return resolve_tls(url)\n"
           "    except Exception:\n        return True\n")
    assert "fail_closed" not in ids(src)
