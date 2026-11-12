"""Text helpers shared by the AI package and the backend search."""
import re

_JOSA = "은는이가을를에의도로와과만"
_SUFFIX = ("했어요", "했나요", "했는지", "했어", "했나", "하나요", "해요", "됐어", "였어", "인지", "는지", "한지")
_STOP = {"작년", "올해", "언제", "어떻게", "무엇", "뭐", "얼마", "어떤", "왜", "알려", "알려줘", "해줘", "기록"}


def keywords(question: str) -> list[str]:
    """Rough Korean keyword extraction: strip a trailing particle, drop stop words."""
    out = []
    for t in re.findall(r"[0-9A-Za-z가-힣]+", question):
        for suf in _SUFFIX:
            if t.endswith(suf) and len(t) > len(suf):
                t = t[: -len(suf)]
                break
        if len(t) > 2 and t[-1] in _JOSA:
            t = t[:-1]
        if len(t) >= 2 and t not in _STOP:
            out.append(t)
    return list(dict.fromkeys(out))


def sentences(body: str) -> list[str]:
    return [s.strip() for s in re.split(r"\n+|(?<=[.!?다요])\s+", body.strip()) if s.strip()]
