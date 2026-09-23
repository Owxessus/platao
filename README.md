# Platão

<img src="assets/banner.png" alt="Platão — extracted from Athena, the sovereign agentic OS">

[![ci](https://github.com/Owxessus/platao/actions/workflows/ci.yml/badge.svg)](https://github.com/Owxessus/platao/actions/workflows/ci.yml) [![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE) [![python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

**English · [Português](README.pt-BR.md)**

**Your AI said "done." Platão asks the boring questions a skeptical senior would — before you trust it.**

Platão is a deterministic completeness auditor for code (and for the code your AI agents write). It doesn't guess. It reads the actual syntax tree and answers questions like: *Is this wired, or is it dead code? Does this test prove behavior, or just that the file imports? Is "success" real, or is the pipeline structurally unable to fail?* — the exact ways a confident-but-wrong agent leaves work silently incomplete.

It runs as a CLI, a pre-commit hook, a CI gate, and — the point — an **MCP server** that any coding agent calls before it says "finished."

## Built for the loop, not the post-mortem

Platão isn't a linter you run on finished code — it's the check an agent runs **while it builds**. Point it at the diff it just wrote; it answers in milliseconds, deterministically; the agent reads the answer and **fixes it before moving on — and before it declares "done."** The failure it exists to stop isn't ugly code; it's an agent *saying it finished when it didn't* — a module half-wired, an orphan event, a "success" the pipeline structurally can't fail, a test that only proves the file imports.

**Primary use — the agent's self-check (MCP).** Run Platão as an **MCP server** inside your coding agent's loop: the agent calls it after each chunk and can't claim "finished" while a completeness check is red. (Also a CLI, pre-commit hook, and CI gate — the same check, run earlier.)

**Who it helps most: weaker, cheaper, autonomous models.** A frontier model already *tries* to wire what it writes. Platão's value is catching the moments a model **thinks** it finished but didn't — and that gap is widest on **cheap models running long, on their own, with nobody watching.** The floor is deterministic and costs far less than generating the code, so it's viable to run on every step. On a top model it's a light seatbelt; on a cheap autonomous one it's what keeps the work honest.

> **One of three, one philosophy.** Platão has two siblings: **[Basanos](https://github.com/Owxessus/basanos)** — the touchstone for UI wiring (does this button call a handler that exists and does something?) — and **[Socrates](https://github.com/Owxessus/socrates)** — the cross-examiner (do your tests actually catch bugs, and does your public API have proof?). Each ships separately and runs standalone. **Install any of them alongside Platão and it pulls them in as extra eyes** — Basanos answers `ui_wired`, Socrates answers `capabilities_proven` — folded into the same report. See [Running with its siblings](#running-with-its-siblings).

---

## 30 seconds

<img src="assets/demo.svg" alt="Platão — a real run: type the command, see the real output" width="640">

```bash
pipx install "platao[mcp,deep] @ git+https://github.com/Owxessus/platao"   # not on PyPI yet
platao check src/service.py    # review one file your AI just wrote
platao sweep .                 # scan the whole repo for placebo tests & dead code
```

```
Platão — src/service.py
  ⚠ [not_stub]          'process_order' just returns success without doing the work
  • [swallowed_error]   except Exception swallows the error silently (body is just `pass`)
  · [debt_tracked]      untracked TODO — add an owner or issue ref, e.g. TODO(#123)

1 critical · 1 concern · 1 note
```

`sweep` sees across files too — a broken `from .db import connect` (`dangling_import`) or a module nobody imports (`unwired`) only a whole-repo pass can catch.

That's the **free, offline, deterministic floor** — no API key, no network, no LLM. It runs the same way every time and it does not hallucinate, because it *knows* via the AST rather than *guessing* via a model.

The optional **judgment ceiling** (`--judge`) adds the skeptical-senior layer — see [The two layers](#the-two-layers).

---

## Why this exists

Coding agents fail in a specific, recognizable way: **confident but wrong, and silently incomplete.** They write a function nobody calls. They write a test that imports the target and asserts nothing. They emit `event_completed` from a function with an empty body. They say "done" and mean it — and you find out three commits later.

Every check in Platão is a question a senior developer keeps asking a junior after each piece of work. We captured that checklist and made a machine ask it, every time, for free.

**The frame is "obligation, not feature."** A linter is something you can turn off. This is closer to a tribunal — you don't get to switch off the questions just because you're in a hurry. That's the whole point: the moment it's optional-when-inconvenient, the failure mode it prevents comes right back.

---

## The two layers

Platão is deliberately split so the trustworthy part is always on and the expensive part is always your choice.

| Layer | What it is | Cost | Network | Hallucinates? |
|---|---|---|---|---|
| **Deterministic floor** (default) | AST/static checks: wired? orphan? real test? placebo? debt tracked? | **$0** | Offline | **No** — it reads the tree |
| **Judgment ceiling** (`--judge`, opt-in) | The skeptical senior: *would a cynic approve this or tear it apart in 30s?* | Your LLM bill | Your provider | Yes (it's an LLM) — so it's advisory, never the gate |

The floor is what makes Platão trustworthy. The ceiling is what makes it *smart* about things a tree can't see (a mock wearing a real face, an abstraction with no caller). **The ceiling is BYO-LLM** — you bring your own API key or a local model. Platão gives you the *questions and the rubric*; you choose the brain. See [Cost & model routing](#cost--model-routing).

**In the agent loop, the ceiling is a generator–critic move — not a redundant LLM pass.** Verification is cheaper than generation, so a *weak, cheap generator* paired with a skeptical critic beats the generator alone. The point is asymmetry: let the ceiling be a **different or stronger model than the one writing the code**, and run it at **checkpoints** (*"I think this module is done"*) — never per-keystroke, where an LLM call would cost more than it saves. On a frontier generator the ceiling is marginal; on a cheap one running autonomously it's real leverage — the second opinion that stops the cheap model from believing its own first draft.

---

## Languages

Platão's **deep** checks — the placebo/completeness analysis and the import graph — read Python's AST, so they run on `.py`. On **any other language** (JS, TS, Go, Ruby, PHP, Java, …) it runs a **universal layer**: the checks that hold everywhere, matched robustly without a parser — an empty `catch` that swallows an error, dynamic `eval`, a debugger left in the code, an untracked `TODO`. So `platao check app.ts` is real, not a no-op.

That regex layer is deliberately shallow. For **deep** multi-language analysis there's an optional tree-sitter layer:

```bash
pip install 'platao[deep] @ git+https://github.com/Owxessus/platao'   # real ASTs for JS, TS, Go, Ruby, Java, Rust, PHP, C#, …
```

With it installed, deep structural checks run on those languages too — `not_stub` (an action-named function with a genuinely empty body, told apart from an honest abstract declaration) and `empty_test` (a JS/TS `it(...)`/`test(...)` whose body asserts nothing — the fake-test smell). The core stays zero-dependency without the extra; the polyglot regex layer still covers those files. More deep checks land as tree-sitter queries beside these. Today: deep in Python (always) and in the deep-layer languages (with the extra), broad everywhere.

## The questions

Every question is either `CODE` (deterministic, free) or `JUDGMENT` (needs an LLM). **Every deterministic check runs by default; switch any one off by id** in [`.platao.json`](#config-file) (question packs and your own questions are planned). Defaults are the high-signal, low-false-positive set — calibrated against mature real-world repos (`requests`, `flask`, `click`, …) so it stays quiet on idiomatic code and loud on genuine defects.

> **What ships today vs. the roadmap.** The list below is the full checklist Platão is built around. The checks **live in this release** are exactly what `platao list-checks` prints — today the connected / placebo / robustness / hygiene core (`not_stub`, `dangling_import`, `unwired`, `swallowed_error`, `dangerous_dynamic`, `mutable_default`, `hardcoded_secret`, `fail_closed`, `not_god_function`, `debt_tracked`, `debug_leftover`, and the placebo-test checks), the deep `not_stub`/`empty_test` for other languages via `platao[deep]`, plus the nine `momo` judgment questions. The rest is the roadmap — each lands under the same proof gate (see [Contributing](#contributing--the-rigid-gate)). **Run `platao list-checks` for the authoritative set in your version.**

### Deterministic (CODE — free, offline)

**Is it connected?**
- `wired` — called/imported, or dead-code island?
- `orphan_output` — is what it produces (event/export/return/endpoint) consumed anywhere?
- `dangling_ref` — does it reference things that actually exist in the repo?
- `api_exists` — does it call methods/fields that exist on the *real* target, not just on a mock?

**Is it real, or placebo?**
- `has_effect_test` — a test that **asserts behavior** (imports + asserts), not just that it imports/renders?
- `oracle_independent` — does the test check an independent oracle, not the code's own self-report?
- `negative_control` — is there a failure path tested — does it fail when it should?
- `can_fail` — can the pipeline fail (raise / error return / branch), or does it always return success?
- `not_stub` — does the announced function actually do something, not just `pass`/`return True`?
- `done_has_work` — is "completed/success" emitted after real work, not an empty body?

**Does it hold up?**
- `no_swallowed_error` — no `except`/`catch` swallowing errors in silence?
- `fail_closed` — in a gate/auth/validation, does an error deny (closed), not permit (open)?
- `resource_cleanup` — does it close what it opened (`with`/`finally`/`defer`)?

**Reproduces & ships?**
- `deps_declared` — every third-party import declared in `requirements`/`package.json`?
- `no_hardcoded_secret` — no key/token in code **or** logs?
- `no_hardcoded_path` — paths from config/arg, not baked in?
- `atomic_write` — file writes atomic (temp+replace), not corruptible mid-write?

**Hygiene & debt**
- `no_debug_leftover` — no stray `print`/`console.log`/`debugger`?
- `no_dangerous_dynamic` — no `eval`/`exec`/`shell` without scope validation?
- `debt_tracked` — every shortcut has a trackable `TODO`, not just in your head?
- `typed_documented` — public functions have types + docstring/JSDoc?
- `not_god_function` — function under ~120 lines / one logical stage?

**Delegated to a sibling, if installed**
- `ui_wired` — do this panel's controls call handlers that exist and do something? (**Basanos**)
- `capabilities_proven` — is every public capability named by at least one test? (**Socrates**)

### Judgment (JUDGMENT — BYO-LLM, opt-in)

- `momo_scrutiny` — **the flagship.** *Would a skeptical senior approve this, or dismantle it in 30 seconds? What do they attack first?*
- `real_or_mock` — is it real, or a mock with a real face?
- `edge_cases` — empty / null / boundary / large input / unicode / concurrent covered?
- `failure_path` — is the failure path handled, not just the happy one?
- `single_responsibility` — one responsibility, or a god-function forming?
- `reuse_over_create` — did you confirm nothing already does this (no duplication)?
- `abstraction_earns_keep` — does the abstraction have more than one caller?
- `simpler_version` — is there a simpler version that solves it the same?
- `hidden_magic` — hidden coupling/magic nobody can explain?

**Planned:** add your own question in one line, and import your existing `CLAUDE.md` / `AGENTS.md` so your house rules become questions (see [Configuration](#configuration)).

---

## Usage modes (route by where the work happens)

You choose how it plugs in, and you can route by complexity — deterministic-only for cheap, quick checks; add the judgment layer only for complex or critical files.

| Mode | Command / setup | Best for |
|---|---|---|
| **CLI** | `platao check <path>` · `platao sweep .` | Manual, "did my AI actually finish?" |
| **Pre-commit hook** | `platao install-hook` | Block a commit on a critical concern |
| **CI gate** | GitHub Action (`uses: Owxessus/platao@main`) | Fail the build on findings at or above `--fail-on` (a new-only ratchet is planned) |
| **MCP server** ⭐ | `platao mcp` | Any agent (Claude Code, Cursor, …) calls it before saying "done" |
| **SDK** | `import platao` | Your own tooling |

The **MCP server** is the point. It exposes two tools — `platao_check` (audit a file or directory) and `platao_list_checks` — so any MCP-capable agent verifies its own work before claiming completion, no editor integration required. Install the extra and run it:

```bash
pip install 'platao[mcp] @ git+https://github.com/Owxessus/platao'
platao mcp        # stdio server; point your agent at it
```

There's a complete, runnable **build-and-audit agent** in [`examples/agent/`](examples/agent/): a Claude Code project that wires both Platão and Basanos as MCP servers and gives an agent one rule — *build, then audit, then fix, and only then say "done"*. It ships with seeded-broken demo files so you watch the tools fire on the first run.

---

## Cost & model routing

**The deterministic floor is $0, always, and runs on every check.** This section is only about the opt-in judgment layer, which uses whatever LLM you point it at — **you pick the model, and you can route by complexity** (cheap model or floor-only for simple diffs; a premium model for critical files).

### The token model (measured, reproducible)

A judgment review sends: a short preamble + the file under review (capped at **12,000 characters** — this caps your worst-case cost) + the enabled judgment questions. Measured on a representative ~440-line file with 12 questions enabled (9 ship today, so the real output is a little smaller):

- **Input:** ≈ 3,500 tokens
- **Output:** ≈ 750 tokens (one line per question)

**Cost per review = `3500/1e6 × price_in + 750/1e6 × price_out`.** Plug in any provider's price. Small files cost ~40–50% of this; the 12k-char cap is the ceiling.

### Ready reckoner (~10 tiers)

Prices as of **2026-06-24**; LLM pricing drifts — **verify current rates at your provider.** Anthropic rows are exact from the official table; third-party rows are approximate and marked ≈.

| Tier | Model | $/1M in | $/1M out | **Cost / review** | 1,000 reviews |
|---|---|---|---|---|---|
| Local | Ollama (gemma/qwen/llama) | — | — | **$0** (your hardware) | $0 |
| Ultra-cheap | DeepSeek-V3.2 ≈ | ≈0.28 | ≈0.42 | ≈ $0.0013 | ≈ $1.3 |
| Cheap | Gemini Flash-class ≈ | ≈0.10 | ≈0.40 | ≈ $0.0007 | ≈ $0.7 |
| Cheap | GPT-mini-class ≈ | ≈0.15 | ≈0.60 | ≈ $0.0010 | ≈ $1.0 |
| Budget | **Claude Haiku 4.5** | 1.00 | 5.00 | **$0.0073** | $7.3 |
| Mid | Qwen/Llama-70B hosted ≈ | ≈0.40 | ≈0.40 | ≈ $0.0017 | ≈ $1.7 |
| Balanced | **Claude Sonnet 5** (intro) | 2.00 | 10.00 | **$0.0145** | $14.5 |
| Balanced | **Claude Sonnet 5** (std) | 3.00 | 15.00 | **$0.0218** | $21.8 |
| Premium | **Claude Opus 5** | 5.00 | 25.00 | **$0.0363** | $36.3 |
| Top | **Claude Fable 5** | 10.00 | 50.00 | **$0.0725** | $72.5 |

Notes for total honesty:
- **Caching doesn't help here.** The file body changes every review; only the small preamble+questions (~500 tokens) is stable, below the cache floor. No cache discount claimed.
- A verbose review (a full paragraph per question) can roughly double the output cost. Still cents.
- **Routing:** configure a cheap model for `platao check` on every save and a premium one only for `--judge` on critical paths, or run **floor-only** (free) and reserve judgment for when you actually want the senior's eye.

---

## Configuration

### Judgment (opt-in, BYO-LLM)

The skeptical-senior layer is off until you ask for it and point it at a model. It's BYO-LLM — any OpenAI-compatible endpoint (OpenAI, OpenRouter, DeepSeek, a local Ollama):

```bash
export PLATAO_JUDGE_MODEL=gpt-4o-mini          # your model
export PLATAO_JUDGE_API_KEY=sk-...             # your key — Platão reads it from the env, never stores it
export PLATAO_JUDGE_BASE_URL=https://api.openai.com/v1   # optional; defaults to OpenAI
platao check src/service.py --judge
```

Judgment is **advisory**: its findings are shown but **do not drive the exit code** — the deterministic checks are the gate (you don't fail CI on an LLM's opinion). And if the model can't be reached, Platão says so with a `judge_unverified` finding — it never silently reports "all good".

### Config file

Turn specific checks off with a `.platao.json` at your repo root (zero-dependency, real today). No file = nothing disabled:

```json
{ "disable": ["debt_tracked", "not_god_function"] }
```

When sweeping a tree, Platão walks past vendored and generated directories by default — `node_modules`, `.venv`/`venv`, `site-packages`, `build`/`dist`, the caches, and vendored-code dirs (`vendor`, `third_party`, `thirdparty`, …). Code you didn't write isn't yours to audit. (Point the tool straight at one of those dirs to override.)

Run `platao list-checks` to see every id you can disable. A richer `.platao.yml` (question packs, importing your own `CLAUDE.md` as questions) is **planned** — the shape it will take:

```yaml
# .platao.yml (planned)
questions:
  packs: { connected: true, placebo: true, robustness: true, hygiene: true, judgment: false }
  disable: [typed_documented]
  import: [CLAUDE.md]      # turn your house rules into questions
```

---

## Running with its siblings

Platão is the interrogator; its siblings are extra eyes it grows when they're present. Both are **feature-detected and silent when absent** — no config, and a missing sibling never errors — and both stay within Platão's promise: they read your code, they never *run* your app.

- **[Socrates](https://github.com/Owxessus/socrates)** (Python — imported in-process). On a whole-repo `sweep`, Platão's `capabilities_proven` question lights up and asks Socrates: which public capabilities does no test name? Only Socrates' *static* capability-proof is delegated — its dynamic mutation testing (`socrates mutate`) you run explicitly, so Platão stays "never executes your code".

  ```bash
  pipx install "platao @ git+https://github.com/Owxessus/platao"   # then, in the same environment:
  pip install socrates-oss     # sweep now includes capabilities_proven
  ```

- **[Basanos](https://github.com/Owxessus/basanos)** (a Node CLI — shelled out to). If `basanos` is on your PATH, Platão's `ui_wired` question delegates to it and folds dead/stub UI controls into the report.

  ```bash
  npm install -g basanos       # sweep now includes ui_wired
  ```

Each stands alone; installed together, Platão gathers all three answers into one pass.

---

## Contributing — the rigid gate

**Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR.** Every contributed check must pass a rigorous proof or it does not merge — no exceptions, enforced by CI:

1. **Deterministic** — a `CODE` check uses no LLM.
2. **Proven** — it ships with `prove_effect` (it catches the target on a fixture that has the defect) **and** `negative_control` (it stays silent on clean code — no false positive).
3. **Declared severity.**
4. **"Detect easier than produce"** — the check to find the problem must be simpler than the code that has it. A validator you can't trust doesn't ship.

CI runs each check's proof on every PR. No proof, no merge. This isn't bureaucracy — it *is* the product. A completeness auditor that accepts unproven checks would be its own worst finding.

---

## Proven, not asserted

Anti-placebo is a rule this project holds *itself* to. **Every check ships with a `prove_effect` + `negative_control` pair** — it must catch the real defect *and* stay silent on the honest twin, or it doesn't ship (CI enforces it). And it passes its own audit — Platão runs **clean under its own `platao sweep`** — the auditor survives its own audit.

Then it was hardened on **real codebases, 10k–90k★**, across every tier — big-tech, frameworks, AI-agent projects, solo work. On that gauntlet it found real defects the test suites missed — dozens of module-level broken imports that a 67k★ project's test suite never caught (latent `ImportError`s on real code paths) — and, the harder half, it **stayed quiet where the code was good.** Every false-positive pattern it tripped on became a fix with a regression test: **15 classes of false positive eliminated** on real code. A low false-positive rate isn't a promise here — it was *built*.

## Where this came from

Platão is one entity extracted from **Athena**, a sovereign agentic OS built on a single discipline: **anti-placebo, secure, deterministic, governed, auditable.** In Athena, "did you actually finish?" isn't a linter you run — it's a reflex the system performs on itself, every time it builds something, wired to dozens of complementary entities that heal, gate, remember, and prove.

What you're holding is roughly **1% of that** — the deterministic half of one of those entities, given away on its own. We open-sourced it because the failure mode it prevents — confident, incomplete, unverified work — is everyone's problem now that agents write so much of our code, and this piece is genuinely useful standalone.

The rest — the judgment orchestration, the security gates, the memory, the self-healing, the governance that decides what an agent is even allowed to do — is the part that isn't a tool. It's an architecture. If the questions in this README made you curious what it looks like when a system asks them *of itself*, that's the right instinct. More on that when it's ready.

For now: this stands on its own. Use it.

---

Athena is that discipline as a *system*, not a tool: every action passes a **decision gate** before it runs, a **sandbox** that can roll back before anything destructive, and a **tamper-evident ledger** that records what happened; memory is written only through a guardian that hashes every record; reasoning is cloud-first but the **data stays sovereign** — nothing leaves without clearing the egress gates. Platão is ~1% of it — the organ that answers *"is this actually done — wired, real, and unable to fake success?"* — carved out to run standalone, in your own agent's loop, with no strings to the rest.

**The point isn't the linter; it's the reflex** — an agent that refuses to say it finished when it didn't. If a $0, never-wrong verifier of that kind is useful to you, that reflex is the whole of Athena: governed, auditable, self-defending. This tool is the doorway; Athena is the room.

## License

MIT. Contributions under the same, plus the [CONTRIBUTING.md](CONTRIBUTING.md) proof gate.
