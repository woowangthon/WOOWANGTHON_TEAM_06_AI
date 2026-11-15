# 졸업하지 않는 선배 · AI

일정 추출, 근거 기반 답변, 브리핑, 퇴임 인터뷰 질문, 결정 초안을 담당하는 Python 패키지(`senior_ai`)입니다. 서버가 아니라 [Backend](https://github.com/woowangthon/WOOWANGTHON_TEAM_06_BE)가 import해서 씁니다. (AI 우왕톤 TEAM 06)

## 원칙

- AI는 **기록에 있는 내용만** 답합니다. 모델이 돌려준 인용 구절이 원문에 그대로 있는지 코드가 다시 확인하고, 없으면 모델의 인용 대신 원문 구간의 시작 부분을 근거로 보여 줍니다.
- 근거가 없으면 "기록에 없습니다"라고 답합니다.
- AI는 결정을 대신하지 않습니다. 결정 초안은 제안일 뿐이고 저장은 사람이 합니다.

## 공개 함수

```python
from senior_ai import (
    extract_timeline,    # 문서에서 '언제 무엇을 했는지' 일정 항목 추출
    answer_question,     # 검색된 구간만으로 답하고 인용 검증
    make_briefing,       # 작년 이맘때 브리핑
    interview_next,      # 퇴임 인터뷰의 다음 질문(최대 5개, 근거 문장 검증)
    suggest_decision,    # 올해 결정 초안
)
```

## 모델 제공자 (`LLM_PROVIDER`)

| 값 | 설명 |
| --- | --- |
| `fake` (기본) | 키 없이 도는 규칙 기반 구현. 개발·테스트용 |
| `gemini` | Gemini REST API. `GEMINI_API_KEY` 필요, `GEMINI_MODEL` 선택. 모델 이름이 404이면 사용 가능한 모델을 자동으로 찾고, 사고 기능은 꺼서 지연을 줄입니다. 한도(429) 오류는 안내 문구로 바꿉니다 |
| `claude` | 로컬에 로그인된 `claude -p`를 사용. **로컬 개발 전용** |

`LLM_EXTRACT=1`을 주면 일정 추출에도 모델을 씁니다. 기본은 규칙 기반이라 파일을 올려도 모델 호출 한도를 쓰지 않습니다.

## 기술 선택

- **별도 레포의 패키지:** 모델과 프롬프트를 바꿔도 서버와 화면을 건드리지 않도록 분리했습니다. 백엔드는 git URL로 설치합니다.
- **검증을 코드로:** 모델을 믿지 않고 인용 일치, 근거 번호 범위, JSON 형식을 모두 코드에서 확인합니다.
- **fake 구현:** 네트워크와 키 없이 전체 흐름을 테스트하고, 모델이 실패해도 서비스가 멈추지 않게 합니다.

## 설치와 테스트

```bash
pip install -e . pytest
pytest                      # fake 모델 기준, 네트워크 없음
```

Backend에서는 `requirements.txt`가 이 저장소를 git URL로 설치합니다. 로컬 개발은 `pip install -e ../AI`로 바로 반영합니다.
