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
    from langchain_core.messages import HumanMessage, SystemMessage
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
_FULL_TEXT_LIMIT = 28000  # 정확도 우선 — 모든 배치가 전체 보고서 사용

def _slice_text(report_text: str, batch_idx: int = 0) -> str:
    """모든 배치에 전체 보고서를 제공 (정확도 우선)."""
    return report_text[:_FULL_TEXT_LIMIT]

# 배치별 필드 추출 힌트 (한국어, 값을 찾는 단서 제공)
_BATCH_HINTS = {
    0: "",  # 기본정보: 힌트 불필요
    1: (   # 원인·지연: 분류형 필드 추출 지침 (분류·파생 유도로 누락 방지)
        "\n\n[배치2 추출 지침 — 원인·지연 분석. 반드시 준수]\n"
        "보고서의 '원인', '분석', '고찰', '지연', '조치', '결론' 관련 서술을 근거로 아래를 채우세요.\n"
        "- 근본원인그룹: 근본 원인을 다음 중 하나로 분류 — 인적요인(운전·취급·판단·정비 실수), "
        "기술적요인(설비·차량·부품·시설 결함/노후), 환경적요인(기상·외부충격·자연). "
        "원인이 서술돼 있으면 반드시 하나를 선택\n"
        "- 근본원인유형: 근본원인의 세부 유형 (예: 운전취급, 신호취급, 열차차량설비, 선로시설, 전기설비, 유지보수 등)\n"
        "- 근본원인상세: 근본 원인을 구체적으로 설명한 문장\n"
        "- 직접원인: 사고를 직접 촉발한 방아쇠. ⚠️ 사고 결과(예: '열차 탈선')를 그대로 쓰지 말고, "
        "그 탈선/사고를 유발한 직전 요인을 쓰세요 (예: 선로좌굴, 차륜 슬립, 신호 오취급)\n"
        "- 운행영향유형: 운행 영향을 다음 중 하나로 — 운행중단, 지연운행, 서행운전. "
        "열차가 중단·지연·서행했으면 반드시 하나를 선택\n"
        "- 지연여부: 지연·운휴·서행이 있었으면 '지연', 전혀 없으면 '무지연'\n"
        "- 지연원인: 지연이 발생한 주된 이유 (지연이 있으면 반드시 추출)\n"
        "- 지연원인상세: 지연 상황을 구체적으로 설명한 문장\n"
        "- 지연열차수: 지연·운휴된 열차 편수 (숫자만)\n"
        "분류형 필드(근본원인그룹, 운행영향유형)는 보고서에 원인·영향이 서술돼 있으면 "
        "맥락으로 판단해 반드시 채우고, 근거가 전혀 없을 때만 null 로 두세요.\n"
    ),
    2: (   # 피해·위치A: 행정구역 오채움 방지
        "\n\n[배치3 추출 지침]\n"
        "- 행정구역: 보고서에 명시된 행정 주소(시/군/구, 예: 경기도 파주시)만 추출. "
        "⚠️ 노선명(예: 경의선)·역명을 행정구역에 넣지 마세요. 주소가 없으면 null.\n"
        "- 최대지연시간(분): 실제 지연된 시간(분)이 명시된 경우만 숫자로. 없으면 null.\n"
    ),
    3: "",  # 위치·기상: 힌트 불필요
    4: (
        "\n\n[배치4 추출 지침 — 반드시 준수]\n"
        "아래 필드는 보고서의 어느 위치에든 있을 수 있습니다. 전체 보고서를 꼼꼼히 읽고 추출하세요.\n"
        "- 고장부품명: 사고/고장의 **직접 원인이 된 핵심 부품·요소**만 최대 1~2개 (예: 선로전환기, 차륜, 레일). "
        "⚠️ 사고 후 '피해내역·교체목록·점검표'에 나열된 부품을 전부 옮기지 마세요. "
        "탈선처럼 특정 고장부품이 없는 사고는 원인 요소(예: 선로, 차륜)만 쓰거나 null.\n"
        "- 고장현상: 실제 발생한 고장/이상 증상을 간결히 (예: 동작불량, SLIP 발생, 절연파괴). 부품 목록 나열 금지.\n"
        "- 고장원인: 기술적 근본 원인을 **한 문장**으로 (예: 선로좌굴, 차륜 슬립, 부품 노후). "
        "⚠️ 부품명을 여러 개 나열하지 말고 원인 자체를 서술하세요.\n"
        "- 조치내용: 사고/장애 발생 후 취한 핵심 조치를 요약 (예: 현장출동, 부품교체, 열차억류, 대피유도).\n"
        "- 이벤트개요: 위 보고서 내용을 바탕으로 한국어 3~5문장으로 사고 개요를 직접 작성하세요\n"
    ),
}

def _build_batch_prompt(batch_cols, report_text, model_name, batch_idx=0):
    text_chunk = _slice_text(report_text, batch_idx)
    guide_lines = []
    for n, desc in batch_cols:
        guide_lines.append(f'  "{n}": {desc}')
    guide = "\n".join(guide_lines)
    json_template = "{" + ", ".join(f'"{n}": null' for n, _ in batch_cols) + "}"
    hint = _BATCH_HINTS.get(batch_idx, "")

    return (
        "당신은 철도사고 조사보고서 분석 전문가입니다.\n"
        "아래 [보고서]에서 지정된 필드 값을 추출하여 JSON 객체 하나만 출력하세요.\n\n"
        "【규칙】\n"
        "1. JSON 객체만 출력 — 설명·마크다운·코드블록 금지\n"
        "2. 보고서에 없는 정보만 null 사용 (있으면 반드시 추출)\n"
        "3. 날짜: YYYY-MM-DD, 시간: HH:MM\n"
        "4. 숫자 필드: 따옴표 없이 숫자만 (예: 3, 15.5)\n"
        f"5. 모든 텍스트 값은 한국어로 작성{hint}\n\n"
        "【추출 필드】\n"
        f"{guide}\n\n"
        "【출력 형식】\n"
        f"{json_template}\n\n"
        "【보고서 전문】\n"
        f"{text_chunk}\n\n"
        "JSON 출력:"
    )

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
            # format="json" 제거 — Ollama JSON 문법 제약이 한국어 텍스트 생성을 차단함
            llm_kwargs = dict(
                model=model_name, base_url="http://127.0.0.1:11434",
                temperature=0,
                num_ctx=16384,      # 32768→16384: 텍스트 전량 수용, 스왑 완화로 속도 이득
                num_predict=4096,
                keep_alive="30m",   # 모델 상주 — 연속 처리 시 파일마다 재로딩 제거
            )
            if _is_qwen3(model_name):
                llm_kwargs["reasoning"] = False
            llm = ChatOllama(**llm_kwargs)
            sys_msg = SystemMessage(content=(
                "당신은 철도사고 조사보고서 분석 전문가입니다. "
                "요청된 필드를 보고서에서 정확히 추출하여 JSON 객체만 출력하세요. "
                "설명, 마크다운, 코드블록 없이 JSON만 출력합니다."
            ))

            def _run_batch(prompt_text, cols, label=""):
                msgs = [sys_msg, HumanMessage(content=prompt_text)]
                for attempt in range(2):
                    try:
                        resp = llm.invoke(msgs)
                        parsed = _safe_json(resp.content)
                        if parsed:
                            return parsed
                    except Exception as e:
                        err = str(e)
                        if "not found" in err or "404" in err:
                            if progress_fn:
                                progress_fn(0, f"❌ 모델 '{model_name}' 을 찾을 수 없습니다. Ollama에서 모델명을 확인하세요.")
                            return {}
                        if attempt == 1 and progress_fn:
                            progress_fn(0, f"⚠️ {label} LLM 오류: {err[:120]}")
                return {}

            # ── 배치 추출 (5배치, 모두 전체 보고서 사용) ─────────────────
            for i, batch in enumerate(BATCHES):
                pct = 0.15 + 0.55 * i / len(BATCHES)
                if progress_fn: progress_fn(pct, f"🤖 배치 {i+1}/{len(BATCHES)}: {BATCH_NAMES[i]} 추출 중...")
                prompt = _build_batch_prompt(batch, report_text, model_name, batch_idx=i)
                batch_result = _run_batch(prompt, batch, label=f"배치{i+1}")
                for col_name, _ in batch:
                    val = batch_result.get(col_name)
                    if val is not None and str(val).strip() not in ("","null","NULL","None",""):
                        result[col_name] = str(val).strip()

            # ── 고장 5개 필드 전용 재추출 ─────────────────────────────────
            FAULT_FIELDS = ["고장부품명", "고장현상", "고장원인", "조치내용"]
            null_fault = [f for f in FAULT_FIELDS
                          if not result.get(f) or str(result[f]).strip() in ("","null","NULL","None")]
            if null_fault:
                if progress_fn: progress_fn(0.75, f"🔧 고장 필드 재추출 중... ({', '.join(null_fault)})")
                fault_cols = [(n, d) for n, d in COLUMNS if n in null_fault]
                fault_guide = "\n".join(
                    f'  "{n}": {d}  ← 핵심만 간결히 (없으면 null)' for n, d in fault_cols
                )
                fault_tmpl = "{" + ", ".join(f'"{n}": null' for n in null_fault) + "}"
                fault_prompt = (
                    "당신은 철도사고 보고서 분석 전문가입니다.\n"
                    "아래 보고서에서 고장/조치의 핵심 정보만 간결히 추출하여 JSON으로 출력하세요.\n\n"
                    "【중요 규칙】\n"
                    "- 고장부품명: 사고의 직접 원인이 된 핵심 부품 1~2개만. "
                    "'피해내역·교체목록·점검표'에 나열된 부품 전체를 옮기지 마세요. "
                    "특정 고장부품이 없으면(예: 탈선) 원인 요소만 쓰거나 null.\n"
                    "- 고장원인: 기술적 근본 원인을 한 문장으로. 부품명 여러 개 나열 금지.\n"
                    "- 고장현상·조치내용: 핵심만 간결히 요약.\n\n"
                    f"【추출 대상】\n{fault_guide}\n\n"
                    f"【출력】{fault_tmpl}\n\n"
                    f"【보고서】\n{report_text[:_FULL_TEXT_LIMIT]}\n\n"
                    "JSON:"
                )
                fault_result = _run_batch(fault_prompt, fault_cols)
                for f in null_fault:
                    val = fault_result.get(f)
                    if val and str(val).strip() not in ("","null","NULL","None"):
                        result[f] = str(val).strip()

            # ── 이벤트개요 전용 요약 생성 ─────────────────────────────────
            if not result.get("이벤트개요") or str(result.get("이벤트개요","")).strip() in ("","null","NULL","None"):
                if progress_fn: progress_fn(0.87, "📝 이벤트개요 요약 생성 중...")
                ctx_parts = []
                for k in ["발생일자","노선","이벤트소분류","주원인","직접원인","사망자수","부상자수","조치내용"]:
                    if result.get(k): ctx_parts.append(f"{k}: {result[k]}")
                ctx_hint = "\n".join(ctx_parts)
                overview_prompt = (
                    "당신은 철도사고 조사보고서 분석 전문가입니다.\n"
                    "아래 보고서를 읽고 사고/장애의 발생 경위, 원인, 피해 규모, 조치 내용을\n"
                    "포함하여 한국어 3~5문장으로 요약하세요.\n"
                    "JSON 형식으로 다음 키 하나만 출력하세요: {\"이벤트개요\": \"요약 내용\"}\n\n"
                    + (f"[추출된 기본 정보]\n{ctx_hint}\n\n" if ctx_hint else "")
                    + f"[보고서 전문]\n{report_text[:_FULL_TEXT_LIMIT]}\n\n"
                    "JSON:"
                )
                for attempt in range(2):
                    try:
                        resp = llm.invoke([sys_msg, HumanMessage(content=overview_prompt)])
                        parsed = _safe_json(resp.content)
                        val = parsed.get("이벤트개요")
                        if val and str(val).strip() not in ("","null","NULL","None"):
                            result["이벤트개요"] = str(val).strip()
                            break
                    except Exception:
                        pass

            # ── 이벤트개요 최종 합성 fallback (LLM 실패 시) ──────────────
            if not result.get("이벤트개요") or str(result.get("이벤트개요","")).strip() in ("","null","NULL","None"):
                parts = []
                date = result.get("발생일자",""); line = result.get("노선","")
                sub = result.get("이벤트소분류","") or result.get("이벤트대분류","사고")
                if date or line:
                    parts.append(f"{date} {line} 노선에서 {sub}가 발생하였습니다.".strip())
                if result.get("주원인"):
                    parts.append(f"주요 원인은 {result['주원인']}으로 분석됩니다.")
                if result.get("직접원인"):
                    parts.append(f"직접 원인: {result['직접원인']}")
                if result.get("조치내용"):
                    parts.append(f"조치사항: {result['조치내용']}")
                if parts:
                    result["이벤트개요"] = " ".join(parts)

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
st.set_page_config(page_title="🚄 철도사고 위험도 평가 AI에이전트", layout="wide", initial_sidebar_state="expanded")
st.title("🚄 철도사고 위험도 평가 AI에이전트")


APP_VERSION = "v1.7.4"


@st.cache_data(show_spinner=False)
def _git_short_hash() -> str:
    """현재 체크아웃된 커밋의 짧은 해시를 런타임에 조회 (실패 시 'unknown')."""
    import subprocess
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


st.caption(f"{APP_VERSION} · commit `{_git_short_hash()}` · "
           "[GitHub](https://github.com/khselect/AI_Agent)")

# ── 사이드바 ──────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 설정")
    CONFIG_FILE = os.path.join(SHARED_DIR, "system_config.json")
    default_model = "qwen3:8b"
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                default_model = json.load(f).get("selected_model", default_model)
        except Exception:
            pass

    MODELS = ["qwen3:8b", "qwen3:30b-a3b", "qwen3:32b", "qwen2.5:7b-instruct", "llama3.1:8b"]
    try: midx = MODELS.index(default_model)
    except ValueError: midx = 0

    model_name = st.selectbox("🤖 LLM 모델", MODELS, index=midx)
    if _is_qwen3(model_name):
        st.info("💡 qwen3: thinking 비활성화 적용")

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