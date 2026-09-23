# Example: a build-and-audit agent (Claude Code + MCP)

A minimal, runnable example of the point of these tools: **an agent that isn't allowed to say "done"
until it has proven its work.** It wires both MCP servers — Platão (completeness) and Basanos (UI
wiring) — into a Claude Code project and gives the agent one rule: *build, then audit, then fix, and
only then finish.*

This is the generate → **audit** → fix loop, with a deterministic auditor closing it instead of the
agent's own optimism.

---

## What's here

```
examples/agent/
  .mcp.json                        # registers the platao + basanos MCP servers
  .claude/agents/builder-auditor.md  # a subagent that must audit before saying "done"
  CLAUDE.md                        # the project rule: no "done" without a clean audit
  demo/
    pkg/service.py                 # a Python service that LOOKS finished and isn't
    pkg/db.py
    ui/Cart.tsx                    # a React component with a dead button
```

The two `demo/` files are seeded with the exact defects these tools catch, so you can watch them fire
on the first run.

---

## Setup (once)

Install the two tools so `.mcp.json` can launch them:

```bash
pipx install 'platao[mcp] @ git+https://github.com/Owxessus/platao'   # not on PyPI yet
npm install -g basanos
```

Then, from **this directory** (`examples/agent/`), start Claude Code — it reads `.mcp.json` and
`.claude/` from the working directory:

```bash
cd examples/agent
claude
```

> **Not using Claude Code?** The servers are plain MCP over stdio, so any MCP client works. Register
> them by hand with `claude mcp add platao -- platao mcp` and `claude mcp add basanos -- basanos mcp`,
> or from source with `... -- python -c "from platao.mcp_server import run; run()"` (with `src/` on
> `PYTHONPATH`) and `... -- node dist/cli.js mcp`.

---

## Run it

Ask the `builder-auditor` agent to finish the demo:

> Finish the order service in `demo/pkg/service.py` and the cart UI in `demo/ui/Cart.tsx`.

It will write code, then call `platao_check` and `basanos_audit` — and refuse to report "done" while
anything is red. You can also just run the auditors yourself to see what the agent sees:

```bash
platao sweep demo/pkg
```

```
Platão — demo/pkg/service.py
  ⚠ [dangling_import]  `from pkg.db import connect` — 'connect' is not defined or re-exported in module 'pkg.db'
  ⚠ [not_stub]  'process_order' just returns success without doing the work
  • [swallowed_error]  except Exception swallows the error silently (body is just `pass`) — no log, no re-raise
  · [unwired]  module 'pkg.service' is imported by nobody in the scanned tree — dead code, or public API used only by downstream consumers (eyeball it)
  · [debt_tracked]  untracked TODO — add an owner or issue ref, e.g. TODO(#123)

2 critical · 1 concern · 2 note
```

```bash
basanos audit demo/ui/Cart.tsx
```

```
  [x] DEAD  onClick={checkout}  — handler 'checkout' does not resolve to a real function (dead control)
  [!] STUB  onClick={() => {}}  — handler has an empty body (the control does nothing)

1 dead . 1 stub
```

Two `critical`/`DEAD` findings are the ones that block completion: a broken import, a function that
claims success while doing nothing, and a button wired to a handler that doesn't exist. A well-behaved
agent fixes those and re-audits before it says a word about being finished.

---

## The whole idea in one line

The agent writes the code. The **deterministic auditor decides whether it's real** — not the model's
confidence. That's the loop, and it's why the audit call is a rule, not a suggestion.
