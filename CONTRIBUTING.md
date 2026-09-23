# Contributing to Platão — the proof gate

Platão is a completeness auditor. It would be its own worst finding if it accepted checks that don't prove they work. So contribution here is governed by one rule, held in review and backed by CI:

**A check that cannot prove itself does not merge.**

This is not bureaucracy. Proving a check is the same discipline the tool asks of your code. If that feels heavy, that's the point — it's the culture the tool exists to spread.

## What every new check must ship with

A pull request that adds or changes a check **must** include all four, or it does not merge:

### 1. It is deterministic (for CODE checks)
A `CODE` check uses no LLM, no network, no randomness. Same input → same output, always. If your idea genuinely needs judgment, it's a `JUDGMENT` check (BYO-LLM) and lives in the judgment pack — different rules, still needs a rubric and examples.

### 2. `prove_effect` — it catches the target
A test fixture that **has the defect**, and an assertion that your check **fires** on it. If your check claims to find island code, ship a file that is island code and prove the check reports it.

### 3. `negative_control` — it stays silent on clean code
A fixture that is **clean** (does not have the defect), and an assertion that your check **does not fire**. A check with no negative control is a false-positive generator waiting to happen. This is the half most linters skip, and the half we require.

### 4. Declared severity
`low` | `medium` | `high`. Be honest. `high` is for defects that break behavior, not for style preferences.

## The law: "detect easier than produce"

The code that **detects** the problem must be simpler than the code that **has** the problem. If verifying a property is as hard as getting it right in the first place, the check can't be trusted — a validator you can't verify is worse than none. If your detector is a 300-line heuristic to catch a 10-line smell, it will misfire on real code. Simplify it or withdraw it.

## Example: the shape of a good check

A check is a generator in `src/platao/checks/<category>.py`, registered by its decorator; its proofs
live in `tests/test_<category>.py`, with the fixture source inline:

```python
# src/platao/checks/robustness.py — the detector (deterministic, one clear rule)
@register("swallowed_error", "robustness", Severity.MEDIUM)
def swallowed_error(ctx: FileContext):
    for node in ast.walk(ctx.tree):
        if isinstance(node, ast.ExceptHandler) and ...:   # a broad except whose body is just `pass`
            yield (node.lineno, "except swallows the error silently — no log, no re-raise")
```

```python
# tests/test_robustness.py
from platao import analyze_source

def ids(src: str) -> set[str]:
    return {f.check_id for f in analyze_source("module.py", src)}

def test_swallowed_error__bare_except_pass_is_caught():       # prove_effect
    assert "swallowed_error" in ids("def f():\n    try:\n        risky()\n    except:\n        pass\n")

def test_swallowed_error__logged_and_reraised_is_silent():    # negative_control
    src = "def f():\n    try:\n        risky()\n    except Exception:\n        log(); raise\n"
    assert "swallowed_error" not in ids(src)
```

## CI

On every PR, CI runs the proof of **every** check — new and existing — plus the linter and Platão's
audit of its own source. An existing check whose negative control starts firing (a regression toward
false positives) fails the build. That a *new* check ships both proofs is held in review: a PR
without them is not merged.

## Adding questions to the catalog

New questions are welcome — the catalog is meant to grow into a community-curated "senior code review checklist." A question that's genuinely general (something *your* tech lead always asks) is exactly what belongs here. Same gate applies: `CODE` questions need the two proofs; `JUDGMENT` questions need a clear rubric prompt plus example artifacts showing the verdict.

## License

By contributing you agree your work is released under the project's MIT license.
