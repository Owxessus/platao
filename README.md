# Platão

<img src="assets/athena-coin.jpg" align="right" width="108" alt="Athena — the sovereign OS Platão was extracted from">

**English · [Português](README.pt-BR.md)**

**Your AI said "done." Platão asks the boring questions a skeptical senior would — before you trust it.**

Platão is a deterministic completeness auditor for code (and for the code your AI agents write). It doesn't guess. It reads the actual syntax tree and answers questions like: *Is this wired, or is it dead code? Does this test prove behavior, or just that the file imports? Is "success" real, or is the pipeline structurally unable to fail?* — the exact ways a confident-but-wrong agent leaves work silently incomplete.

It runs as a CLI, a pre-commit hook, a CI gate, and — the point — an **MCP server** that any coding agent calls before it says "finished."

> **Two products, one philosophy.** Platão has a sibling, [Basanos](https://github.com/Owxessus/basanos) — the touchstone for UI wiring (does this button call a handler that actually exists and does something?). They ship separately and run standalone. Install both and Platão will pull Basanos in as one of its eyes. See [Running with Basanos](#running-with-basanos).

---

## 30 seconds

```bash
npm install -g platao          # or: pipx install platao
platao check src/service.py    # review one file your AI just wrote
platao sweep .                 # scan the whole repo for placebo tests & dead code
```

```
Platão — src/service.py
  ⚠ CRITICAL [wired]        nobody imports 'service' — island code (wire it, or it's dead)
  ⚠ CRITICAL [has_effect]   'process()' is tested but the test never asserts on it — proves import, not effect
  · [debt_tracked]          2 TODOs without a trackable ID
  ✓ 9 checks passed
```

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

---

## Languages

Platão's **deep** checks — the placebo/completeness analysis and the import graph — read Python's AST, so they run on `.py`. On **any other language** (JS, TS, Go, Ruby, PHP, Java, …) it runs a **universal layer**: the checks that hold everywhere, matched robustly without a parser — an empty `catch` that swallows an error, dynamic `eval`, a debugger left in the code, an untracked `TODO`. So `platao check app.ts` is real, not a no-op.

That regex layer is deliberately shallow. For **deep** multi-language analysis there's an optional tree-sitter layer:

```bash
pip install 'platao[deep]'   # adds real ASTs for JS, TS, Go, Ruby, Java, Rust, PHP, C#, …
```

With it installed, deep structural checks run on those languages too — `not_stub` (an action-named function with a genuinely empty body, told apart from an honest abstract declaration) and `empty_test` (a JS/TS `it(...)`/`test(...)` whose body asserts nothing — the fake-test smell). The core stays zero-dependency without the extra; the polyglot regex layer still covers those files. More deep checks land as tree-sitter queries beside these. Today: deep in Python (always) and in the deep-layer languages (with the extra), broad everywhere.

## The questions

Every question is either `CODE` (deterministic, free) or `JUDGMENT` (needs an LLM). **All of them are opt-in** — enable the packs you want, disable the ones you don't, add your own. Defaults are the high-signal, low-false-positive set.

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

**Wiring (delegated to Basanos, if installed)**
- `ui_wired` — do this panel's controls call handlers that exist and do something?

### Judgment (JUDGMENT — BYO-LLM, opt-in)

- `momo_scrutiny` — **the flagship.** *Would a skeptical senior approve this, or dismantle it in 30 seconds? What do they attack first?*
- `real_or_mock` — is it real, or a mock with a real face?
- `edge_cases` — empty / null / boundary / large input / unicode / concurrent covered?
- `single_responsibility` — one responsibility, or a god-function forming?
- `reuse_over_create` — did you confirm nothing already does this (no duplication)?
- `abstraction_earns_keep` — does the abstraction have more than one caller?
- `simpler_version` — is there a simpler version that solves it the same?
- `hidden_magic` — hidden coupling/magic nobody can explain?

**Add your own in one line** (see [Configuration](#configuration)). Import your existing `CLAUDE.md` / `AGENTS.md` and Platão turns your house rules into questions.

---

## Usage modes (route by where the work happens)

You choose how it plugs in, and you can route by complexity — deterministic-only for cheap, quick checks; add the judgment layer only for complex or critical files.

| Mode | Command / setup | Best for |
|---|---|---|
| **CLI** | `platao check <path>` · `platao sweep .` | Manual, "did my AI actually finish?" |
| **Pre-commit hook** | `platao install-hook` | Block a commit on a critical concern |
| **CI gate (ratchet)** | GitHub Action | Fail the PR only if it **introduces** new placebo/dead code — never punishes old debt |
| **MCP server** ⭐ | `platao mcp` | Any agent (Claude Code, Cursor, …) calls it before saying "done" |
| **SDK** | `import platao` | Your own tooling |

The **MCP server** is the point. It exposes two tools — `platao_check` (audit a file or directory) and `platao_list_checks` — so any MCP-capable agent verifies its own work before claiming completion, no editor integration required. Install the extra and run it:

```bash
pip install 'platao[mcp]'
platao mcp        # stdio server; point your agent at it
```

---

## Cost & model routing

**The deterministic floor is $0, always, and runs on every check.** This section is only about the opt-in judgment layer, which uses whatever LLM you point it at — **you pick the model, and you can route by complexity** (cheap model or floor-only for simple diffs; a premium model for critical files).

### The token model (measured, reproducible)

A judgment review sends: a short preamble + the file under review (capped at **12,000 characters** — this caps your worst-case cost) + the enabled judgment questions. Measured on a representative ~440-line file with 12 questions enabled:

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

A `.platao.yml` for enabling/disabling questions and packs is **planned**; today, use the flags above and `list-checks`. The shape it will take:

Everything is opt-in via `.platao.yml` at your repo root. No file = sensible defaults (the high-signal deterministic set, judgment off).

```yaml
# .platao.yml
judge:
  enabled: false            # opt into the LLM layer explicitly
  model: deepseek-v3.2      # you pick the brain
  # api_key: env(OPENROUTER_API_KEY)   # BYO — never stored by Platão

questions:
  packs:                    # turn whole groups on/off
    connected: true
    placebo: true
    robustness: true
    hygiene: true
    judgment: false         # the BYO-LLM group
  disable: [typed_documented]   # drop individual questions you don't want
  import: [CLAUDE.md]           # turn your own house rules into questions

# Add a question in one line — id, the prompt, whether it's CODE or JUDGMENT, severity.
custom:
  - id: no_console_log
    kind: CODE
    severity: low
    detect: 'console\.log'    # simple pattern, or point to a checker module
    prompt: "Left a console.log behind?"
```

---

## Running with Basanos

[Basanos](https://github.com/Owxessus/basanos) is a separate product. If it's installed, Platão's `ui_wired` question lights up and delegates to it automatically — no config. If it isn't, the question quietly disappears (feature-detected, never an error). That's the "two products, run together" model: each stands alone; installed together, Platão is the interrogator and Basanos is its wiring eye.

```bash
npm install -g platao basanos    # both → Platão pulls Basanos as an eye
```

---

## Contributing — the rigid gate

**Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR.** Every contributed check must pass a rigorous proof or it does not merge — no exceptions, enforced by CI:

1. **Deterministic** — a `CODE` check uses no LLM.
2. **Proven** — it ships with `prove_effect` (it catches the target on a fixture that has the defect) **and** `negative_control` (it stays silent on clean code — no false positive).
3. **Declared severity.**
4. **"Detect easier than produce"** — the check to find the problem must be simpler than the code that has it. A validator you can't trust doesn't ship.

CI runs each check's proof on every PR. No proof, no merge. This isn't bureaucracy — it *is* the product. A completeness auditor that accepts unproven checks would be its own worst finding.

---

## Where this came from

Platão is one entity extracted from **Athena**, a sovereign agentic OS built on a single discipline: **anti-placebo, secure, deterministic, governed, auditable.** In Athena, "did you actually finish?" isn't a linter you run — it's a reflex the system performs on itself, every time it builds something, wired to dozens of complementary entities that heal, gate, remember, and prove.

What you're holding is roughly **1% of that** — the deterministic half of one of those entities, given away on its own. We open-sourced it because the failure mode it prevents — confident, incomplete, unverified work — is everyone's problem now that agents write so much of our code, and this piece is genuinely useful standalone.

The rest — the judgment orchestration, the security gates, the memory, the self-healing, the governance that decides what an agent is even allowed to do — is the part that isn't a tool. It's an architecture. If the questions in this README made you curious what it looks like when a system asks them *of itself*, that's the right instinct. More on that when it's ready.

For now: this stands on its own. Use it.

---

## License

MIT. Contributions under the same, plus the [CONTRIBUTING.md](CONTRIBUTING.md) proof gate.
