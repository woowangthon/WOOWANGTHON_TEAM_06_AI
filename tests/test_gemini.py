import pytest

import senior_ai
from senior_ai import LLMError, answer_question

REC = [
    {"id": 1, "title": "총회 회의록", "body": "회의장을 3주 전에 예약했다.\n안건지는 하루 전에 배포했다.", "occurred_on": "2025-11-27"},
    {"id": 2, "title": "MT", "body": "버스는 33인승 2대를 예약했다.", "occurred_on": "2025-05-03"},
]


@pytest.fixture(autouse=True)
def gemini(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")


def test_grounded_answer_keeps_verbatim_quotes(monkeypatch):
    monkeypatch.setattr(senior_ai, "complete_json", lambda s, p: {
        "answer": "회의장은 3주 전에 예약했다.", "sources": [{"passage": "P1", "quote": "회의장을 3주 전에 예약했다."}]})
    out = answer_question("총회 준비", REC)
    assert out["sources"] == [{"record_id": 1, "title": "총회 회의록", "quote": "회의장을 3주 전에 예약했다.", "occurred_on": "2025-11-27"}]


def test_invented_quote_falls_back_to_passage_text(monkeypatch):
    monkeypatch.setattr(senior_ai, "complete_json", lambda s, p: {
        "answer": "x", "sources": [{"passage": "P2", "quote": "이 문장은 자료에 없다"}]})
    assert answer_question("버스", REC)["sources"][0]["quote"].startswith("버스는 33인승")


def test_unknown_passage_or_no_sources_means_not_in_records(monkeypatch):
    monkeypatch.setattr(senior_ai, "complete_json", lambda s, p: {"answer": "있다", "sources": [{"passage": "P9", "quote": "q"}]})
    assert answer_question("?", REC) == {"answer": "기록에 없다.", "sources": []}


def test_missing_key_is_llm_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(LLMError):
        answer_question("총회", REC)
