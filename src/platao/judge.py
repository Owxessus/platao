"""judge — the opt-in "skeptical senior" layer. BYO-LLM: you bring the key, Platão brings the questions.

The deterministic floor (the other checks) is what makes Platão trustworthy and free. This is the
ceiling: the questions a cynical senior keeps asking that a syntax tree can't answer — is this real
or a mock with a real face? would they approve it, or take it apart in 30 seconds? It sends the code
to whatever OpenAI-compatible model you point it at (OpenAI, OpenRouter, DeepSeek, a local Ollama —
your key, your model, your bill) and turns the answers into findings.

Zero dependencies — a stdlib ``urllib`` POST. Honest about its limits: if the model can't be reached
the run says so (a ``judge_unverified`` finding), it never silently reports "all good". Advisory by
design — judgment findings are shown but do not drive the CLI's exit code (you don't fail CI on an
LLM's opinion; the deterministic checks are the gate).
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from platao.finding import Finding, Severity

_SRC_CAP = 12000  # chars of source sent to the model — caps the worst-case token cost

# (id, prompt, severity). The captured "senior code review" checklist — generic, no house specifics.
JUDGE_QUESTIONS: list[tuple[str, str, Severity]] = [
    ("momo_scrutiny",
     "Would a skeptical senior approve this or take it apart in 30 seconds? Name what they attack first.",
     Severity.HIGH),
    ("real_or_mock", "Is this real, or a mock wearing a real face?", Severity.HIGH),
    ("edge_cases",
     "Are the edge cases handled — empty, null, boundary, large input, unicode, concurrent?",
     Severity.HIGH),
    ("failure_path", "Does it handle the failure path, not just the happy one?", Severity.HIGH),
    ("single_responsibility", "One responsibility, or is a god-function forming?", Severity.MEDIUM),
    ("reuse_over_create",
     "Did the author confirm nothing already does this (no duplication)?", Severity.MEDIUM),
    ("abstraction_earns_keep",
     "Does each abstraction earn its keep (more than one caller, not premature)?", Severity.MEDIUM),
    ("hidden_magic", "Is there hidden coupling or magic nobody could explain?", Severity.MEDIUM),
    ("simpler_version", "Is there a materially simpler version that solves it the same?", Severity.LOW),
]


@dataclass(frozen=True, slots=True)
class JudgeConfig:
    """Where to send the code. Read from the environment — Platão never stores a key."""

    model: str
    base_url: str
    api_key: str

    @classmethod
    def from_env(cls) -> JudgeConfig | None:
        """Build from ``PLATAO_JUDGE_MODEL`` / ``PLATAO_JUDGE_API_KEY`` / ``PLATAO_JUDGE_BASE_URL``.

        Returns ``None`` (fail-closed) if the model or key is missing — the caller then skips judgment
        with a clear message rather than pretending it ran.
        """
        model = os.getenv("PLATAO_JUDGE_MODEL", "").strip()
        api_key = os.getenv("PLATAO_JUDGE_API_KEY", "").strip()
        base_url = os.getenv("PLATAO_JUDGE_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
        if not model or not api_key:
            return None
        return cls(model=model, base_url=base_url, api_key=api_key)


def build_prompt(path: str, source: str, questions: list[tuple[str, str, Severity]]) -> str:
    """The senior-critic prompt, with the code attached and the exact answer format."""
    src = source[:_SRC_CAP] + ("\n… [truncated]" if len(source) > _SRC_CAP else "")
    lines = [
        "You are a skeptical senior engineer reviewing a junior's just-finished work. Be honest and "
        "terse; do not praise — name what is missing. Judge the CODE below, not any description.",
        f"\nFile: {path}\n\n```\n{src}\n```\n",
        "Answer EACH question on its own line, in the exact form `id: VERDICT — reason` "
        "(VERDICT is OK or CONCERN):",
    ]
    lines += [f"- {qid}: {prompt}" for qid, prompt, _ in questions]
    return "\n".join(lines)


def call_llm(config: JudgeConfig, prompt: str, *, timeout: float = 60.0) -> str:
    """POST the prompt to an OpenAI-compatible ``/chat/completions`` endpoint; return the reply text."""
    body = json.dumps({
        "model": config.model,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    request = urllib.request.Request(  # noqa: S310 — user-configured https endpoint
        f"{config.base_url}/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        data = json.load(response)
    choices = data.get("choices") or [{}]
    message = choices[0].get("message") or {}
    return str(message.get("content") or "")


def parse_verdicts(questions: list[tuple[str, str, Severity]], answer: str) -> dict[str, tuple[str, str]]:
    """Extract ``{id: (VERDICT, reason)}`` from the model's reply. Tolerant of form, strict on verdict."""
    out: dict[str, tuple[str, str]] = {}
    for qid, _, _ in questions:
        match = re.search(
            rf"(?im)^[^\n]*\b{re.escape(qid)}\b[^\n]*?\b(OK|CONCERN)\b[:\-—\s]*(.*)$", answer,
        )
        if match:
            out[qid] = (match.group(1).upper(), match.group(2).strip()[:300])
    return out


LlmCall = Callable[[JudgeConfig, str], str]


def run_judgment(path: str, source: str, config: JudgeConfig, *, call: LlmCall = call_llm) -> list[Finding]:
    """Ask the senior's questions about one file and return the CONCERNs as findings.

    ``call`` is injectable so the parsing/verdict logic is tested without a network. If the call fails,
    a single ``judge_unverified`` finding is returned — blindness declared, never silence.
    """
    prompt = build_prompt(path, source, JUDGE_QUESTIONS)
    try:
        answer = call(config, prompt)
    except Exception as exc:  # noqa: BLE001 — any transport/parse failure means "not verified"
        return [Finding("judge_unverified", "judgment", Severity.LOW, path, 1,
                        f"judgment layer unreachable ({type(exc).__name__}) — the senior's angles "
                        f"were NOT verified")]

    verdicts = parse_verdicts(JUDGE_QUESTIONS, answer)
    findings: list[Finding] = []
    for qid, _, severity in JUDGE_QUESTIONS:
        entry = verdicts.get(qid)
        if entry is None:
            continue  # not answered — don't invent a verdict
        verdict, reason = entry
        if verdict == "CONCERN":
            findings.append(Finding(qid, "judgment", severity, path, 1, reason or "(no reason given)"))
    return findings
