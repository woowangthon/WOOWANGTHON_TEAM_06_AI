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
    assert answer_question("?", REC) == {"answer": "기록에 없습니다.", "sources": []}


def test_missing_key_is_llm_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(LLMError):
        answer_question("총회", REC)


def test_unknown_model_404_falls_back_to_a_listed_flash_model(monkeypatch):
    import urllib.error

    from senior_ai import llm
    llm._model_cache.clear()
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    calls = []

    def fake_request(url, key, body=None):
        calls.append(url)
        if url.endswith("/models?pageSize=200"):
            ms = [("gemini-2.5-flash-lite", "generateContent"), ("gemini-3.0-flash-lite", "generateContent"), ("gemini-3.0-flash", "generateContent"), ("gemini-3.0-flash-preview", "generateContent"),
                  ("gemini-2.5-flash-image", "generateContent"), ("gemini-embedding-001", "embedContent")]
            return {"models": [{"name": f"models/{n}", "supportedGenerationMethods": [m]} for n, m in ms]}
        if "gemini-2.5-flash-lite:" in url:
            raise urllib.error.HTTPError(url, 404, "nf", {}, None)
        return {"candidates": [{"content": {"parts": [{"text": "{\"ok\": true}"}]}}]}

    monkeypatch.setattr(llm, "_gemini_request", fake_request)
    assert llm.complete("s", "p") == '{"ok": true}'
    assert any("gemini-3.0-flash-lite:" in c for c in calls) and llm._model_cache["k"] == "gemini-3.0-flash-lite"
    llm._model_cache.clear()


def test_thinking_off_is_dropped_when_the_model_rejects_it(monkeypatch):
    import urllib.error

    from senior_ai import llm
    llm._model_cache.clear()
    monkeypatch.setenv("GEMINI_API_KEY", "k2")
    seen = []

    def fake_request(url, key, body=None):
        seen.append("thinkingConfig" in body["generationConfig"])
        if "thinkingConfig" in body["generationConfig"]:
            raise urllib.error.HTTPError(url, 400, "bad", {}, None)
        return {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}

    monkeypatch.setattr(llm, "_gemini_request", fake_request)
    assert llm.complete("s", "p", json_mode=False) == "ok" and seen == [True, False]
    llm._model_cache.clear()


def test_rate_limit_error_is_explained(monkeypatch):
    import urllib.error

    from senior_ai import llm
    llm._model_cache.clear()
    monkeypatch.setenv("GEMINI_API_KEY", "k3")
    monkeypatch.setattr(llm, "_gemini_request", lambda url, key, body=None: (_ for _ in ()).throw(urllib.error.HTTPError(url, 429, "x", {}, None)))
    with pytest.raises(LLMError) as e:
        llm.complete("s", "p")
    assert "429" in str(e.value) and "한도" in str(e.value)
    llm._model_cache.clear()


def test_upload_extraction_does_not_call_the_model_by_default(monkeypatch):
    from datetime import date

    monkeypatch.delenv("LLM_EXTRACT", raising=False)

    def boom(*a, **k):
        raise AssertionError("model must not be called")

    monkeypatch.setattr(senior_ai, "complete_json", boom)
    assert senior_ai.extract_timeline("t", "2025-05-01 모임을 했다.", date(2025, 5, 1))[0]["done_on"] == "2025-05-01"
