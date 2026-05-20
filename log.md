# 변경 이력 (Safety Agent)

---

## v1.4.0 — 2026-05-20 · qwen3 추출 정확도 개선

### [문제점]
- `qwen3:32b` 모델 선택 시 `qwen2.5:7b-instruct` 대비 43개 필드 추출률 저하
- `/no_think` 를 프롬프트 텍스트에 삽입하는 방식으로는 thinking 모드가 실제로 비활성화되지 않음
- thinking 모드 ON 상태에서 `<think>` 블록이 `num_predict=2048` 토큰 대부분을 소비해 JSON 출력 잘림
- 배치 파싱 실패 시 재시도 없이 조용히 skip → 필드 누락
- `format="json"` 미적용으로 마크다운/설명문 섞인 응답 파싱 오류 발생

### [개선점]
- `reasoning=False` 파라미터 추가 (`langchain_ollama 0.3+` → Ollama `think=false` 전달) — thinking 완전 비활성화
- `num_predict` 2048 → 4096 으로 증가 — JSON 출력 잘림 방지
- `format="json"` 옵션 추가 — 모델이 JSON 구조만 출력하도록 강제
- 배치별 실패 시 1회 재시도 로직 추가 — 파싱 오류에 의한 누락 방지
- 프롬프트에서 불필요한 `/no_think` prefix 제거 (reasoning=False 로 대체)
- 수정 파일: `safety_analytics.py`, `safety_core.py`
- 메인 페이지 상단에 버전/커밋 정보 표시 추가

---

## v1.3.0 — 2026-03-29 · LLM 추출 버그 및 DB 컬럼명 불일치 수정

### [문제점]
- LLM 추출 비활성화 버그 (조건 분기 오류)
- DB 컬럼명 불일치 (`최대지연시간_분` vs `최대지연시간(분)`) 로 INSERT 실패

### [개선점]
- LLM 활성화 조건 분기 수정
- DB 컬럼명 `"최대지연시간(분)"`, `"피해액(백만원)"` 특수문자 포함 형태로 통일

---

## v1.2.0 — 2026-03-29 · 3-레이어 아키텍처 리팩토링

### [문제점]
- `safety_analytics.py` 단일 모놀리식 파일에 UI·비즈니스로직·DB·에이전트 혼재
- 에이전트(`railway_safety_agent.py`)가 Streamlit을 간접 import해 독립 실행 불가

### [개선점]
- `safety_core.py` 분리 (비즈니스 로직, Streamlit 의존 없음)
- UI 탭별 모듈화 (`ui/tab_*.py`)
- 에이전트가 `safety_core` 만 import하도록 변경

---

## v1.1.0 — CLAUDE.md·.gitignore 추가

### [개선점]
- `CLAUDE.md` 작성 (아키텍처·DB 스키마·실행방법 문서화)
- `.gitignore` 추가 (`.venv/`, `__pycache__/`, `*.pyc` 제외)
- `notify_config.json` 알림 이력 구조 정비
