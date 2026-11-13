import subprocess

import pytest

import senior_ai
from senior_ai import LLMError, answer_question, llm

REC = [{"id": 1, "title": "총회", "body": "회의장은 3주 전에 예약했다.", "occurred_on": "2025-11-27"}]


@pytest.fixture(autouse=True)
def claude(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "claude")


def fake_run(stdout="", code=0, stderr=""):
    def run(cmd, **kw):
        run.cmd, run.input = cmd, kw.get("input")
        return subprocess.CompletedProcess(cmd, code, stdout, stderr)
    return run


def test_claude_cli_answer_is_validated_like_any_model(monkeypatch):
    run = fake_run('```json\n{"answer": "3주 전에 예약했습니다.", "sources": [{"passage": "P1", "quote": "회의장은 3주 전에 예약했다."}]}\n```')
    monkeypatch.setattr(llm.subprocess, "run", run)
    out = answer_question("총회는 어떻게 준비했나요?", REC)
    assert out["answer"].startswith("3주 전") and out["sources"][0]["record_id"] == 1
    assert "--tools" in run.cmd and "--setting-sources" in run.cmd and "[P1]" in run.input


def test_claude_cli_failure_is_llm_error(monkeypatch):
    monkeypatch.setattr(llm.subprocess, "run", fake_run("", 1, "Failed to authenticate: OAuth session expired"))
    with pytest.raises(LLMError) as e:
        answer_question("총회", REC)
    assert "authenticate" in str(e.value)


def test_claude_provider_keeps_extraction_rule_based_by_default(monkeypatch):
    monkeypatch.setattr(llm.subprocess, "run", fake_run("", 1, "should not be called"))
    from datetime import date
    assert senior_ai.extract_timeline("t", "2025-05-01 모임", date(2025, 5, 1))[0]["done_on"] == "2025-05-01"
