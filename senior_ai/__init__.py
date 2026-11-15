"""AI logic for 졸업하지 않는 선배. The backend imports these functions."""
import os
import re
from datetime import date

from . import fake
from .llm import LLMError, complete_json, provider
from .prompts import ASK_SYSTEM, BRIEFING_SYSTEM, DECISION_SYSTEM, EXTRACT_SYSTEM, INTERVIEW_NEXT_SYSTEM
from .text import keywords

__all__ = ["LLMError", "keywords", "extract_timeline", "answer_question", "next_interview_question", "make_briefing", "interview_next", "suggest_decision"]


def _ws(s: str) -> str:
    return re.sub(r"\s+", "", s)


def _whole_table(quote: str, body: str) -> str:
    """If the quoted text is inside a markdown table, quote the whole table so the reader sees the full timetable."""
    lines = body.splitlines()
    for i, l in enumerate(lines):
        if l.startswith("|") and _ws(quote)[:20] in _ws(l):
            a = i
            while a > 0 and lines[a - 1].startswith("|"):
                a -= 1
            b = i
            while b + 1 < len(lines) and lines[b + 1].startswith("|"):
                b += 1
            return "\n".join(lines[a:b + 1])
    return quote


def extract_timeline(title: str, body: str, occurred_on: date, event_name: str = "") -> list[dict]:
    # timeline extraction stays rule based unless LLM_EXTRACT=1, so uploads do not spend model quota (free plans allow few calls a day)
    if provider() == "fake" or os.environ.get("LLM_EXTRACT") != "1":
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
        quote = _whole_table(quote, r["body"])
        if (r["id"], quote) in seen:
            continue
        seen.add((r["id"], quote))
        sources.append({"record_id": r["id"], "title": r["title"], "quote": quote, "occurred_on": r.get("occurred_on", "")})
    if not answer or not sources:
        return {"answer": "기록에 없습니다.", "sources": []}
    return {"answer": answer, "sources": sources}


def next_interview_question(event_name: str, asked: list[str]) -> str | None:
    return fake.next_interview_question(event_name, asked)


def _llm_on() -> bool:
    return provider() != "fake"


def _clip(t: str, n: int) -> str:
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= n else t[:n] + "…"


def make_briefing(today: date, groups: list[dict]) -> dict:
    """groups: [{event, cohort, docs:[{record_id,title,date,note}], lessons:[{record_id,title,text}], decisions:[{body,reason}]}]."""
    if not _llm_on() or not groups:
        return fake.make_briefing(today, groups)
    blocks = []
    for g in groups[:6]:
        lines = [f"### {g['event']} ({g['cohort']})"]
        for d in g["docs"][:3]:
            lines.append(f"- 문서 [R{d['record_id']}] {d['date']} {d['title']}" + (f" — {_clip(d['note'], 120)}" if d.get("note") else ""))
            if d.get("excerpt"):
                lines.append(f"  본문 발췌: {_clip(d['excerpt'], 900)}")
        lines += [f"- 교훈 [R{l['record_id']}] {l['title']}: {_clip(l['text'], 700)}" for l in g["lessons"][:3]]
        lines += [f"- 그해 결정: {d['body']} (이유: {d['reason']})" for d in g.get("decisions", [])[:2]]
        blocks.append("\n".join(lines))
    data = complete_json(BRIEFING_SYSTEM, f"오늘은 {today}입니다. 작년 같은 시기의 기록입니다.\n\n" + "\n\n".join(blocks))
    if not isinstance(data, dict):
        raise LLMError("브리핑 형식이 올바르지 않습니다")
    ok = {d["record_id"] for g in groups for d in g["docs"]} | {l["record_id"] for g in groups for l in g["lessons"]}

    def ids(v) -> list[int]:
        out = []
        for x in v if isinstance(v, list) else [v]:
            m = re.search(r"\d+", str(x))
            if m and int(m[0]) in ok and int(m[0]) not in out:
                out.append(int(m[0]))
        return out

    todos = [{"title": str(t.get("title", ""))[:120], "why": str(t.get("why", ""))[:240], "record_ids": ids(t.get("record_ids", []))[:3]}
             for t in data.get("todos", [])[:4] if isinstance(t, dict) and t.get("title")]
    cautions = [{"text": str(c.get("text", ""))[:240], "record_id": (ids(c.get("record_id")) or [None])[0]}
                for c in data.get("cautions", [])[:3] if isinstance(c, dict) and c.get("text")]
    if len(groups) == 1:  # one event only: its tasks come from that event's documents, so link the main one when the model named none
        for t in todos:
            t["record_ids"] = t["record_ids"] or [groups[0]["docs"][0]["record_id"]]
    summary = str(data.get("summary", "")).strip()
    if not summary:
        raise LLMError("브리핑이 비어 있습니다")
    return {"summary": summary, "todos": todos, "cautions": cautions}


def interview_next(event_name: str, turns: list[dict], passages: list[dict], max_q: int = 5) -> dict:
    """turns: [{question, answer}] so far; passages: retrieved record passages [{id,title,body,occurred_on}]."""
    if not _llm_on():
        return fake.interview_next(event_name, turns, passages)
    if len(turns) >= max_q:
        return {"question": None, "basis": "", "total": max_q}
    ctx = "\n\n".join(f"[{p['occurred_on']} {p['title']}]\n{_clip(p['body'], 900)}" for p in passages[:6]) or "(관련 기록 없음)"
    done = "\n".join(f"Q{i}. {t['question']}\nA{i}. {t['answer']}" for i, t in enumerate(turns, 1)) or "(아직 없음)"
    data = complete_json(INTERVIEW_NEXT_SYSTEM, f"행사: {event_name}\n\n[행사 기록]\n{ctx}\n\n[지금까지의 문답]\n{done}\n\n다음 질문을 하나 만들어 주세요.")
    q = data.get("question") if isinstance(data, dict) else None
    basis = str(data.get("basis", "")).strip() if isinstance(data, dict) else ""
    if basis and _ws(basis) not in _ws(" ".join(p["body"] for p in passages)):
        basis = ""  # only show a basis sentence that really is in the records
    return {"question": str(q).strip() if q else None, "basis": basis[:200], "total": max_q}


def suggest_decision(event: str, item_title: str, note: str, lessons: list[dict], past: list[dict], passages: list[dict]) -> dict:
    """Draft only: a person edits and saves. lessons: [{record_id,title,text}]; past: [{body,reason}]; passages as in answer_question."""
    if not _llm_on():
        return fake.suggest_decision(event, item_title, note, lessons, past, passages)
    parts = [f"행사: {event}\n작년 일정: {item_title}" + (f" — {_clip(note, 200)}" if note else "")]
    parts += [f"[R{l['record_id']}] 교훈 · {l['title']}: {_clip(l['text'], 800)}" for l in lessons[:3]]
    parts += [f"[R{p['id']}] {p['occurred_on']} {p['title']}: {_clip(p['body'], 500)}" for p in passages[:4]]
    parts += [f"지난 결정: {d['body']} (이유: {d['reason']})" for d in past[:3]]
    data = complete_json(DECISION_SYSTEM, "\n\n".join(parts) + "\n\n올해의 결정 초안을 제안해 주세요.")
    if not isinstance(data, dict) or not str(data.get("body", "")).strip():
        raise LLMError("결정 초안이 비어 있습니다")
    ok = {l["record_id"] for l in lessons} | {p["id"] for p in passages}
    raw = data.get("record_ids", [])
    ids = []
    for x in raw if isinstance(raw, list) else [raw]:
        m = re.search(r"\d+", str(x))
        if m and int(m[0]) in ok and int(m[0]) not in ids:
            ids.append(int(m[0]))
    # the draft was written from these records, so show them as its basis when the model named none
    ids = ids or [l["record_id"] for l in lessons[:2]] or [p["id"] for p in passages[:2]]
    return {"body": str(data["body"]).strip()[:300], "reason": str(data.get("reason", "")).strip()[:400], "record_ids": ids[:4]}
