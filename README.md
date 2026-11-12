# 졸업하지 않는 선배 · AI

일정 추출, 근거 기반 답변, 퇴임 인터뷰 질문을 담당하는 Python 패키지(`senior_ai`). 서버가 아니라 Backend가 import해서 쓴다.

```python
from senior_ai import extract_timeline, answer_question, next_interview_question
```

- `LLM_PROVIDER=fake` (기본): 키 없이 도는 규칙 기반 구현. 개발·테스트용.
- `LLM_PROVIDER=gemini`: `GEMINI_API_KEY`, `GEMINI_MODEL` 필요. 아직 연결 전.

테스트: `pip install -e . pytest && pytest`
