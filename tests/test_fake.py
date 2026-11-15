from datetime import date

from senior_ai import answer_question, extract_timeline, keywords, next_interview_question


def test_extract_dated_sentences_and_notes():
    body = "2025-05-09 부스 위치 추첨에 참여했다. 부스 예산은 30만 원으로 책정했다. 5월 21일 첫날 부스를 운영했다."
    items = extract_timeline("t", body, date(2025, 5, 2), "봄 축제 부스")
    assert [i["done_on"] for i in items] == ["2025-05-09", "2025-05-21"]
    assert "30만 원" in items[0]["note"]


def test_extract_falls_back_to_record_date():
    items = extract_timeline("회의", "날짜 없는 본문이다.", date(2025, 3, 5))
    assert items[0]["done_on"] == "2025-03-05"


def test_answer_without_records_says_not_in_records():
    assert answer_question("학식 메뉴는?", []) == {"answer": "기록에 없습니다.", "sources": []}


def test_answer_cites_quote():
    rec = {"id": 7, "title": "t", "body": "예산은 30만 원이다. 장소는 가평이다.", "occurred_on": "2025-05-02"}
    out = answer_question("예산은 얼마야", [rec])
    assert out["sources"][0]["record_id"] == 7 and "30만 원" in out["sources"][0]["quote"]


def test_keywords_strip_particles():
    assert "예산" in keywords("축제 예산은 얼마였어?")


def test_interview_runs_out():
    asked = []
    while (q := next_interview_question("송년회", asked)):
        asked.append(q)
    assert len(asked) == 3


def test_extract_korean_full_date():
    items = extract_timeline("t", "2025년 4월 18일 19시 회의 시작\n임원 불참 사유 말함", date(2025, 4, 18))
    assert items[0]["done_on"] == "2025-04-18"


def test_keywords_strip_verb_endings():
    assert keywords("정기총회 어떻게 준비했어?") == ["정기총회", "준비"]


def test_keywords_strip_attached_time_particle():
    assert keywords("MT때 출발시간이 왜 밀렸나요?")[0] == "MT"


def test_table_rows_do_not_leak_into_item_notes():
    body = "2025-11-04 체육대회를 진행했다. 간식이 부족했다.\n행사 일정\n| 시간 | 일정 |\n| --- | --- |\n| 09:00 | 집합 |"
    items = extract_timeline("t", body, date(2025, 11, 4))
    assert "|" not in items[0]["note"] and "간식" in items[0]["note"]
