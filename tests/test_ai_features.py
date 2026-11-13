from datetime import date

import pytest

import senior_ai
from senior_ai import interview_next, make_briefing, suggest_decision

GROUPS = [{"event": "MT", "cohort": "48대",
           "docs": [{"record_id": 20, "title": "MT 임원회의록", "date": "2025-04-18", "note": ""}],
           "lessons": [{"record_id": 23, "title": "MT 평가", "text": "저녁 준비가 늦어 휴식이 길어졌습니다. 다음에는 미리 준비합니다."}],
           "decisions": []}]


def test_fake_briefing_is_grounded_in_the_groups():
    b = make_briefing(date(2026, 5, 1), GROUPS)
    assert b["todos"][0]["record_ids"] == [20] and b["cautions"][0]["record_id"] == 23


def test_fake_briefing_without_records():
    assert make_briefing(date(2026, 5, 1), [])["todos"] == []


@pytest.fixture
def llm(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")


def test_llm_briefing_drops_unknown_record_ids(llm, monkeypatch):
    monkeypatch.setattr(senior_ai, "complete_json", lambda s, p: {
        "summary": "작년 MT가 있었습니다.", "todos": [{"title": "버스 예약", "why": "작년에 예약했습니다.", "record_ids": [20, 999]}],
        "cautions": [{"text": "저녁 준비 지연", "record_id": 888}]})
    b = make_briefing(date(2026, 5, 1), GROUPS)
    assert b["todos"][0]["record_ids"] == [20] and b["cautions"][0]["record_id"] is None


def test_llm_briefing_links_the_event_document_when_the_model_names_none(llm, monkeypatch):
    monkeypatch.setattr(senior_ai, "complete_json", lambda s, p: {
        "summary": "작년 MT가 있었습니다.", "todos": [{"title": "버스 예약", "why": "작년에 예약했습니다.", "record_ids": []}], "cautions": []})
    assert make_briefing(date(2026, 5, 1), GROUPS)["todos"][0]["record_ids"] == [20]


def test_llm_interview_ends_after_max_and_checks_basis(llm, monkeypatch):
    passages = [{"id": 1, "title": "평가", "body": "휴식시간이 30분 밀렸다.", "occurred_on": "2025-05-19"}]
    monkeypatch.setattr(senior_ai, "complete_json", lambda s, p: {"question": "왜 밀렸나요?", "basis": "기록에 없는 문장"})
    out = interview_next("MT", [], passages)
    assert out["question"] == "왜 밀렸나요?" and out["basis"] == ""
    monkeypatch.setattr(senior_ai, "complete_json", lambda s, p: {"question": "왜 밀렸나요?", "basis": "휴식시간이 30분 밀렸다."})
    assert interview_next("MT", [], passages)["basis"] == "휴식시간이 30분 밀렸다."
    turns = [{"question": f"q{i}", "answer": "a"} for i in range(5)]
    assert interview_next("MT", turns, passages)["question"] is None


def test_llm_decision_draft_keeps_only_known_sources(llm, monkeypatch):
    monkeypatch.setattr(senior_ai, "complete_json", lambda s, p: {"body": "버스를 미리 예약합니다.", "reason": "작년에 늦었습니다.", "record_ids": [23, 5]})
    d = suggest_decision("MT", "MT 준비", "", GROUPS[0]["lessons"], [], [])
    assert d["record_ids"] == [23] and d["body"].startswith("버스")


def test_fake_decision_uses_the_first_lesson():
    d = suggest_decision("MT", "MT 준비", "", GROUPS[0]["lessons"], [], [])
    assert d["record_ids"] == [23] and "저녁 준비" in d["reason"]
