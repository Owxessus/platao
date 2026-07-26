"""Proofs for the opt-in judgment layer. The LLM call is injected, so no network is touched."""

from __future__ import annotations

from platao.judge import JUDGE_QUESTIONS, JudgeConfig, build_prompt, parse_verdicts, run_judgment

_CFG = JudgeConfig(model="m", base_url="http://x/v1", api_key="k")


def test_build_prompt_includes_code_and_every_question():
    prompt = build_prompt("service.py", "def process(): pass", JUDGE_QUESTIONS)
    assert "def process(): pass" in prompt
    for qid, _, _ in JUDGE_QUESTIONS:
        assert qid in prompt


def test_parse_verdicts_reads_ok_and_concern_and_skips_unanswered():
    answer = (
        "momo_scrutiny: CONCERN — it's a mock with a real face\n"
        "real_or_mock: OK — genuine\n"
        "edge_cases: CONCERN — no null handling\n"
        # 'hidden_magic' deliberately unanswered
    )
    verdicts = parse_verdicts(JUDGE_QUESTIONS, answer)
    assert verdicts["momo_scrutiny"][0] == "CONCERN"
    assert "mock" in verdicts["momo_scrutiny"][1]
    assert verdicts["real_or_mock"][0] == "OK"
    assert "hidden_magic" not in verdicts


def test_run_judgment_emits_concerns_only():
    def fake(_cfg, _prompt):
        return "momo_scrutiny: CONCERN — shallow\nreal_or_mock: OK — fine"

    findings = run_judgment("m.py", "code", _CFG, call=fake)
    ids = {f.check_id for f in findings}
    assert "momo_scrutiny" in ids  # CONCERN → finding
    assert "real_or_mock" not in ids  # OK → silent
    assert all(f.category == "judgment" for f in findings)


def test_run_judgment_unreachable_is_reported_not_silent():
    def boom(_cfg, _prompt):
        raise RuntimeError("no network")

    findings = run_judgment("m.py", "code", _CFG, call=boom)
    assert len(findings) == 1
    assert findings[0].check_id == "judge_unverified"  # blindness declared, not silence


def test_from_env_is_fail_closed_without_config(monkeypatch):
    monkeypatch.delenv("PLATAO_JUDGE_MODEL", raising=False)
    monkeypatch.delenv("PLATAO_JUDGE_API_KEY", raising=False)
    assert JudgeConfig.from_env() is None


def test_from_env_builds_when_set(monkeypatch):
    monkeypatch.setenv("PLATAO_JUDGE_MODEL", "gpt-x")
    monkeypatch.setenv("PLATAO_JUDGE_API_KEY", "sk-x")
    monkeypatch.delenv("PLATAO_JUDGE_BASE_URL", raising=False)
    config = JudgeConfig.from_env()
    assert config is not None
    assert config.model == "gpt-x"
    assert config.base_url.endswith("/v1")
