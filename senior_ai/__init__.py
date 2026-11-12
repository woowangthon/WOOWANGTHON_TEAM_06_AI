"""AI logic for 졸업하지 않는 선배. The backend imports these functions."""
import re
from datetime import date

from . import fake
from .llm import LLMError, complete_json, provider
from .prompts import ASK_SYSTEM, EXTRACT_SYSTEM
from .text import keywords

__all__ = ["LLMError", "keywords", "extract_timeline", "answer_question", "next_interview_question"]


def _ws(s: str) -> str:
    return re.sub(r"\s+", "", s)


def extract_timeline(title: str, body: str, occurred_on: date, event_name: str = "") -> list[dict]:
    if provider() == "fake":
        return fake.extract_timeline(title, body, occurred_on, event_name)
    data = complete_json(EXTRACT_SYSTEM, f"문서 제목: {title}\n행사명: {event_name}\n문서 날짜: {occurred_on}\n\n본문:\n{body[:12000]}")
    items = []
    for it in data if isinstance(data, list) else []:
        try:
            d = date.fromisoformat(str(it["done_on"]))
        except (KeyError, ValueError):
            continue
        items.append({"title": str(it.get("title") or title)[:200], "done_on": d.isoformat(),
                      "category": str(it.get("category", ""))[:30], "note": str(it.get("note", ""))[:300]})
    return items or fake.extract_timeline(title, body, occurred_on, event_name)


def answer_question(question: str, records: list[dict]) -> dict:
    """records: retrieved passages [{id, title, body, occurred_on}] (id = record id). Returns {answer, sources}."""
    if provider() == "fake" or not records:
        return fake.answer_question(question, records)
    passages = "\n\n".join(f"[P{i}] ({r.get('occurred_on', '')} · {r['title']})\n{r['body']}" for i, r in enumerate(records, 1))
    data = complete_json(ASK_SYSTEM, f"자료:\n{passages}\n\n질문: {question}")
    answer = str(data.get("answer", "")).strip() if isinstance(data, dict) else ""
    sources, seen = [], set()
    for s in (data.get("sources", []) if isinstance(data, dict) else [])[:4]:
        m = re.fullmatch(r"P?(\d+)", str(s.get("passage", "")).strip())
        if not m or not 1 <= int(m[1]) <= len(records):
            continue
        r = records[int(m[1]) - 1]
        quote = str(s.get("quote", "")).strip()
        if not quote or _ws(quote) not in _ws(r["body"]):  # model must quote verbatim; otherwise fall back to the passage start
            quote = r["body"].strip()[:150]
        if (r["id"], quote) in seen:
            continue
        seen.add((r["id"], quote))
        sources.append({"record_id": r["id"], "title": r["title"], "quote": quote, "occurred_on": r.get("occurred_on", "")})
    if not answer or not sources:
        return {"answer": "기록에 없다.", "sources": []}
    return {"answer": answer, "sources": sources}


def next_interview_question(event_name: str, asked: list[str]) -> str | None:
    return fake.next_interview_question(event_name, asked)
