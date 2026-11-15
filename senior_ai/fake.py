"""Deterministic, key-free implementation. Rule based; good enough for the demo seed and tests."""
import re
from datetime import date

from .text import keywords, sentences

_DATE = re.compile(r"(\d{4})[-.](\d{1,2})[-.](\d{1,2})|(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일|(\d{1,2})월\s*(\d{1,2})일")
_CATEGORIES = [
    ("모집", "모집"), ("선거", "선거"), ("면접", "모집"), ("축제", "축제"), ("MT", "행사"),
    ("체육대회", "행사"), ("송년회", "행사"), ("총회", "총회"), ("정산", "회계"), ("예산", "회계"),
    ("인수인계", "인수인계"), ("회의", "회의"),
]
_QUESTIONS = [
    "{e}에서 가장 아쉬웠던 점은 무엇이었나요?",
    "{e}를 다시 한다면 무엇을 바꾸시겠어요?",
    "{e}를 맡을 다음 기수가 꼭 알아야 할 것은 무엇인가요?",
]


def _category(text: str) -> str:
    return next((c for k, c in _CATEGORIES if k in text), "기타")


def _find_date(s: str, default_year: int):
    m = _DATE.search(s)
    if not m:
        return None, s
    try:
        if m[1]:
            d = date(int(m[1]), int(m[2]), int(m[3]))
        elif m[4]:
            d = date(int(m[4]), int(m[5]), int(m[6]))
        else:
            d = date(default_year, int(m[7]), int(m[8]))
    except ValueError:
        return None, s
    return d, (s[: m.start()] + s[m.end():]).strip()


def extract_timeline(title: str, body: str, occurred_on: date, event_name: str = "") -> list[dict]:
    items: list[dict] = []
    for s in sentences(body):
        d, rest = _find_date(s, occurred_on.year)
        if d:
            rest = re.sub(r"^[\s,.:·-]+|[\s.]+$", "", rest) or title
            items.append({"title": rest, "done_on": d.isoformat(), "category": _category(rest + event_name), "note": ""})
        elif items and not s.startswith("|"):  # undated sentence belongs to the previous dated one; table rows stay out of the note
            items[-1]["note"] = (items[-1]["note"] + " " + s).strip()[:160]
    if len(items) > 8:  # long dialogue minutes: dates are noise, keep one item for the document
        items = []
    if not items:
        items.append({"title": title, "done_on": occurred_on.isoformat(), "category": _category(title + event_name), "note": ""})
    return items


def answer_question(question: str, records: list[dict]) -> dict:
    kws = keywords(question)
    sources = []
    for r in records:
        sents = sentences(r["body"]) or [r["body"]]
        quote = max(sents, key=lambda s: sum(k in s for k in kws))
        sources.append({"record_id": r["id"], "title": r["title"], "quote": quote[:200], "occurred_on": r.get("occurred_on", "")})
    if not sources:
        return {"answer": "기록에 없습니다.", "sources": []}
    lines = [f"{i}) {s['occurred_on']} '{s['title']}' — {s['quote']}" for i, s in enumerate(sources, 1)]
    return {"answer": "기록에는 이렇게 남아 있습니다.\n" + "\n".join(lines), "sources": sources}


def next_interview_question(event_name: str, asked: list[str]) -> str | None:
    for q in _QUESTIONS:
        q = q.format(e=event_name)
        if q not in asked:
            return q
    return None


def make_briefing(today, groups: list[dict]) -> dict:
    """Rule-based briefing: names the events found and quotes the first lesson of each."""
    if not groups:
        return {"summary": "이 시기에는 참고할 지난 기록이 없습니다.", "todos": [], "cautions": []}
    names = ", ".join(g["event"] for g in groups[:4])
    todos, cautions = [], []
    for g in groups[:4]:
        doc = g["docs"][0]
        todos.append({"title": f"{g['event']} 준비 상황을 점검합니다", "why": f"작년에는 '{doc['title']}'로 {doc['date']}에 다뤘습니다.", "record_ids": [doc["record_id"]]})
        if g["lessons"]:
            les = g["lessons"][0]
            cautions.append({"text": sentences(les["text"])[0][:140], "record_id": les["record_id"]})
    return {"summary": f"작년 이맘때에는 {names} 관련 기록이 있습니다. 아래 항목은 작년 기록을 그대로 옮긴 것입니다.", "todos": todos, "cautions": cautions[:3]}


def interview_next(event_name: str, turns: list[dict], passages: list[dict], max_q: int = 3) -> dict:
    q = next_interview_question(event_name, [t["question"] for t in turns])
    return {"question": q, "basis": "", "total": max_q}


def suggest_decision(event: str, item_title: str, note: str, lessons: list[dict], past: list[dict], passages: list[dict]) -> dict:
    if lessons:
        les = lessons[0]
        first = sentences(les["text"])[0][:160]
        return {"body": f"작년 교훈을 반영해 {event}를 진행합니다.", "reason": f"작년 기록에 '{first}'라고 남아 있습니다.", "record_ids": [les["record_id"]]}
    return {"body": f"작년 방식을 참고해 {event}를 진행합니다.", "reason": f"작년에는 '{item_title}'로 진행했습니다.", "record_ids": []}
