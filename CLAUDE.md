# Safety Agent — CLAUDE.md

## 트리거 키워드

### "깃 커밋" 또는 "git 커밋"

사용자가 **"깃 커밋"** 또는 **"git 커밋"** 이라고 입력하면 아래 절차를 자동 실행한다.

1. `git status` 확인 (변경 파일 목록 파악)
2. `.venv/`를 **제외**하고 변경된 파일 스테이징 (`git add`)
3. 변경 내용을 분석해 적절한 커밋 메시지 자동 작성
4. `git commit`
5. `git push origin main` → **https://github.com/khselect/AI_Agent** 로 push

> `.venv/`는 `.gitignore`에 등록되어 있으므로 자동 제외된다.
> push 전에 커밋 메시지를 보여주고 진행 여부를 확인한다.

---

## 프로젝트 개요

철도 사고 조사 보고서 PDF를 자동 분석하고, 위험도 산정 및 알림 발송을 수행하는 AI 에이전트 시스템.

- **UI**: Streamlit (`safety_analytics.py`)
- **에이전트**: LangGraph + Ollama (`railway_agent/railway_safety_agent.py`)
- **LLM**: Ollama 로컬 서버 (`http://127.0.0.1:11434`), 기본 모델 `qwen2.5:3b`

---

## 파일 구조

```
Safety_agent/
├── safety_analytics.py          # Streamlit UI 진입점 (streamlit run)
├── safety_core.py               # 공유 비즈니스 로직 (UI 의존성 없음)
├── gen_data.py                  # 가상 데이터 생성기 (python gen_data.py)
├── shared/
│   ├── railway_accidents.duckdb # 사고 데이터 DB
│   ├── notify_config.json       # 수신자·채널·알림 이력
│   └── notify_config_template.json
└── railway_agent/
    ├── __init__.py
    ├── railway_safety_agent.py  # LangGraph 에이전트 + Tool 정의
    └── agent_ui.py              # AI 에이전트 탭 UI (Streamlit)
```

---

## 아키텍처 원칙

### 3-레이어 분리 패턴

```
UI 레이어          safety_analytics.py  (Streamlit, import safety_core)
                   railway_agent/agent_ui.py (Streamlit 탭)
        ↓ import
Core 레이어        safety_core.py       (비즈니스 로직, Streamlit 의존 없음)
        ↓ import
Data 레이어        shared/railway_accidents.duckdb
                   shared/notify_config.json
```

- **safety_core.py는 Streamlit을 절대 import하지 않는다.** 에이전트와 UI가 공유하는 유일한 로직 파일.
- 에이전트(`railway_safety_agent.py`)는 `safety_core`의 함수를 `@tool`로 래핑해 LangGraph에 등록한다.
- UI(`safety_analytics.py`)는 `safety_core`를 직접 import해 사용한다.

### CORE_AVAILABLE 패턴

`railway_safety_agent.py`는 `safety_core` 임포트 실패 시 내장 fallback으로 동작한다.

```python
try:
    from safety_core import extract_from_pdf, insert_accident, ...
    CORE_AVAILABLE = True
except ImportError:
    CORE_AVAILABLE = False
```

각 Tool 함수 내에서 `if CORE_AVAILABLE: ... else: # fallback` 분기를 유지한다.

---

## DB 스키마

DuckDB `accidents` 테이블: **49개 컬럼** (id, created_at, source_file + 43개 필드 + risk_score, risk_grade, raw_json)

주요 컬럼:
- `발생일자` (VARCHAR, YYYY-MM-DD), `노선`, `이벤트소분류`
- `사망자수`, `부상자수`, `피해액(백만원)`, `최대지연시간(분)`
- `risk_score` (DOUBLE, 0~100), `risk_grade` (Critical/High/Medium/Low)

**컬럼명 주의**: `safety_core.py`는 `"최대지연시간(분)"`, `"피해액(백만원)"` (따옴표 필요한 특수문자 포함).
`gen_data.py`는 `최대지연시간_분`, `피해액_백만원` (언더스코어, 다른 스키마).

---

## 위험도 산정 공식

`safety_core.calculate_risk()` 기준 — **gen_data.py와 동일한 공식을 유지해야 함.**

```
score = min(efi * 20, 40)          # EFI = 사망 + 부상/100
      + min(피해액 / 50, 20)
      + min(지연(분) / 40, 15)
      + 이벤트 보정 (+15 탈선/충돌/화재/폭발/추락/붕괴, +10 사고, +5 장애)

Hard Constraint:
  사망 ≥ 1  → score = max(score, 60)   → High 이상 강제
  사망 ≥ 3 or 부상 ≥ 20 → score = max(score, 80)  → Critical
  사망 ≥ 5  → score = max(score, 90)

등급: Critical ≥ 80 / High ≥ 60 / Medium ≥ 25 / Low < 25
```

---

## 에이전트 Tool 목록

| Tool | 래핑 함수 | 설명 |
|------|-----------|------|
| `extract_pdf_tool` | `extract_from_pdf()` | PDF → 43개 필드 추출 (5배치 LLM) |
| `save_db_tool` | `insert_accident()` + `calculate_risk()` | DB 저장 + 위험도 |
| `query_db_tool` | `get_all_accidents()` | DB 조회·필터 |
| `assess_risk_tool` | `calculate_risk()` | 위험도만 즉시 산정 |
| `scenario_tool` | `generate_scenarios()` | Bow-Tie 시나리오 생성 |
| `web_collect_tool` | (내장) | URL에서 텍스트 수집 |
| `notify_tool` | (내장) | notify_config.json 기반 알림 발송 |

---

## LangGraph 그래프 구조

```
[START] → supervisor → (tool_calls?) → tool_node → supervisor → ... → [END]
```

- 최대 반복 15회 (`iteration >= 15`이면 강제 종료)
- `should_continue()`: tool_calls 있으면 `tool_node`, 없으면 `END`
- `ChatOllama`는 반드시 `langchain_ollama` 패키지 사용 (`langchain_community` 는 `bind_tools` 미지원)

---

## PDF 추출 파이프라인

`safety_core.extract_from_pdf()` 3단계:
1. `pymupdf4llm.to_markdown()` → 전체 텍스트 변환
2. `_regex_base()` → 날짜·사망·부상 정규식 추출 (기본값)
3. LLM 5배치 병렬 추출 → `_safe_json()` 파싱 → 기존값 보강

**배치 슬라이싱**: 각 배치는 텍스트의 다른 오프셋 구간 사용 (`BATCH_SLICE`)
**Qwen3 대응**: 모델명에 `qwen3` 포함 시 `/no_think\n` 프리픽스 추가, `<think>` 태그 제거

---

## 알림 설정 (`shared/notify_config.json`)

```json
{
  "recipients": [{ "name", "email", "slack", "phone", "active", "notify_grades" }],
  "rules": { "Critical": ["email","slack","sms"], "High": ["email","slack"], ... },
  "notify_log": [최근 100건 이력]
}
```

- `notify_config_template.json`을 복사해 `notify_config.json` 생성
- 알림 이력은 자동으로 `notify_log`에 선입후출(최대 100건) 기록

---

## 실행 방법

```bash
# Streamlit UI 실행
streamlit run safety_analytics.py

# 에이전트 단독 실행
python railway_agent/railway_safety_agent.py --goal "High 이상 사고 조회"
python railway_agent/railway_safety_agent.py --demo query_high
python railway_agent/railway_safety_agent.py --demo assess
python railway_agent/railway_safety_agent.py --demo scenario

# 가상 데이터 재생성 (기존 DB 삭제 후 500건 생성)
python gen_data.py
```

---

## 필수 패키지

```bash
pip install streamlit duckdb pandas altair pymupdf4llm openpyxl
pip install langchain langchain-ollama langgraph
# (주의) langchain_community ChatOllama 아닌 langchain_ollama 사용
```

---

## 데이터 분포 목표 (gen_data.py)

| 등급 | 비율 | 조건 |
|------|------|------|
| Critical | 15% (75건) | 사망≥3 또는 부상≥20 |
| High | 20% (100건) | 사망=1 |
| Medium | 35% (175건) | 사망=0, 부상 8~19 |
| Low | 30% (150건) | 사망=0, 부상 0~2, 장애류 |
