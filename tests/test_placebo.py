"""Proofs for the anti-placebo checks. Each check: prove_effect (catches it) + negative_control (silent)."""

from __future__ import annotations

from platao import analyze_source


def ids(source: str, path: str = "module.py") -> set[str]:
    return {f.check_id for f in analyze_source(path, source)}


# ── not_stub ──────────────────────────────────────────────────────────────────────

def test_not_stub__pass_body_is_caught():
    assert "not_stub" in ids("def execute():\n    pass\n")


def test_not_stub__returns_success_is_caught():
    assert "not_stub" in ids("def deploy():\n    return True\n")


def test_not_stub__docstring_only_is_caught():
    assert "not_stub" in ids('def apply():\n    """does the thing"""\n')


def test_not_stub__real_work_is_silent():  # negative control
    src = "def execute():\n    result = do_work()\n    return result\n"
    assert "not_stub" not in ids(src)


def test_not_stub__ellipsis_is_honest():  # `...` declares "not here", not placebo
    assert "not_stub" not in ids("def execute():\n    ...\n")


def test_not_stub__notimplemented_is_honest():
    assert "not_stub" not in ids("def execute():\n    raise NotImplementedError\n")


def test_not_stub__honest_name_is_exempt():
    assert "not_stub" not in ids("def execute_noop():\n    pass\n")


def test_not_stub__override_noop_is_exempt():  # FP guard — explicit override of a hook to a no-op
    src = "from typing import override\nclass C:\n    @override\n    def persist(self):\n        pass\n"
    assert "not_stub" not in ids(src)


def test_not_stub__abstractmethod_pass_is_exempt():
    src = "from abc import abstractmethod\nclass C:\n    @abstractmethod\n    def deploy(self):\n        pass\n"
    assert "not_stub" not in ids(src)


def test_not_stub__non_action_name_is_ignored():
    # `parse` doesn't promise a side effect, so a trivial body isn't a placebo.
    assert "not_stub" not in ids("def parse():\n    return True\n")


# ── always_succeeds ───────────────────────────────────────────────────────────────

def test_always_succeeds__no_failure_path_is_caught():
    src = "def deploy():\n    step_one()\n    step_two()\n    return True\n"
    assert "always_succeeds" in ids(src)


def test_always_succeeds__with_raise_is_silent():  # negative control
    src = "def deploy():\n    step_one()\n    if broken():\n        raise RuntimeError('no')\n    return True\n"
    assert "always_succeeds" not in ids(src)


def test_always_succeeds__with_failure_return_is_silent():
    src = "def deploy():\n    step_one()\n    step_two()\n    if bad():\n        return False\n    return True\n"
    assert "always_succeeds" not in ids(src)


# ── assert_selfreport (test files only) ───────────────────────────────────────────

def test_assert_selfreport__success_attr_is_caught():
    src = "def test_it():\n    r = run()\n    assert r.success\n"
    assert "assert_selfreport" in ids(src, "tests/test_it.py")


def test_assert_selfreport__status_compare_is_caught():
    src = "def test_it():\n    r = run()\n    assert r.status == 'ok'\n"
    assert "assert_selfreport" in ids(src, "tests/test_it.py")


def test_assert_selfreport__real_oracle_is_silent():  # negative control
    src = "def test_it():\n    r = run()\n    assert r == 42\n"
    assert "assert_selfreport" not in ids(src, "tests/test_it.py")


def test_assert_selfreport__does_not_run_outside_tests():  # test-only gating
    src = "def helper():\n    assert obj.success\n"
    assert "assert_selfreport" not in ids(src, "src/helper.py")


# ── no_negative_control (test files only) ─────────────────────────────────────────

def test_no_negative_control__happy_path_only_is_caught():
    src = "def test_it():\n    r = run()\n    assert r.success\n"
    assert "no_negative_control" in ids(src, "tests/test_it.py")


def test_no_negative_control__with_raises_is_silent():  # negative control
    src = (
        "import pytest\n"
        "def test_it():\n    r = run()\n    assert r.success\n"
        "def test_bad():\n    with pytest.raises(ValueError):\n        run(bad=True)\n"
    )
    assert "no_negative_control" not in ids(src, "tests/test_it.py")


def test_no_negative_control__failure_named_test_is_silent():
    src = (
        "def test_ok():\n    r = run()\n    assert r.success\n"
        "def test_it_fails_on_bad_input():\n    r = run(bad=True)\n    assert not r.success\n"
    )
    assert "no_negative_control" not in ids(src, "tests/test_it.py")


# ── oracle_independent (asserts on a dict the test itself wrote) ────────────────────

def test_oracle_independent__self_written_dict_is_caught():
    src = ('def test_it():\n    state = {}\n    state["ok"] = True\n    assert state["ok"]\n')
    assert "oracle_independent" in ids(src, "tests/test_x.py")


def test_oracle_independent__asserting_sut_effect_is_silent():  # negative control
    # The SUT fills the dict; the test reads it — a legitimate oracle, not self-written.
    src = ('def test_it():\n    state = {}\n    run(state)\n    assert state["ok"]\n')
    assert "oracle_independent" not in ids(src, "tests/test_x.py")


def test_oracle_independent__spy_capture_is_silent():  # the calibration — nested write
    src = (
        'def test_it(monkeypatch):\n    captured = {}\n'
        '    def _spy(**kw):\n        captured["body"] = kw\n'
        '    monkeypatch.setattr(mod, "post", _spy)\n    run()\n'
        '    assert captured["body"] == {"x": 1}\n'
    )
    assert "oracle_independent" not in ids(src, "tests/test_x.py")
