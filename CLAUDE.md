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
- **LLM**: Ollama 로컬 서버 (`http://127.0.0.1:11434`), 기본 모델 `qwen3:8b`
- **현재 버전**: v1.7.4 (기본 모델 qwen3:8b, 추출률 43/43)

---

## 파일 구조

```
Safety_agent/
├── safety_analytics.py          # Streamlit UI 진입점 (streamlit run)
├── safety_core.py               # 공유 비즈니스 로직 (UI 의존성 없음)
├── gen_data.py                  # 가상 데이터 생성기 (python gen_data.py)
├── log.md                       # 버전별 변경 이력 [문제점][개선점]
├── docs/
│   └── 기술상세서.md             # 비전공자용 시스템 설명서
├── shared/
│   ├── railway_accidents.duckdb # 사고 데이터 DB
│   ├── notify_config.json       # 수신자·채널·알림 이력
│   └── notify_config_template.json
├── ui/
│   ├── tab_input.py             # 보고서 입력 탭
│   ├── tab_data.py              # 데이터 조회 탭
│   ├── tab_dashboard.py         # 대시보드 탭
│   ├── tab_risk.py              # 위험도 평가 탭
│   └── tab_forecast.py          # 위험 예측 탭
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
                   ui/tab_*.py          (탭별 분리 모듈)
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
| `extract_pdf_tool` | `extract_from_pdf()` | PDF → 43개 필드 추출 |
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

## PDF 추출 파이프라인 (v1.7.0)

### 7단계 추출 흐름

```
[1] pymupdf4llm.to_markdown()     PDF 전체 텍스트 추출
[2] _regex_base()                 정규식으로 날짜·기관·인명피해 즉시 추출
[3] LLM 5배치 순차 추출            전체 보고서(28000자) × 5배치 → 43개 필드
[4] 고장 필드 전용 재추출           고장부품명·고장현상·고장원인·조치내용이 null이면 재시도
[5] 이벤트개요 전용 생성            LLM에게 3~5문장 요약 생성 요청 (추출이 아닌 생성)
[6] 이벤트개요 합성 fallback       LLM 실패 시 기추출 필드로 문장 자동 조합
[7] 데이터출처 기본값 설정          null이면 'PDF 자동 추출' 설정
```

### LLM 호출 설정

```python
ChatOllama(
    model=model_name,
    base_url="http://127.0.0.1:11434",
    temperature=0,
    num_ctx=16384,       # v1.7.3: 32768→16384 (입력 토큰 불변 확인, 스왑 완화)
    num_predict=4096,    # thinking 블록 포함 여유있는 출력 허용
    keep_alive="30m",    # v1.7.3: 모델 상주 — 연속 처리 시 재로딩 제거
    reasoning=False,     # qwen3 모델만 적용 — Ollama think=false 전달
    # format="json" 사용 금지 — 한국어 텍스트 생성 차단 확인됨
)
```

**`format="json"` 사용 절대 금지**: Ollama의 JSON 문법 제약이 한국어 유니코드 토큰 생성을 차단해 모든 텍스트 필드가 null로 반환됨. `_safe_json()`으로 파싱 처리.

### 모델명 주의

**기본 모델**: `qwen3:8b` (~7.4GB, 24GB 램에서 100% GPU 상주 → 스왑 없음, 30b 대비 ~3.3배)  
**대안 모델**: `qwen3:30b-a3b` (MoE 20GB — 24GB 램에선 12% CPU 스필+스왑 발생), `qwen3:32b` (고품질, RAM 여유 필요)  
> v1.7.4에서 30b→8b 전환. 8b가 추출률 43/43로 30b(37~40/43)보다 오히려 우수하며,
> 고장/직접원인 과추출은 프롬프트 정밀화(피해내역·점검표 나열 금지)로 해결.
`qwen3:32`는 Ollama에서 404 오류 발생 → 예외가 catch되어 LLM 기여 0개, 정규식만 추출됨.

### 오류 처리

모델 미발견(404) 시 progress_fn으로 사용자에게 명시적 오류 메시지 표시.  
각 배치는 실패 시 1회 자동 재시도 후 skip.

### 배치 구성

모든 배치가 **전체 보고서(28000자)** 를 사용한다. 구간 슬라이싱 없음.

| 배치 | 담당 컬럼 | 비고 |
|------|---------|------|
| 0 (기본정보) | COLUMNS[0:9] | 발생일시·기관·노선·이벤트분류 |
| 1 (원인·지연) | COLUMNS[9:18] | 근본원인·직접원인·지연정보 |
| 2 (피해·위치A) | COLUMNS[18:26] | 피해현황·위치 |
| 3 (위치·기상) | COLUMNS[26:34] | 위치상세·기상환경 |
| 4 (선로·고장·개요) | COLUMNS[34:] | **고장부품·조치·개요 — 한국어 강조 지시 포함** |

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
# langchain-ollama >= 0.3.0 필수 (reasoning 파라미터 지원)
```

---

## 데이터 분포 목표 (gen_data.py)

| 등급 | 비율 | 조건 |
|------|------|------|
| Critical | 15% (75건) | 사망≥3 또는 부상≥20 |
| High | 20% (100건) | 사망=1 |
| Medium | 35% (175건) | 사망=0, 부상 8~19 |
| Low | 30% (150건) | 사망=0, 부상 0~2, 장애류 |

---

## 버전 이력 요약

| 버전 | 날짜 | 주요 변경 |
|------|------|---------|
| v1.7.4 | 2026-08-13 | **기본 모델 30b→`qwen3:8b`** (24GB 램 스왑 병목 해결, 속도 ~3.3배) + 고장/직접원인 과추출 정밀화 |
| v1.7.3 | 2026-08-07 | 정확도 무위험 성능 개선(num_ctx 16384, keep_alive 30m, `extract_cli.py`) + 배치2 추출률 개선 |
| v1.7.2 | 2026-06-29 | 기본 모델 `qwen3:32b` → `qwen3:30b-a3b` 변경 |
| v1.7.1 | 2026-05-28 | PDF 추출+DB저장 소요시간 표시 기능 추가 |
| v1.7.0 | 2026-05-20 | **모델명 오타 수정** `qwen3:32` → `qwen3:32b` (핵심 버그) |
| v1.6.0 | 2026-05-20 | format="json" 제거, 한국어 프롬프트, 이벤트개요 전용 생성 |
| v1.5.0 | 2026-05-20 | 배치4 전체 보고서 사용, 고장 필드 재추출 패스 |
| v1.4.0 | 2026-05-20 | reasoning=False, num_predict 4096, 버전 표시 추가 |
| v1.3.0 | 2026-03-29 | LLM 추출 버그·DB 컬럼명 불일치 수정 |
| v1.2.0 | 2026-03-29 | 3-레이어 아키텍처 리팩토링, ui/탭 모듈화 |
| v1.1.0 | 2026-03-29 | CLAUDE.md·.gitignore 추가 |

> 상세 변경 이력: `log.md` 참조
