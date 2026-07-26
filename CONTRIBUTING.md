# Contributing to Platão — the proof gate

Platão is a completeness auditor. It would be its own worst finding if it accepted checks that don't prove they work. So contribution here is governed by one rule, enforced by CI:

**A check that cannot prove itself does not merge.**

This is not bureaucracy. Proving a check is the same discipline the tool asks of your code. If that feels heavy, that's the point — it's the culture the tool exists to spread.

## What every new check must ship with

A pull request that adds or changes a check **must** include all four, or CI fails it:

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

```
checks/
  no_swallowed_error.py         # the detector (deterministic, one clear rule)
  fixtures/
    swallowed_error__dirty.py   # HAS the defect
    swallowed_error__clean.py   # does NOT — the negative control
  tests/
    test_no_swallowed_error.py  # prove_effect + negative_control
```

```python
def test_prove_effect():
    findings = run_check("no_swallowed_error", "fixtures/swallowed_error__dirty.py")
    assert any(f.id == "no_swallowed_error" for f in findings)   # it catches it

def test_negative_control():
    findings = run_check("no_swallowed_error", "fixtures/swallowed_error__clean.py")
    assert not any(f.id == "no_swallowed_error" for f in findings)  # and stays quiet
```

## CI

On every PR, CI runs the proof of **every** check — new and existing. A new check without both a `prove_effect` and a `negative_control` fails the build. So does an existing check whose negative control starts firing (a regression toward false positives).

## Adding questions to the catalog

New questions are welcome — the catalog is meant to grow into a community-curated "senior code review checklist." A question that's genuinely general (something *your* tech lead always asks) is exactly what belongs here. Same gate applies: `CODE` questions need the two proofs; `JUDGMENT` questions need a clear rubric prompt plus example artifacts showing the verdict.

## License

By contributing you agree your work is released under the project's MIT license.
