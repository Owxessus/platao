"""Proofs for the language-agnostic layer. Each pattern: prove_effect + negative_control."""

from __future__ import annotations

from platao.finding import Severity
from platao.polyglot import scan


def ids(source: str, path: str = "app.ts") -> set[str]:
    return {f.check_id for f in scan(path, source)}


# ── swallowed_error (empty catch) ─────────────────────────────────────────────────

def test_empty_catch_is_caught():
    assert "swallowed_error" in ids("try { risky() } catch (e) {}")


def test_empty_catch_is_medium():  # parity with Python `except Exception: pass` — advisory, not a hard fail
    f = next(x for x in scan("app.ts", "try { risky() } catch (e) {}") if x.check_id == "swallowed_error")
    assert f.severity is Severity.MEDIUM


def test_empty_catch_multiline_is_caught():
    assert "swallowed_error" in ids("try {\n  risky()\n} catch (e) {\n\n}")


def test_handled_catch_is_silent():  # negative control
    assert "swallowed_error" not in ids("try { risky() } catch (e) { log(e); throw e; }")


# ── dangerous_dynamic ─────────────────────────────────────────────────────────────

def test_eval_is_caught():
    assert "dangerous_dynamic" in ids("const x = eval(userInput);")


def test_new_function_is_caught():
    assert "dangerous_dynamic" in ids("const f = new Function('return 1');")


def test_no_dynamic_is_silent():  # negative control
    assert "dangerous_dynamic" not in ids("const x = evaluate(input);")


# ── debug_leftover ────────────────────────────────────────────────────────────────

def test_debugger_is_caught():
    assert "debug_leftover" in ids("function f() {\n  debugger;\n  return 1;\n}")


def test_ruby_byebug_is_caught():
    assert "debug_leftover" in ids("def f\n  byebug\n  do_thing\nend", "app.rb")


def test_no_debugger_is_silent():  # negative control
    assert "debug_leftover" not in ids("function f() { return debuggerName; }")


# ── debt_tracked (comment-aware, cross-language) ──────────────────────────────────

def test_bare_todo_in_js_comment_is_caught():
    assert "debt_tracked" in ids("// TODO fix this later\nconst x = 1;")


def test_todo_with_issue_is_silent():  # negative control
    assert "debt_tracked" not in ids("// TODO fix later, see #42\nconst x = 1;")


def test_todo_with_owner_is_silent():
    assert "debt_tracked" not in ids("// TODO(alice) fix later\nconst x = 1;")


# ── comment / string masking (regex FP guards, from vite) ─────────────────────────

def test_eval_in_line_comment_is_silent():  # vite: `// Most eval() calls are in this format`
    assert "dangerous_dynamic" not in ids("// Most eval() calls are in this format\nconst x = 1")


def test_eval_in_string_is_silent():
    assert "dangerous_dynamic" not in ids("const s = 'eval(untrusted)'\n")


def test_real_eval_still_caught_next_to_a_comment():  # prove_effect — masking didn't blind it
    assert "dangerous_dynamic" in ids("// call eval below\nconst r = eval(userInput)\n")


def test_empty_catch_in_block_comment_is_silent():
    assert "swallowed_error" not in ids("/* try { x } catch (e) {} */\nconst y = 2")


def test_debugger_in_string_is_silent():
    assert "debug_leftover" not in ids("const help = 'type debugger to break'\n")
