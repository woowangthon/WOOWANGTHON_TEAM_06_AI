"""AI logic for 졸업하지 않는 선배. The backend imports these four functions."""
from datetime import date

from . import fake
from .llm import LLMError, provider
from .text import keywords

__all__ = ["LLMError", "keywords", "extract_timeline", "answer_question", "next_interview_question"]


def _impl():
    if provider() == "fake":
        return fake
    from . import llm  # gemini path is not wired yet; every call raises LLMError
    llm.complete("", "")


def extract_timeline(title: str, body: str, occurred_on: date, event_name: str = "") -> list[dict]:
    return _impl().extract_timeline(title, body, occurred_on, event_name)


def answer_question(question: str, records: list[dict]) -> dict:
    """records: [{id, title, body, occurred_on}] already retrieved by the backend."""
    return _impl().answer_question(question, records)


def next_interview_question(event_name: str, asked: list[str]) -> str | None:
    return _impl().next_interview_question(event_name, asked)
