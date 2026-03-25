"""
safety_core.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
safety_analytics.py 에서 Streamlit UI 의존성을 제거하고
핵심 비즈니스 로직만 추출한 공유 모듈입니다.

【목적】
  - safety_analytics.py (Streamlit UI)
  - railway_safety_agent.py (LangGraph 에이전트)
  두 파일 모두 이 모듈을 공유 임포트합니다.

【사용법】
  from safety_core import (
      extract_from_pdf, insert_accident, get_all_accidents,
      calculate_risk, generate_scenarios, get_accident_count
  )

【파일 배치】
  프로젝트 루트/
  ├── safety_analytics.py         ← 기존 Streamlit UI
  ├── safety_core.py              ← 이 파일 (신규)
  ├── railway_agent/
  │   └── railway_safety_agent.py ← 에이전트
  └── shared/
      └── railway_accidents.duckdb
"""

import os, sys, json, re, tempfile
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any

# ── 패키지 임포트 ────────────────────────────────────────────
try:
    import duckdb
    DUCKDB_OK = True
except ImportError:
    DUCKDB_OK = False

try:
    import pymupdf4llm
    PDF_OK = True
except ImportError:
    PDF_OK = False

try:
    from langchain_ollama import ChatOllama          # bind_tools 지원 버전
    from langchain_core.messages import HumanMessage, SystemMessage
    LLM_OK = True
except ImportError:
    try:
        from langchain_community.chat_models import ChatOllama  # fallback
        from langchain.schema import HumanMessage, SystemMessage
        LLM_OK = True
    except ImportError:
        LLM_OK = False

import pandas as pd


# ══════════════════════════════════════════════════════════════
# 경로 설정
# ══════════════════════════════════════════════════════════════
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.join(BASE_DIR, "shared")
DB_PATH    = os.path.join(SHARED_DIR, "railway_accidents.duckdb")
os.makedirs(SHARED_DIR, exist_ok=True)


# ══════════════════════════════════════════════════════════════
# DB 레이어
# ══════════════════════════════════════════════════════════════
DDL = """
CREATE SEQUENCE IF NOT EXISTS accidents_seq START 1;
CREATE TABLE IF NOT EXISTS accidents (
    id INTEGER PRIMARY KEY, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_file VARCHAR,
    발생일자 VARCHAR, 발생시간 VARCHAR, 등록기관 VARCHAR,
    철도구분 VARCHAR, 노선 VARCHAR,
    이벤트대분류 VARCHAR, 이벤트중분류 VARCHAR, 이벤트소분류 VARCHAR,
    주원인 VARCHAR, 근본원인그룹 VARCHAR, 근본원인유형 VARCHAR,
    근본원인상세 VARCHAR, 직접원인 VARCHAR,
    운행영향유형 VARCHAR, 지연여부 VARCHAR, 지연원인 VARCHAR, 지연원인상세 VARCHAR,
    지연열차수 INTEGER, "최대지연시간(분)" INTEGER,
    총피해인원 INTEGER, 사망자수 INTEGER, 부상자수 INTEGER,
    "피해액(백만원)" DOUBLE,
    행정구역 VARCHAR, 발생역A VARCHAR, 발생역B VARCHAR,
    장소대분류 VARCHAR, 장소중분류 VARCHAR, 상세위치 VARCHAR,
    기상상태 VARCHAR, 온도 DOUBLE, 강우량 DOUBLE, 적설량 DOUBLE,
    대상구분 VARCHAR, 열차종류 VARCHAR, 선로유형 VARCHAR,
    신호시스템유형 VARCHAR, 고장부품명 VARCHAR, 고장현상 VARCHAR,
    고장원인 VARCHAR, 조치내용 VARCHAR, 이벤트개요 VARCHAR,
    데이터출처 VARCHAR,
    risk_score DOUBLE, risk_grade VARCHAR, raw_json VARCHAR
);
"""

def _get_conn():
    conn = duckdb.connect(DB_PATH)
    conn.execute(DDL)
    return conn

def _si(v, d=None):
    try: return int(float(str(v))) if v is not None and str(v).strip() not in ('','None','null') else d
    except: return d

def _sf(v, d=None):
    try: return float(str(v)) if v is not None and str(v).strip() not in ('','None','null') else d
    except: return d

def _ss(v):
    return str(v).strip() if v is not None and str(v).strip() not in ('None','null') else None


# ══════════════════════════════════════════════════════════════
# 위험도 산정 (calculate_risk) — safety_analytics.py 와 동일
# ══════════════════════════════════════════════════════════════
def calculate_risk(extracted: dict) -> Tuple[float, str]:
    dead    = _si(extracted.get('사망자수'), 0)
    injured = _si(extracted.get('부상자수'), 0)
    damage  = _sf(extracted.get('피해액(백만원)'), 0) or 0
    delay   = _si(extracted.get('최대지연시간(분)'), 0)
    evt     = str(extracted.get('이벤트대분류','') or '')
    sub     = str(extracted.get('이벤트소분류','') or '')

    efi = dead + injured / 100.0
    score = 0.0
    score += min(efi * 20, 40)
    score += min(damage / 50, 20)
    score += min(delay / 40, 15)

    high_kw = ['탈선','충돌','화재','폭발','추락','붕괴']
    if any(k in sub for k in high_kw): score += 15
    elif evt == '사고': score += 10
    elif evt == '장애': score += 5

    if dead >= 1: score = max(score, 60.0)
    if dead >= 3 or injured >= 20: score = max(score, 80.0)
    if dead >= 5: score = max(score, 90.0)

    score = min(round(score, 1), 100)
    grade = ('Critical' if score >= 80 else
             'High'     if score >= 60 else
             'Medium'   if score >= 25 else 'Low')
    return score, grade


# ══════════════════════════════════════════════════════════════
# DB CRUD
# ══════════════════════════════════════════════════════════════
def insert_accident(extracted: dict, source_file: str = "") -> int:
    conn = _get_conn()
    risk_score, risk_grade = calculate_risk(extracted)
    row_id = conn.execute("SELECT nextval('accidents_seq')").fetchone()[0]
    conn.execute("""
        INSERT INTO accidents VALUES (
            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
        )
    """, [
        row_id, datetime.now(), source_file,
        _ss(extracted.get('발생일자')), _ss(extracted.get('발생시간')),
        _ss(extracted.get('등록기관')), _ss(extracted.get('철도구분')),
        _ss(extracted.get('노선')),
        _ss(extracted.get('이벤트대분류')), _ss(extracted.get('이벤트중분류')),
        _ss(extracted.get('이벤트소분류')), _ss(extracted.get('주원인')),
        _ss(extracted.get('근본원인그룹')), _ss(extracted.get('근본원인유형')),
        _ss(extracted.get('근본원인상세')), _ss(extracted.get('직접원인')),
        _ss(extracted.get('운행영향유형')), _ss(extracted.get('지연여부')),
        _ss(extracted.get('지연원인')), _ss(extracted.get('지연원인상세')),
        _si(extracted.get('지연열차수')), _si(extracted.get('최대지연시간(분)')),
        _si(extracted.get('총피해인원')), _si(extracted.get('사망자수')),
        _si(extracted.get('부상자수')), _sf(extracted.get('피해액(백만원)')),
        _ss(extracted.get('행정구역')), _ss(extracted.get('발생역A')),
        _ss(extracted.get('발생역B')), _ss(extracted.get('장소대분류')),
        _ss(extracted.get('장소중분류')), _ss(extracted.get('상세위치')),
        _ss(extracted.get('기상상태')), _sf(extracted.get('온도')),
        _sf(extracted.get('강우량')), _sf(extracted.get('적설량')),
        _ss(extracted.get('대상구분')), _ss(extracted.get('열차종류')),
        _ss(extracted.get('선로유형')), _ss(extracted.get('신호시스템유형')),
        _ss(extracted.get('고장부품명')), _ss(extracted.get('고장현상')),
        _ss(extracted.get('고장원인')), _ss(extracted.get('조치내용')),
        _ss(extracted.get('이벤트개요')), _ss(extracted.get('데이터출처')),
        risk_score, risk_grade,
        json.dumps(extracted, ensure_ascii=False),
    ])
    conn.close()
    return row_id

def get_all_accidents() -> pd.DataFrame:
    conn = _get_conn()
    df = conn.execute("SELECT * FROM accidents ORDER BY id DESC").df()
    conn.close()
    return df

def get_accident_count() -> int:
    conn = _get_conn()
    n = conn.execute("SELECT COUNT(*) FROM accidents").fetchone()[0]
    conn.close()
    return n


# ══════════════════════════════════════════════════════════════
# 시나리오 생성
# ══════════════════════════════════════════════════════════════
SCENARIO_TEMPLATES = {
    ('탈선','인적요인'): [
        "과속 운행 → 곡선 구간 탈선 → 선로 이탈 → 후속 열차 지장",
        "신호 오인 → 분기기 통과 중 탈선 → 승객 대피 지연",
    ],
    ('탈선','기술적요인'): [
        "궤도 변형 미점검 → 고속 통과 중 탈선 → 운행 중단",
        "차륜 균열 → 고속 주행 중 파손 → 탈선 → 대규모 지연",
    ],
    ('충돌','인적요인'): [
        "관제 통신 오류 → 동일 선로 진입 → 열차 충돌",
        "신호 무시 → 선행 열차 추돌 → 연쇄 사고",
    ],
    ('화재','기술적요인'): [
        "전동차 전장품 과부하 → 발화 → 객실 확산",
        "제동장치 과열 → 차체 하부 발화 → 역사 대피",
    ],
}

MITIGATIONS = {
    ('탈선','인적요인') : "승무원 신호 준수 교육 강화, ATP 점검 주기 단축, 피로 관리 절차 수립",
    ('탈선','기술적요인'): "궤도 정기 검측 주기 단축, 차륜/차축 비파괴 검사, 분기기 센서 이중화",
    ('충돌','인적요인') : "관제 통신 프로토콜 재정비, CTC 경보 강화, 열차 방호 장치 설치",
    ('화재','기술적요인'): "전장품 내열 등급 상향, 자동 소화 시스템, 화재 감지 센서 추가",
}

def generate_scenarios(
    event_type : str,
    cause_group: str,
    line       : str = "",
    weather    : str = "맑음"
) -> list:
    templates = SCENARIO_TEMPLATES.get((event_type, cause_group), [
        f"{event_type} 발생 → 현장 대응 지연 → 2차 피해 확대",
        f"초기 {event_type} 징후 미인지 → 적시 조치 실패 → 사고 심화",
    ])
    wf = {'눈':'적설로 제동거리 증가','비':'우천으로 시야 제한','안개':'안개로 신호 확인 지연'}.get(weather,'')
    scenarios = []
    for i, tmpl in enumerate(templates):
        desc = (f"[{line}] " if line else "") + tmpl + (f" + {wf}" if wf else "")
        sev  = 'High' if any(k in desc for k in ['추돌','화재','감전','폭발']) else ('Medium' if i==0 else 'Low')
        scenarios.append({
            'no'         : i+1,
            'scenario'   : desc,
            'severity'   : sev,
            'mitigation' : MITIGATIONS.get((event_type, cause_group),
                           "정기 안전 점검 강화, 위험 요소 모니터링, 비상 대응 훈련")
        })
    return scenarios


# ══════════════════════════════════════════════════════════════
# PDF 추출 (3단계 파이프라인)
# ══════════════════════════════════════════════════════════════
COLUMNS = [
    ("발생일자","이벤트 발생 날짜. YYYY-MM-DD"),
    ("발생시간","이벤트 발생 시간. HH:MM"),
    ("등록기관","데이터를 등록·보고한 기관명"),
    ("철도구분","일반철도/도시철도/고속철도"),
    ("노선","노선명"),
    ("이벤트대분류","사고/장애/고장"),
    ("이벤트중분류","차량/신호/선로/전력/외부요인 등"),
    ("이벤트소분류","탈선, 충돌, 화재 등 세부유형"),
    ("주원인","1차 원인 요약"),
    ("근본원인그룹","인적요인/기술적요인/환경적요인"),
    ("근본원인유형","운전취급, 열차차량설비 등"),
    ("근본원인상세","상세 원인 설명"),
    ("직접원인","직접 원인 기술"),
    ("운행영향유형","운행중단/지연운행/서행운전"),
    ("지연여부","지연/무지연"),
    ("지연원인","지연 주요 원인"),
    ("지연원인상세","지연 상세 사유"),
    ("지연열차수","지연된 열차 수. 숫자"),
    ("최대지연시간(분)","최대 지연시간. 숫자(분)"),
    ("총피해인원","사망+부상 합계. 숫자"),
    ("사망자수","사망자 수. 숫자"),
    ("부상자수","부상자 수. 숫자"),
    ("피해액(백만원)","재산 피해액. 숫자(백만원)"),
    ("행정구역","행정 주소"),
    ("발생역A","기준역 명"),
    ("발생역B","인접역 명"),
    ("장소대분류","역/본선/기지"),
    ("장소중분류","구내선로/본선/승강장"),
    ("상세위치","상세 위치 기술"),
    ("기상상태","맑음/흐림/비/눈/안개"),
    ("온도","발생 당시 온도. 숫자(℃)"),
    ("강우량","발생 당시 강우량. 숫자(mm)"),
    ("적설량","발생 당시 적설량. 숫자(cm)"),
    ("대상구분","열차/차량/설비"),
    ("열차종류","전동열차/화물열차/여객열차/KTX"),
    ("선로유형","지상/지하/교량"),
    ("신호시스템유형","ATP/ATO, 자동폐색 등"),
    ("고장부품명","고장 부품 명칭"),
    ("고장현상","고장 현상 설명"),
    ("고장원인","기술적 고장 원인"),
    ("조치내용","취해진 조치 내용 요약"),
    ("이벤트개요","3~5문장 사고 개요"),
    ("데이터출처","보고서 출처 정보"),
]
BATCHES = [COLUMNS[0:9], COLUMNS[9:18], COLUMNS[18:26], COLUMNS[26:34], COLUMNS[34:]]

def _is_qwen3(m): return "qwen3" in m.lower()

def _clean_llm(raw: str) -> str:
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    if "<think>" in raw:
        brace = raw.find("{", raw.find("<think>"))
        if brace != -1: raw = raw[brace:]
        else: raw = re.sub(r"<think>.*", "", raw, flags=re.DOTALL)
    raw = re.sub(r"```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = raw.replace("```","")
    brace = raw.find("{")
    if brace > 0: raw = raw[brace:]
    return raw.strip()

def _safe_json(text: str) -> dict:
    text = _clean_llm(text)
    def _repair(s):
        s = re.sub(r',\s*([}\]])', r'\1', s)
        s = re.sub(r'//[^\n]*', '', s)
        return s
    blk = re.search(r'\{[\s\S]*\}', text)
    blk_str = blk.group() if blk else ""
    for candidate in ([text, blk_str] if blk_str else [text]):
        for transform in [lambda s:s, _repair]:
            try:
                r = json.loads(transform(candidate))
                if isinstance(r, dict) and r: return r
            except: pass
    return {}

def _regex_base(t: str) -> dict:
    d = {}
    dm = re.search(r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', t)
    if dm: d['발생일자'] = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
    tm = re.search(r'(\d{1,2})시\s*(\d{2})분', t)
    if tm: d['발생시간'] = f"{int(tm.group(1)):02d}:{tm.group(2)}"
    for ag in ['서울교통공사','KORAIL','한국철도공사','부산교통공사','인천교통공사','SR']:
        if ag in t: d['등록기관'] = ag; break
    dead = re.search(r'사망자?\s*(\d+)\s*명', t)
    d['사망자수'] = int(dead.group(1)) if dead else 0
    inj = re.search(r'부상자?\s*(\d+)\s*명', t)
    d['부상자수'] = int(inj.group(1)) if inj else 0
    return d

BATCH_SLICE = [(0,10000),(3000,16000),(0,12000),(5000,18000),(8000,None)]

def _slice_text(text, idx):
    s, e = BATCH_SLICE[idx]
    return (text[s:e] if e else text[s:])[:12000]

def extract_from_pdf(pdf_bytes: bytes, model_name: str = "qwen2.5:3b",
                     progress_fn=None) -> Tuple[dict, str]:
    """
    3단계 PDF 추출 파이프라인.
    safety_analytics.py 와 동일한 로직.
    """
    if not PDF_OK:
        raise RuntimeError("pymupdf4llm 미설치")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        if progress_fn: progress_fn(0.05, "PDF 텍스트 추출 중...")
        report_text = pymupdf4llm.to_markdown(tmp_path)
        result = _regex_base(report_text)

        if LLM_OK:
            llm = ChatOllama(
                model=model_name, base_url="http://127.0.0.1:11434",
                temperature=0, num_ctx=32768,
                # num_predict 는 langchain_ollama 에서 num_predict → Ollama 옵션으로 전달
                num_predict=2048,
            )
            for i, batch_cols in enumerate(BATCHES):
                if progress_fn:
                    progress_fn(0.1 + i*0.17, f"배치 {i+1}/5 추출 중...")
                prefix = "/no_think\n" if _is_qwen3(model_name) else ""
                schema_keys = ", ".join(f'"{n}"' for n,_ in batch_cols)
                guide = "\n".join(f'  - "{n}": {desc}' for n,desc in batch_cols)
                text_chunk = _slice_text(report_text, i)
                json_tmpl = "{" + ", ".join(f'"{n}": null' for n,_ in batch_cols) + "}"
                prompt = (
                    f"{prefix}You are a railway accident report data extractor.\n"
                    f"Extract ONLY the fields listed below from the [REPORT] and return a single JSON object.\n"
                    f"STRICT RULES:\n1. Output ONLY the JSON object — no explanation, no markdown\n"
                    f"2. Use null for missing fields\n3. Date: YYYY-MM-DD, Time: HH:MM\n"
                    f"4. Numeric fields: use numbers without quotes\n"
                    f"FIELDS:\n{guide}\nOUTPUT TEMPLATE:\n{json_tmpl}\n[REPORT]\n{text_chunk}\nJSON:"
                )
                sys_msg = SystemMessage(content="You are a structured data extractor. Output ONLY valid JSON.")
                human_msg = HumanMessage(content=prompt)
                try:
                    raw = llm.invoke([sys_msg, human_msg]).content
                    batch_result = _safe_json(raw)
                    for k, v in batch_result.items():
                        if v is not None and str(v).strip() not in ('','null','None'):
                            result[k] = v
                except Exception:
                    pass

        return result, report_text

    finally:
        os.unlink(tmp_path)
