"""
safety_analytics.py  ─ UI 오케스트레이터 (v3.0)
────────────────────────────────────────────────────────────
비즈니스 로직은 safety_core.py 에서 import.
UI(Streamlit) 전용 로직만 이 파일에 유지.

실행:
    streamlit run safety_analytics.py

필수 패키지:
    pip install streamlit duckdb pandas altair pymupdf4llm \
                langchain-ollama langchain scikit-learn openpyxl
"""

# ══════════════════════════════════════════════════════════════
# 0. 공통 임포트
# ══════════════════════════════════════════════════════════════
import streamlit as st
import os, sys, json, tempfile, re, io
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from railway_agent.agent_ui import render_agent_tab

import pandas as pd
import numpy as np
import altair as alt

# ── Core 비즈니스 로직 (safety_core.py) ──────────────────────
from safety_core import (
    _get_conn,
    calculate_risk,
    insert_accident,
    get_all_accidents,
    get_accident_count,
    generate_scenarios,
    SHARED_DIR,
    _is_qwen3,
)
from ui.tab_input    import render_input_tab
from ui.tab_data     import render_data_tab
from ui.tab_dashboard import render_dashboard_tab
from ui.tab_risk     import render_risk_tab
from ui.tab_forecast import render_forecast_tab

# ── LLM (PDF 추출용 — UI 강화 버전 로컬 유지) ────────────────
try:
    from langchain_ollama import ChatOllama
    from langchain.schema import HumanMessage, SystemMessage
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

# ── PDF ──────────────────────────────────────────────────────
try:
    import pymupdf4llm
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# ── DuckDB ───────────────────────────────────────────────────
try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False
    st.error("duckdb 미설치: `pip install duckdb`")
    st.stop()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ══════════════════════════════════════════════════════════════
# 1. UI 전용 DB 유틸
# ══════════════════════════════════════════════════════════════
# _get_conn, calculate_risk, insert_accident, get_all_accidents,
# get_accident_count, generate_scenarios → safety_core 에서 import

# ── 예측 모델 가중치 (predict_risk_statistical 전용) ──────────
RISK_WEIGHTS = {
    'event_risk': {
        '탈선':85,'충돌':90,'화재':95,'폭발':100,
        '추락':80,'끼임':65,'감전':70,'누출':75,
        '신호무응답':60,'차량고장':40,'궤도틀림':55,
        '전력고장':45,'기타':30,
    },
    'cause_weight': {'인적요인':1.2,'기술적요인':1.0,'환경적요인':0.8},
    'weather_weight': {'맑음':1.0,'흐림':1.1,'비':1.3,'눈':1.5,'안개':1.4,'강풍':1.4},
}

def delete_accident(row_id: int):
    conn = _get_conn()
    conn.execute("DELETE FROM accidents WHERE id = ?", [row_id])
    conn.close()


# ══════════════════════════════════════════════════════════════
# 2. 예측 모델 (risk_model 인라인)
# ══════════════════════════════════════════════════════════════

def find_similar_accidents(df: pd.DataFrame, query: dict, top_k: int = 5) -> pd.DataFrame:
    if df.empty or len(df) < 2:
        return df.head(top_k)
    scores = pd.Series(0.0, index=df.index)
    for col, weight in [('노선',3.0),('이벤트소분류',4.0),('근본원인그룹',2.0),
                         ('기상상태',1.0),('열차종류',1.5),('장소대분류',2.0)]:
        if col in df.columns and col in query and query[col]:
            scores += df[col].eq(query[col]).astype(float) * weight
    df = df.copy()
    df['_sim'] = scores
    return df.nlargest(top_k, '_sim').drop(columns=['_sim'])

def predict_risk_statistical(df: pd.DataFrame, scenario: dict) -> dict:
    if df.empty:
        return {'predicted_score':50.0,'predicted_grade':'Medium',
                'confidence':'낮음 (데이터 없음)','basis':'데이터 없음','similar_count':0}
    similar = find_similar_accidents(df, scenario, top_k=20)
    n = len(similar)
    base_score = similar['risk_score'].mean() if 'risk_score' in similar.columns and similar['risk_score'].notna().any() else 50.0
    weather = scenario.get('기상상태','맑음')
    w_mult  = RISK_WEIGHTS['weather_weight'].get(weather, 1.0)
    cause   = scenario.get('근본원인그룹','')
    c_mult  = RISK_WEIGHTS['cause_weight'].get(cause, 1.0)
    evt_sub = scenario.get('이벤트소분류','')
    evt_base= RISK_WEIGHTS['event_risk'].get(evt_sub, 0)
    final   = (base_score*0.7 + evt_base*0.3)*w_mult*c_mult if evt_base > 0 else base_score*w_mult*c_mult
    final   = min(round(final,1), 100)
    grade   = ('Critical' if final>=80 else 'High' if final>=60 else 'Medium' if final>=25 else 'Low')
    conf    = '높음' if n>=10 else ('보통' if n>=5 else '낮음 (유사 사례 부족)')
    basis   = f"유사 {n}건 평균 {base_score:.0f}점 / 기상({weather}) ×{w_mult} / 원인({cause or '미상'}) ×{c_mult:.1f}"
    return {'predicted_score':final,'predicted_grade':grade,'confidence':conf,
            'basis':basis,'similar_count':n,'similar_df':similar}

def run_anomaly_detection(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) < 10:
        return df.assign(anomaly_score=None, is_anomaly=False)
    try:
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import LabelEncoder
        import warnings; warnings.filterwarnings('ignore')
        nums = ['사망자수','부상자수','피해액(백만원)','최대지연시간(분)','지연열차수','risk_score']
        cats = ['이벤트소분류','근본원인그룹','기상상태']
        work = df.copy()
        for c in nums:
            work[c] = pd.to_numeric(work.get(c, pd.Series([0]*len(work))), errors='coerce').fillna(0)
        for c in cats:
            if c in work.columns:
                le = LabelEncoder()
                work[c+'_enc'] = le.fit_transform(work[c].fillna('unknown'))
        X_cols = nums + [c+'_enc' for c in cats if c in work.columns]
        X = work[[c for c in X_cols if c in work.columns]].values
        model = IsolationForest(contamination=0.1, random_state=42)
        sc = model.fit_predict(X)
        df = df.copy()
        df['anomaly_score'] = np.round(-model.decision_function(X)*100, 1)
        df['is_anomaly'] = sc == -1
        return df
    except Exception:
        return df.assign(anomaly_score=None, is_anomaly=False)

# generate_scenarios → safety_core 에서 import

def analyze_trends(df: pd.DataFrame) -> dict:
    if df.empty: return {}
    return {
        'total': len(df),
        'high_risk': int(df['risk_grade'].isin(['High','Critical']).sum()) if 'risk_grade' in df.columns else 0,
        'avg_risk_score': float(df['risk_score'].mean()) if 'risk_score' in df.columns else 0,
        'total_deaths': int(df['사망자수'].fillna(0).sum()) if '사망자수' in df.columns else 0,
        'total_injured': int(df['부상자수'].fillna(0).sum()) if '부상자수' in df.columns else 0,
    }


# ══════════════════════════════════════════════════════════════
# 3. PDF 추출 (report_extractor_v2 로직 인라인)
# ══════════════════════════════════════════════════════════════
COLUMNS = [
    ("발생일자","이벤트 발생 날짜. YYYY-MM-DD"),
    ("발생시간","이벤트 발생 시간. HH:MM"),
    ("등록기관","데이터를 등록·보고한 기관명"),
    ("철도구분","일반철도/도시철도/고속철도"),
    ("노선","노선명"),
    ("이벤트대분류","사고/장애/고장"),
    ("이벤트중분류","차량/신호/선로/전력/외부요인 등"),
    ("이벤트소분류","탈선, 충돌, 화재 등"),
    ("주원인","1차 원인 요약"),
    ("근본원인그룹","인적요인/기술적요인/환경적요인"),
    ("근본원인유형","운전취급, 열차차량설비 등"),
    ("근본원인상세","상세 원인 설명"),
    ("직접원인","직접 원인"),
    ("운행영향유형","운행중단/지연운행/서행운전"),
    ("지연여부","지연/무지연"),
    ("지연원인","지연 주요 원인"),
    ("지연원인상세","지연 상세 사유"),
    ("지연열차수","숫자"),
    ("최대지연시간(분)","숫자"),
    ("총피해인원","숫자"),
    ("사망자수","숫자"),
    ("부상자수","숫자"),
    ("피해액(백만원)","숫자"),
    ("행정구역","행정 주소"),
    ("발생역A","기준역"),
    ("발생역B","인접역"),
    ("장소대분류","역/본선/기지"),
    ("장소중분류","구내선로/본선/승강장"),
    ("상세위치","상세 위치"),
    ("기상상태","맑음/흐림/비/눈/안개"),
    ("온도","℃ 숫자"),
    ("강우량","mm 숫자"),
    ("적설량","cm 숫자"),
    ("대상구분","열차/차량/설비"),
    ("열차종류","전동열차/화물열차/여객열차/KTX"),
    ("선로유형","지상/지하/교량"),
    ("신호시스템유형","ATP/ATO, 자동폐색 등"),
    ("고장부품명","부품명"),
    ("고장현상","현상 설명"),
    ("고장원인","기술적 원인"),
    ("조치내용","조치 내용 요약"),
    ("이벤트개요","3~5문장 요약"),
    ("데이터출처","출처"),
]
COLUMN_NAMES = [c[0] for c in COLUMNS]

BATCHES = [COLUMNS[0:9], COLUMNS[9:18], COLUMNS[18:26], COLUMNS[26:34], COLUMNS[34:]]
BATCH_NAMES = ["기본정보","원인·지연","피해·위치A","위치·기상","선로·고장·개요"]

# _is_qwen3 → safety_core 에서 import

def _clean_llm(raw: str) -> str:
    """LLM 응답에서 노이즈 제거 — qwen3 think 블록·마크다운 코드펜스 등"""
    # 1) 완결된 <think>...</think> 제거
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    # 2) 미완결 <think> (닫힘 태그 없음) → <think> 이후 첫 { 전까지 제거
    if "<think>" in raw:
        brace = raw.find("{", raw.find("<think>"))
        if brace != -1:
            raw = raw[brace:]
        else:
            raw = re.sub(r"<think>.*", "", raw, flags=re.DOTALL)
    # 3) 마크다운 코드블록 제거
    raw = re.sub(r"```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = raw.replace("```", "")
    # 4) JSON 앞 자연어 서문 제거 (첫 { 이전 텍스트)
    brace = raw.find("{")
    if brace > 0:
        raw = raw[brace:]
    return raw.strip()

def _safe_json(text: str) -> dict:
    """강화된 JSON 파싱 — Python 3.9 호환, 6단계 fallback"""
    text = _clean_llm(text)

    def _repair(s):
        s = re.sub(r',\s*([}\]])', r'\1', s)           # trailing comma
        s = re.sub(r'//[^\n]*', '', s)                  # // 주석
        s = re.sub(r'/\*.*?\*/', '', s, flags=re.DOTALL)
        return s

    def _fix_sq(s):
        """단따옴표 키/값만 쌍따옴표로 교체 (내부 아포스트로피 보호)"""
        s = re.sub(r"'([^'\n]{1,80})'\s*:", r'"\1":', s)
        s = re.sub(r":\s*'([^'\n]*?)'", r': "\1"', s)
        return s

    blk = (re.search(r'\{[\s\S]*\}', text) or None)
    blk_str = blk.group() if blk else ""

    for candidate in ([text, blk_str] if blk_str else [text]):
        for transform in [lambda s: s, _repair, _fix_sq,
                          lambda s: _repair(_fix_sq(s))]:
            try:
                t = transform(candidate)
                r = json.loads(t)
                if isinstance(r, dict) and r:
                    return r
            except Exception:
                pass

    # 최후 수단: 키-값 정규식 스캔
    result = {}
    for key, _ in COLUMNS:
        k = re.escape(key)
        ms = re.search(r'["\']?' + k + r'["\']?\s*:\s*["\']([^"\'\\n]{0,300})["\']', text)
        if ms and ms.group(1).strip() not in ('null', 'NULL', 'None', ''):
            result[key] = ms.group(1).strip()
            continue
        mn = re.search(r'["\']?' + k + r'["\']?\s*:\s*(-?\d+\.?\d*)', text)
        if mn:
            result[key] = mn.group(1)
    return result

def _regex_base(t: str) -> dict:
    """정규식 기반 1차 추출 — LLM 미사용 시 또는 LLM 실패 필드 보완"""
    d = {}
    # ── 날짜·시간 ─────────────────────────────────────────────
    dm = re.search(r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', t)
    if dm: d['발생일자'] = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
    tm = re.search(r'(\d{1,2})시\s*(\d{2})분', t)
    if tm: d['발생시간'] = f"{int(tm.group(1)):02d}:{tm.group(2)}"

    # ── 기관·철도구분 ─────────────────────────────────────────
    AGENCIES = ['서울교통공사','KORAIL','한국철도공사','부산교통공사','대구도시철도',
                '광주도시철도','대전도시철도','인천교통공사','SR','공항철도']
    for ag in AGENCIES:
        if ag in t: d['등록기관'] = ag; break
    if 'KTX' in t or '고속철도' in t or 'SRT' in t: d['철도구분'] = '고속철도'
    elif any(k in t for k in ['호선','지하철','도시철도']): d['철도구분'] = '도시철도'
    else: d['철도구분'] = '일반철도'

    # ── 노선 ──────────────────────────────────────────────────
    nm = re.search(
        r'(서울\s*\d+호선|부산\s*\d+호선|대구\s*\d+호선|인천\s*\d+호선|'
        r'광주\s*\d+호선|대전\s*\d+호선|경부선|경인선|수인선|중앙선|'
        r'분당선|신분당선|공항철도|경강선|KTX|SRT)', t
    )
    if nm: d['노선'] = nm.group(1).replace(' ', '')

    # ── 이벤트 분류 ───────────────────────────────────────────
    EVT_MAP = {
        '탈선': ('사고','차량','탈선'), '충돌': ('사고','차량','충돌'),
        '화재': ('사고','차량','화재'), '추락': ('사고','인적','추락'),
        '신호장애': ('장애','신호','신호장애'), '전력장애': ('장애','전력','전력장애'),
        '차량고장': ('장애','차량','차량고장'), '선로장애': ('장애','선로','선로장애'),
    }
    for kw, (大, 中, 小) in EVT_MAP.items():
        if kw in t:
            d.update({'이벤트대분류':大, '이벤트중분류':中, '이벤트소분류':小})
            break

    # ── 인명피해 ──────────────────────────────────────────────
    dead = re.search(r'사망자?\s*(\d+)\s*명', t)
    d['사망자수'] = dead.group(1) if dead else '0'
    inj = re.search(r'부상자?\s*(\d+)\s*명', t)
    d['부상자수'] = inj.group(1) if inj else '0'
    d['총피해인원'] = str(int(d.get('사망자수','0') or 0) + int(d.get('부상자수','0') or 0))

    # ── 피해액 ────────────────────────────────────────────────
    dmg = re.search(r'(?:총\s*)?([\d,]+)\s*백만\s*원', t)
    if dmg: d['피해액(백만원)'] = dmg.group(1).replace(',','')
    else:
        dmg2 = re.search(r'([\d,]+)\s*원(?!권)', t)
        if dmg2:
            won = int(dmg2.group(1).replace(',',''))
            if won >= 1_000_000:
                d['피해액(백만원)'] = str(round(won / 1_000_000, 1))

    # ── 지연 ──────────────────────────────────────────────────
    delay = re.search(r'(\d+)\s*분(?:\s*(?:지연|운휴|중단))', t)
    if delay: d['최대지연시간(분)'] = delay.group(1)
    dly_cnt = re.search(r'(\d+)\s*(?:개|편)?\s*열차(?:\s*지연)?', t)
    if dly_cnt: d['지연열차수'] = dly_cnt.group(1)
    if any(k in t for k in ['운행 중단','운행중단','운휴']): d['지연여부'] = '지연'
    elif any(k in t for k in ['지연','서행']): d['지연여부'] = '지연'
    else: d['지연여부'] = '무지연'

    # ── 위치 ──────────────────────────────────────────────────
    sta = re.search(r'([가-힣]+역)(?:\s*(\d+)번\s*승강장)?', t)
    if sta:
        d['발생역A'] = sta.group(1)
        if sta.group(2): d['상세위치'] = f"{sta.group(2)}번 승강장"
    if '승강장' in t: d.setdefault('장소중분류', '승강장')
    if '구내선로' in t: d.setdefault('장소중분류', '구내선로')
    if '역' in t: d.setdefault('장소대분류', '역')
    elif '기지' in t or '차량기지' in t: d['장소대분류'] = '기지'

    # ── 기상·환경 ─────────────────────────────────────────────
    for kw, wv in {'맑았':'맑음','맑음':'맑음','흐림':'흐림','비':'비','눈':'눈','안개':'안개'}.items():
        if kw in t: d['기상상태'] = wv; break
    temp = re.search(r'(-?\d+(?:\.\d+)?)\s*℃', t)
    if temp: d['온도'] = temp.group(1)

    # ── 기술 ──────────────────────────────────────────────────
    if '지하' in t: d['선로유형'] = '지하'
    elif '교량' in t: d['선로유형'] = '교량'
    else: d.setdefault('선로유형', '지상')
    if 'ATP' in t and 'ATO' in t: d['신호시스템유형'] = 'ATP/ATO'
    elif 'ATP' in t: d['신호시스템유형'] = 'ATP'
    elif '자동폐색' in t: d['신호시스템유형'] = '자동폐색'

    # ── 열차종류 ──────────────────────────────────────────────
    if '전동열차' in t or '전동차' in t: d['열차종류'] = '전동열차'
    elif 'KTX' in t: d['열차종류'] = 'KTX'
    elif 'SRT' in t: d['열차종류'] = 'SRT'
    elif '화물' in t: d['열차종류'] = '화물열차'

    return d

# 배치별 보고서 텍스트 슬라이스 전략
# - 기본정보(배치0): 앞부분 집중 (제목·일시·노선)
# - 원인·지연(배치1): 중간부분 (조사결과·원인분석)
# - 피해·위치(배치2): 앞+중간 (피해현황·사고위치)
# - 위치·기상(배치3): 중간+뒷부분 (현장조건·기상)
# - 선로·고장·개요(배치4): 뒷부분 전체 (기술분석·조치)
BATCH_SLICE = [
    (0,    10000),   # 배치0 기본정보: 앞 10000자
    (3000, 16000),   # 배치1 원인·지연: 3000~16000자
    (0,    12000),   # 배치2 피해·위치A: 앞 12000자
    (5000, 18000),   # 배치3 위치·기상: 5000~18000자
    (8000, None),    # 배치4 선로·고장·개요: 8000자 이후 전체
]

def _slice_text(report_text: str, batch_idx: int) -> str:
    """배치 인덱스에 따라 보고서 적절 구간 추출. 최대 12000자."""
    start, end = BATCH_SLICE[batch_idx]
    chunk = report_text[start:end] if end else report_text[start:]
    return chunk[:12000]  # 안전 상한 (num_ctx=32768 기준)

def _build_batch_prompt(batch_cols, report_text, model_name, batch_idx=0):
    prefix = "/no_think\n" if _is_qwen3(model_name) else ""
    schema_keys = ", ".join(f'"{n}"' for n, _ in batch_cols)
    guide = "\n".join(f'  - "{n}": {desc}' for n, desc in batch_cols)
    text_chunk = _slice_text(report_text, batch_idx)

    # Few-shot 예시 (숫자 필드 명확화)
    num_fields = {n for n, d in batch_cols if any(k in d for k in ['숫자','수','분','℃','mm','cm'])}
    num_note = ""
    if num_fields:
        examples = ", ".join(f'"{n}": 0' for n in list(num_fields)[:3])
        num_note = f'\n숫자 필드는 따옴표 없이 숫자로만. 예: {{{examples}}}\n'

    # 출력 템플릿: 키=null 형태로 LLM이 구조 그대로 채우도록
    json_template = "{" + ", ".join(f'"{n}": null' for n, _ in batch_cols) + "}"

    return f"""{prefix}You are a railway accident report data extractor.
Extract ONLY the fields listed below from the [REPORT] and return a single JSON object.

STRICT RULES:
1. Output ONLY the JSON object — no explanation, no markdown, no code blocks
2. Use null for missing or unclear fields
3. Date format: "YYYY-MM-DD", Time format: "HH:MM"
4. Numeric fields: use numbers without quotes (e.g. 3, not "3"){num_note}
FIELDS TO EXTRACT:
{guide}

OUTPUT TEMPLATE (fill in the values, keep null if not found):
{json_template}

[REPORT]
{text_chunk}

JSON:"""

def extract_from_pdf(pdf_bytes: bytes, model_name: str, progress_fn=None) -> tuple:
    if not PDF_AVAILABLE:
        raise RuntimeError("pymupdf4llm 미설치: pip install pymupdf4llm")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf_bytes); tmp_path = tmp.name

    try:
        if progress_fn: progress_fn(0.05, "📖 PDF 텍스트 추출 중...")
        report_text = pymupdf4llm.to_markdown(tmp_path)
        result = _regex_base(report_text)

        if LLM_AVAILABLE:
            llm = ChatOllama(
                model=model_name, base_url="http://127.0.0.1:11434",
                temperature=0,
                num_ctx=32768,   # ↑ 8192→32768: 한국어 장문 보고서 전체 처리
                num_predict=2048,
            )
            sys_msg = SystemMessage(content=(
                "You are a structured data extractor. "
                "Output ONLY a valid JSON object. "
                "No markdown, no code blocks, no explanations."
            ))
            for i, batch in enumerate(BATCHES):
                pct = 0.15 + 0.65 * i / len(BATCHES)
                if progress_fn: progress_fn(pct, f"🤖 배치 {i+1}/{len(BATCHES)}: {BATCH_NAMES[i]} 추출 중...")
                try:
                    # batch_idx 전달 → 배치별 최적 텍스트 구간 사용
                    prompt = _build_batch_prompt(batch, report_text, model_name, batch_idx=i)
                    resp = llm.invoke([sys_msg, HumanMessage(content=prompt)])
                    batch_result = _safe_json(resp.content)
                    for col_name, _ in batch:
                        val = batch_result.get(col_name)
                        if val is not None and str(val).strip() not in ("","null","NULL","None",""):
                            result[col_name] = str(val).strip()
                except Exception as e:
                    if progress_fn: progress_fn(pct, f"⚠️ 배치 {i+1} 오류: {e}")

        result['데이터출처'] = result.get('데이터출처') or 'PDF 자동 추출'
        # 추출률 계산 및 로깅
        total_fields = len(COLUMN_NAMES)
        extracted_fields = sum(
            1 for k in COLUMN_NAMES
            if result.get(k) and str(result[k]).strip() not in ('','None','null','NULL')
        )
        rate = extracted_fields / total_fields * 100
        msg = f"✅ 추출 완료 ({extracted_fields}/{total_fields}개 필드, {rate:.0f}%)"
        if progress_fn: progress_fn(0.95, msg)
        return result, report_text
    finally:
        if os.path.exists(tmp_path): os.remove(tmp_path)


# ══════════════════════════════════════════════════════════════
# 4. Streamlit UI
# ══════════════════════════════════════════════════════════════
st.set_page_config(page_title="🚄 철도 사고 분석 시스템", layout="wide", initial_sidebar_state="expanded")
st.title("🚄 철도 사고조사 데이터 분석 시스템")

# ── 사이드바 ──────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 설정")
    CONFIG_FILE = os.path.join(SHARED_DIR, "system_config.json")
    default_model = "qwen2.5:7b-instruct"
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                default_model = json.load(f).get("selected_model", default_model)
        except Exception:
            pass

    MODELS = ["qwen3:8b","qwen2.5:7b-instruct","llama3.1:8b"]
    try: midx = MODELS.index(default_model)
    except ValueError: midx = 1

    model_name = st.selectbox("🤖 LLM 모델", MODELS, index=midx)
    if _is_qwen3(model_name):
        st.info("💡 qwen3: /no_think 자동 적용")

    st.divider()
    total_records = get_accident_count()
    st.metric("누적 사고 데이터", f"{total_records}건")

    phase = "Phase 3 🟢" if total_records >= 200 else ("Phase 2 🟡" if total_records >= 50 else "Phase 1 🔴")
    st.caption(f"예측 모델: {phase}")
    st.caption(f"DB: shared/railway_accidents.duckdb")

    with st.expander("📌 Phase 안내"):
        st.markdown("""
- **Phase 1** (0~49건): 규칙+통계 기반
- **Phase 2** (50건~): Isolation Forest 이상탐지
- **Phase 3** (200건~): Random Forest 분류
        """)

# ── 탭 ───────────────────────────────────────────────────────
tab1, tab_data, tab2, tab3, tab4, tab_agent = st.tabs([
    "📥 보고서 입력", "📋 데이터 조회/관리", "📊 대시보드", "⚠️ 위험도 평가", "🔮 위험 예측", "🤖 AI 에이전트"
])


# ── 탭별 render 함수 호출 ─────────────────────────────────────
_column_names = [n for n, _ in COLUMNS]

with tab1:
    render_input_tab(model_name, extract_from_pdf, COLUMNS, BATCHES, _column_names)


with tab_data:
    render_data_tab(COLUMNS)


with tab2:
    render_dashboard_tab(delete_accident)


with tab3:
    render_risk_tab()


with tab4:
    render_forecast_tab()


with tab_agent:
    render_agent_tab(model_name)