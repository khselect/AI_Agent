"""
agent_ui.py  v3.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AI 에이전트 탭 UI — 구조화 워크플로우 + 수신자 관리

【주요 개선사항】
  v2 → v3
  - 자유 텍스트 입력 → 구조화 워크플로우 선택 (파라미터 입력)
  - 버튼 클릭 session_state 버그 수정
  - 에이전트 실행 결과를 카드 형태로 가독성 있게 표시
  - 워크플로우별 에이전트 목표 자동 생성 (파라미터 조합)
  - 자유 입력 모드 유지 (고급 사용자용)
"""

import streamlit as st
import json, os
from datetime import datetime, date, timedelta
from typing import Optional

try:
    from railway_agent.railway_safety_agent import build_agent
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    AGENT_AVAILABLE = True
except ImportError:
    AGENT_AVAILABLE = False

try:
    import sys, os as _os
    sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from safety_core import _get_conn as _db_conn
    DB_AVAILABLE = True
except Exception:
    DB_AVAILABLE = False

_BASE              = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTIFY_CONFIG_PATH = os.path.join(_BASE, "shared", "notify_config.json")


@st.cache_data(ttl=300)
def _get_agency_line_map() -> dict:
    """DB에서 등록기관 → 노선 목록 매핑 조회 (5분 캐시)"""
    if not DB_AVAILABLE:
        return {}
    try:
        conn = _db_conn()
        df = conn.execute(
            "SELECT DISTINCT 등록기관, 노선 FROM accidents "
            "WHERE 등록기관 IS NOT NULL AND 등록기관 != '' "
            "AND 노선 IS NOT NULL AND 노선 != '' "
            "ORDER BY 등록기관, 노선"
        ).df()
        conn.close()
        result: dict = {}
        for agency, line in zip(df["등록기관"], df["노선"]):
            result.setdefault(agency, []).append(line)
        return result
    except Exception:
        return {}

# ══════════════════════════════════════════════════════════════
# 설정 파일
# ══════════════════════════════════════════════════════════════
DEFAULT_CONFIG = {
    "recipients": [],
    "rules": {
        "Critical": ["email", "slack", "sms"],
        "High":     ["email", "slack"],
        "Medium":   ["email"],
        "Low":      ["log"]
    },
    "notify_log": [],
    "workflow_params": {}
}

def load_config() -> dict:
    os.makedirs(os.path.dirname(NOTIFY_CONFIG_PATH), exist_ok=True)
    if os.path.exists(NOTIFY_CONFIG_PATH):
        try:
            with open(NOTIFY_CONFIG_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg: dict):
    os.makedirs(os.path.dirname(NOTIFY_CONFIG_PATH), exist_ok=True)
    with open(NOTIFY_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def append_notify_log(cfg, entry):
    cfg["notify_log"].insert(0, entry)
    cfg["notify_log"] = cfg["notify_log"][:100]
    save_config(cfg)


def _save_workflow_params(wf_name: str, params_val: dict):
    """워크플로우 파라미터를 설정 파일에 저장 (직렬화 가능한 값만)"""
    cfg = load_config()
    if "workflow_params" not in cfg:
        cfg["workflow_params"] = {}
    serializable = {}
    for k, v in params_val.items():
        if hasattr(v, "strftime"):
            serializable[k] = v.strftime("%Y-%m-%d")
        elif isinstance(v, (str, int, float, bool, list)):
            serializable[k] = v
    cfg["workflow_params"][wf_name] = serializable
    save_config(cfg)


def _restore_workflow_params(wf_name: str, wf: dict, cfg: dict):
    """저장된 파라미터를 세션 상태에 복원 (세션 최초 로드 시 한 번만 실행)"""
    init_flag = f"params_inited_{wf_name}"
    if st.session_state.get(init_flag):
        return
    st.session_state[init_flag] = True

    saved = cfg.get("workflow_params", {}).get(wf_name, {})
    if not saved:
        return

    for p_name, p_def in wf["params"].items():
        p_type = p_def[0]
        try:
            if p_type == "date_range":
                for suffix, key_name in [("df", "date_from"), ("dt", "date_to")]:
                    sk = f"p_{suffix}_{wf_name}"
                    if sk not in st.session_state and key_name in saved:
                        st.session_state[sk] = datetime.strptime(
                            saved[key_name], "%Y-%m-%d"
                        ).date()
            elif p_type == "agency_line":
                agency_sk = f"p_agency_{wf_name}_{p_name}"
                line_sk   = f"p_{p_name}_{wf_name}"
                if agency_sk not in st.session_state and f"_agency_{p_name}" in saved:
                    st.session_state[agency_sk] = saved[f"_agency_{p_name}"]
                if line_sk not in st.session_state and p_name in saved:
                    st.session_state[line_sk] = saved[p_name]
            else:
                sk = f"p_{p_name}_{wf_name}"
                if sk not in st.session_state and p_name in saved:
                    st.session_state[sk] = saved[p_name]
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════
# 워크플로우 정의 (에이전트의 실질적 활용 예시)
# ══════════════════════════════════════════════════════════════
WORKFLOWS = {

    "📊 정기 위험 현황 보고": {
        "desc": "지정 기간의 위험 사고를 조회하고 담당자에게 요약 보고",
        "why" : "기존 Tab2 대시보드는 화면만 보여줍니다. 에이전트는 DB를 실제로 조회하고 결과를 알림까지 자동 발송합니다.",
        "params": {
            "기간": ("date_range", None),
            "최소 위험등급": ("select", ["Critical", "High", "Medium", "Low"], "High"),
            "최대 건수": ("number", 10),
            "알림 발송": ("bool", True),
        },
        "goal_template": (
            "{date_from}부터 {date_to}까지 위험등급 {grade} 이상 사고를 "
            "최대 {top_n}건 조회하고, 노선·이벤트유형·사망자수 중심으로 요약해줘. "
            "{notify_str}"
        ),
    },

    "🔍 특정 노선 집중 분석": {
        "desc": "선택 노선의 사고 패턴을 분석하고 취약 구간·원인 도출",
        "why" : "기존 LLM은 실제 DB 데이터 없이 일반적 답변만 합니다. 에이전트는 해당 노선 실제 사고 이력을 조회해 분석합니다.",
        "params": {
            "노선명": ("agency_line", "경부선"),
            "분석 기간(년)": ("number", 3),
            "시나리오 생성 포함": ("bool", True),
        },
        "goal_template": (
            "{line} 노선의 최근 {years}년 사고 데이터를 조회하고 "
            "이벤트 유형별·원인별 패턴을 분석해줘. "
            "{scenario_str}"
        ),
    },

    "⚠️ 신규 사고 위험도 즉시 평가": {
        "desc": "사고 정보를 입력하면 EFI 기반 위험도를 즉시 산정하고 알림",
        "why" : "기존 Tab3은 DB에 저장된 데이터만 평가합니다. 에이전트는 현장에서 입력한 즉석 데이터도 바로 평가합니다.",
        "params": {
            "이벤트 유형": ("select", ["탈선","충돌","화재","신호장애","차량고장","추락"], "탈선"),
            "사망자수": ("number", 0),
            "부상자수": ("number", 0),
            "피해액(백만원)": ("number", 0),
            "최대지연시간(분)": ("number", 0),
            "자동 알림": ("bool", True),
        },
        "goal_template": (
            "다음 사고 데이터의 위험도를 즉시 산정해줘: "
            '{{"이벤트소분류":"{event_type}","사망자수":{dead},'
            '"부상자수":{injured},"피해액(백만원)":{damage},'
            '"최대지연시간(분)":{delay}}}. '
            "EFI 계산 과정과 Hard Constraint 적용 여부를 설명하고, "
            "{notify_str}"
        ),
    },

    "🎯 Bow-Tie 시나리오 + DB 연계 분석": {
        "desc": "DB에서 유사 과거 사고를 조회하고 시나리오에 실제 사례 반영",
        "why" : "기존 Tab5는 템플릿 기반 시나리오만 생성합니다. 에이전트는 DB에서 유사 사고를 먼저 조회한 뒤 실제 사례를 반영한 시나리오를 만듭니다.",
        "params": {
            "이벤트 유형": ("select", ["탈선","충돌","화재","신호장애","차량고장"], "탈선"),
            "근본원인": ("select", ["인적요인","기술적요인","환경적요인"], "기술적요인"),
            "노선": ("agency_line", "경부선"),
            "기상상태": ("select", ["맑음","비","눈","안개"], "맑음"),
        },
        "goal_template": (
            "먼저 DB에서 {line} 노선의 {event_type} 사고 이력을 조회하고, "
            "그 결과를 바탕으로 {cause_group} 원인의 Bow-Tie 시나리오를 생성해줘. "
            "기상: {weather}. 실제 사고 사례를 시나리오에 반영해서 구체적으로 작성해줘."
        ),
    },

    "📨 수신자별 맞춤 보고서 발송": {
        "desc": "등록된 수신자에게 역할별 맞춤 보고서를 자동 작성·발송",
        "why" : "기존 시스템은 알림이 없습니다. 에이전트는 DB 조회 → 보고서 작성 → 수신자별 발송을 한 번에 처리합니다.",
        "params": {
            "보고 기간(일)": ("number", 7),
            "보고서 형식": ("select", ["요약형(3줄)","상세형","항목별 분류"], "요약형(3줄)"),
            "수신자 선택": ("recipients", None),
        },
        "goal_template": (
            "최근 {days}일간 사고 데이터를 조회하고 {format} 보고서를 작성해줘. "
            "Critical/High 사고는 별도 강조하고, "
            "등록된 수신자에게 log 채널로 보고서를 발송해줘."
        ),
    },

    "✏️ 직접 입력 (고급)": {
        "desc": "자연어로 목표를 직접 입력하는 고급 모드",
        "why" : "위 워크플로우에 없는 복합 작업에 활용합니다.",
        "params": {
            "목표 직접 입력": ("textarea", "지난 5년간 탈선 사고를 조회하고 이벤트 유형별·원인별 패턴을 분석해줘."),
        },
        "goal_template": "{custom_goal}",
    },
}


# ══════════════════════════════════════════════════════════════
# 메인 렌더러
# ══════════════════════════════════════════════════════════════
def render_agent_tab(model_name: str = "qwen2.5:3b"):
    st.subheader("🤖 AI 에이전트 — 자율 업무 자동화")

    sub_exec, sub_recipients, sub_log = st.tabs([
        "▶ 워크플로우 실행",
        "👤 수신자 관리",
        "📋 알림 발송 이력",
    ])

    with sub_exec:
        _render_workflow(model_name)
    with sub_recipients:
        _render_recipient_manager()
    with sub_log:
        _render_notify_log()


# ══════════════════════════════════════════════════════════════
# [서브탭 1] 워크플로우 실행
# ══════════════════════════════════════════════════════════════
def _render_workflow(model_name: str):

    if not AGENT_AVAILABLE:
        st.error("에이전트 모듈 미설치")
        st.code("pip install langgraph langchain-ollama")
        return

    # ── 기존 LLM vs 에이전트 차이 안내 ──────────────────────
    with st.expander("💡 에이전트가 기존 LLM 탭과 다른 점", expanded=False):
        st.markdown("""
| | 기존 탭 (Tab3~5) | AI 에이전트 |
|---|---|---|
| **데이터** | 화면에 이미 로드된 것만 | DB를 직접 조회·필터링 |
| **작업 범위** | 단일 기능 | 조회→분석→시나리오→알림 연속 |
| **알림** | ❌ | ✅ 자동 발송 |
| **재시도** | ❌ | ✅ 실패 시 자동 재계획 |

**에이전트를 써야 할 때**: 여러 단계를 연속으로, 실제 DB 데이터를 쓰고, 알림까지 자동화하고 싶을 때
        """)

    st.divider()

    # ── 워크플로우 선택 (session_state로 버튼 버그 수정) ──────
    st.markdown("**1단계 — 워크플로우 선택**")

    if "selected_wf" not in st.session_state:
        st.session_state["selected_wf"] = list(WORKFLOWS.keys())[0]

    cols = st.columns(3)
    wf_keys = list(WORKFLOWS.keys())
    for i, key in enumerate(wf_keys):
        col = cols[i % 3]
        wf  = WORKFLOWS[key]
        is_selected = (st.session_state["selected_wf"] == key)
        btn_type = "primary" if is_selected else "secondary"
        if col.button(key, use_container_width=True, type=btn_type, key=f"wf_btn_{i}"):
            st.session_state["selected_wf"] = key
            st.rerun()

    wf_name = st.session_state["selected_wf"]
    wf      = WORKFLOWS[wf_name]

    # 선택된 워크플로우 설명
    st.info(f"**{wf_name}** — {wf['desc']}\n\n> {wf['why']}")

    st.divider()

    # ── 파라미터 입력 ─────────────────────────────────────────
    st.markdown("**2단계 — 파라미터 설정**")

    cfg        = load_config()
    recipients = cfg.get("recipients", [])
    params_val = {}

    # 저장된 파라미터 복원 (세션 최초 로드 시)
    _restore_workflow_params(wf_name, wf, cfg)

    for p_name, p_def in wf["params"].items():
        p_type = p_def[0]

        if p_type == "date_range":
            c1, c2 = st.columns(2)
            default_from = date.today() - timedelta(days=365)
            default_to   = date.today()
            params_val["date_from"] = c1.date_input("시작일", value=default_from, key=f"p_df_{wf_name}").strftime("%Y-%m-%d")
            params_val["date_to"]   = c2.date_input("종료일", value=default_to,   key=f"p_dt_{wf_name}").strftime("%Y-%m-%d")

        elif p_type == "select":
            options  = p_def[1]
            default  = p_def[2] if len(p_def) > 2 else options[0]
            val = st.selectbox(p_name, options=options, index=options.index(default) if default in options else 0, key=f"p_{p_name}_{wf_name}")
            params_val[p_name] = val

        elif p_type == "number":
            default = p_def[1]
            val = st.number_input(p_name, min_value=0, value=int(default), step=1, key=f"p_{p_name}_{wf_name}")
            params_val[p_name] = int(val)

        elif p_type == "bool":
            default = p_def[1]
            val = st.toggle(p_name, value=default, key=f"p_{p_name}_{wf_name}")
            params_val[p_name] = val

        elif p_type == "agency_line":
            default = p_def[1] if len(p_def) > 1 else ""
            agency_line_map = _get_agency_line_map()
            agencies = sorted(agency_line_map.keys())
            if agencies:
                sel_agency = st.selectbox(
                    "기관 선택 (***공사)",
                    options=agencies,
                    key=f"p_agency_{wf_name}_{p_name}"
                )
                lines = agency_line_map.get(sel_agency, [])
                if lines:
                    sel_line = st.selectbox(
                        p_name,
                        options=lines,
                        key=f"p_{p_name}_{wf_name}"
                    )
                else:
                    sel_line = st.text_input(
                        p_name, value=default,
                        placeholder="해당 기관의 노선 데이터 없음",
                        key=f"p_{p_name}_{wf_name}"
                    )
            else:
                sel_line = st.text_input(
                    p_name, value=default,
                    key=f"p_{p_name}_{wf_name}"
                )
            params_val[p_name] = sel_line
            # 기관명도 저장 대상에 포함
            if agencies:
                params_val[f"_agency_{p_name}"] = st.session_state.get(
                    f"p_agency_{wf_name}_{p_name}", ""
                )

        elif p_type == "text":
            default = p_def[1]
            val = st.text_input(p_name, value=default, key=f"p_{p_name}_{wf_name}")
            params_val[p_name] = val

        elif p_type == "textarea":
            default = p_def[1] if len(p_def) > 1 else ""
            val = st.text_area(p_name, value=default, height=100,
                               key=f"p_{p_name}_{wf_name}")
            params_val["custom_goal"] = val

        elif p_type == "recipients":
            active_r = [r for r in recipients if r.get("active", True)]
            if active_r:
                options = [f"{r['name']} ({r.get('role','')})" for r in active_r]
                selected = st.multiselect(p_name, options=options, default=options[:1], key=f"p_{p_name}_{wf_name}")
                params_val["selected_recipients"] = selected
            else:
                st.warning("수신자가 없습니다. '수신자 관리' 탭에서 먼저 등록하세요.")
                params_val["selected_recipients"] = []

    # ── 목표 자동 생성 미리보기 ───────────────────────────────
    goal = _build_goal(wf_name, wf, params_val, recipients)

    with st.expander("📝 에이전트에 전달될 목표 미리보기", expanded=False):
        st.code(goal, language="text")

    st.divider()

    # ── 실행 ──────────────────────────────────────────────────
    st.markdown("**3단계 — 실행**")

    direct_mode_key = f"direct_mode_{wf_name}"
    direct_goal_key = f"direct_goal_{wf_name}"

    if st.session_state.get(direct_mode_key, False):
        # 직접 입력 모드
        st.info("✏️ **직접 입력 모드** — 선택된 워크플로우의 목표를 자유롭게 수정하세요.")
        final_goal = st.text_area(
            "목표 편집",
            value=st.session_state.get(direct_goal_key, goal),
            height=150,
            key=direct_goal_key,
        )
        col_run2, col_exit = st.columns([3, 1])
        run_btn = col_run2.button(
            "▶ 에이전트 실행", type="primary",
            use_container_width=True, key="run_agent_btn"
        )
        if col_exit.button("✕ 종료", use_container_width=True, key="exit_direct_btn"):
            st.session_state[direct_mode_key] = False
            st.rerun()
    else:
        final_goal = goal
        col_run, col_direct = st.columns([3, 1])
        run_btn = col_run.button(
            "▶ 에이전트 실행", type="primary",
            use_container_width=True, key="run_agent_btn"
        )
        if col_direct.button(
            "✏️ 직접 입력", use_container_width=True, key="direct_input_btn"
        ):
            st.session_state[direct_mode_key] = True
            st.session_state[direct_goal_key] = goal
            st.rerun()

    if "agent_history_v3" not in st.session_state:
        st.session_state["agent_history_v3"] = []

    if run_btn:
        if not final_goal.strip() or final_goal == "{custom_goal}":
            st.warning("목표를 입력하거나 파라미터를 설정해주세요.")
            return

        _save_workflow_params(wf_name, params_val)
        _execute_agent(final_goal, wf_name, model_name, cfg)

    # ── 실행 기록 ─────────────────────────────────────────────
    if st.session_state.get("agent_history_v3"):
        st.divider()
        col_h, col_clr = st.columns([5,1])
        col_h.markdown("**실행 기록**")
        if col_clr.button("초기화", key="clear_hist"):
            st.session_state["agent_history_v3"] = []
            st.rerun()

        for item in reversed(st.session_state["agent_history_v3"]):
            _render_history_item(item)


def _build_goal(wf_name: str, wf: dict, params_val: dict, recipients: list) -> str:
    """파라미터 값으로 목표 문자열 자동 생성"""
    tmpl = wf["goal_template"]

    # 공통 변수 처리
    mapping = dict(params_val)

    # 날짜 범위
    if "date_from" in mapping and "date_to" in mapping:
        pass  # 이미 있음

    # 등급 매핑
    grade_map = {
        "최소 위험등급": "grade",
        "이벤트 유형"  : "event_type",
        "근본원인"     : "cause_group",
        "기상상태"     : "weather",
        "노선명"       : "line",
        "노선"         : "line",
        "분석 기간(년)": "years",
        "최대 건수"    : "top_n",
        "사망자수"     : "dead",
        "부상자수"     : "injured",
        "피해액(백만원)": "damage",
        "최대지연시간(분)": "delay",
        "보고 기간(일)": "days",
        "보고서 형식"  : "format",
    }
    for k, v in grade_map.items():
        if k in mapping:
            mapping[v] = mapping.pop(k) if k != "노선" else mapping.get(k, mapping.get("노선명",""))

    # 알림 문자열
    active_r = [r for r in recipients if r.get("active", True)]
    if mapping.get("알림 발송") or mapping.get("자동 알림"):
        if active_r:
            names = ", ".join(r["name"] for r in active_r[:3])
            mapping["notify_str"] = f"결과를 {names}에게 알림 발송해줘."
        else:
            mapping["notify_str"] = "결과를 log 채널로 알림 발송해줘."
    else:
        mapping["notify_str"] = ""

    # 시나리오 문자열
    if mapping.get("시나리오 생성 포함"):
        mapping["scenario_str"] = "그리고 가장 빈번한 사고 유형에 대한 Bow-Tie 시나리오도 생성해줘."
    else:
        mapping["scenario_str"] = ""

    try:
        result = tmpl.format(**mapping)
    except KeyError:
        result = tmpl

    # 직접 입력 모드: 오늘 날짜 컨텍스트 자동 주입
    # ("지난 5년", "최근 3년" 등 상대적 표현을 에이전트가 정확히 해석할 수 있도록)
    if "{custom_goal}" in tmpl or mapping.get("custom_goal"):
        today_str = date.today().strftime("%Y-%m-%d")
        result = f"[오늘 날짜: {today_str}]\n{result}"

    return result


def _execute_agent(goal: str, wf_name: str, model_name: str, cfg: dict):
    """에이전트 실행 및 결과 표시"""
    with st.status(f"🤖 '{wf_name}' 실행 중...", expanded=True) as status:
        try:
            agent = build_agent(model_name)
            init_state = {
                "messages" : [HumanMessage(content=goal)],
                "goal"     : goal,
                "results"  : {},
                "iteration": 0,
            }

            steps        = []
            final_answer = ""
            tool_count   = 0
            notify_sent  = []

            for step in agent.stream(init_state):
                for node_name, node_state in step.items():
                    for msg in node_state.get("messages", []):

                        if isinstance(msg, AIMessage):
                            if hasattr(msg, "tool_calls") and msg.tool_calls:
                                for tc in msg.tool_calls:
                                    tname = tc.get("name","")
                                    targs = tc.get("args",{})
                                    tool_count += 1
                                    icon = {"notify_tool":"📨","query_db_tool":"🗄️",
                                            "assess_risk_tool":"⚠️","scenario_tool":"🎯",
                                            "extract_pdf_tool":"📄","save_db_tool":"💾",
                                            "web_collect_tool":"🌐"}.get(tname,"🔧")
                                    st.write(f"{icon} `{tname}` 호출 #{tool_count}")
                                    with st.expander("인수", expanded=False):
                                        st.json(targs)
                                    steps.append({"type":"tool_call","name":tname,"args":targs,"icon":icon})

                            elif msg.content:
                                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                                if content.strip():
                                    st.write(f"💬 {content}")
                                    final_answer = content
                                    steps.append({"type":"response","content":content})

                        elif isinstance(msg, ToolMessage):
                            try:
                                rd = json.loads(msg.content)
                                st.write("✅ 결과:")
                                st.json(rd)
                                steps.append({"type":"tool_result","data":rd})
                                if isinstance(rd, dict) and rd.get("status") == "발송 완료":
                                    notify_sent.append(rd)
                            except Exception:
                                st.write(f"✅ {str(msg.content)[:300]}")
                                steps.append({"type":"tool_result","data":str(msg.content)})

            status.update(label="✅ 완료", state="complete")

            # 알림 이력 저장
            if notify_sent:
                cfg = load_config()
                for n in notify_sent:
                    append_notify_log(cfg, {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "goal"     : goal[:80],
                        "channel"  : n.get("channel",""),
                        "message"  : str(n.get("message",""))[:200],
                    })

            # 실행 기록 저장
            st.session_state["agent_history_v3"].append({
                "timestamp"   : datetime.now().strftime("%H:%M:%S"),
                "wf_name"     : wf_name,
                "goal"        : goal,
                "steps"       : steps,
                "final_answer": final_answer,
                "tool_count"  : tool_count,
                "notify_count": len(notify_sent),
            })

        except Exception as e:
            status.update(label="❌ 오류", state="error")
            st.error(f"오류: {e}")
            import traceback
            with st.expander("상세 오류"):
                st.code(traceback.format_exc())


def _render_history_item(item: dict):
    notify_badge = f"📨 알림 {item['notify_count']}건" if item.get("notify_count") else ""
    label = (
        f"[{item['timestamp']}] {item['wf_name']} "
        f"— 도구 {item.get('tool_count',0)}회 실행 {notify_badge}"
    )
    with st.expander(label, expanded=False):
        # 최종 답변 카드
        if item.get("final_answer"):
            st.success(item["final_answer"])

        # 실행 단계 타임라인
        st.markdown("**실행 단계**")
        for i, s in enumerate(item["steps"]):
            if s["type"] == "tool_call":
                st.markdown(f"{s.get('icon','🔧')} **{s['name']}**")
            elif s["type"] == "tool_result":
                with st.expander("결과 데이터", expanded=False):
                    if isinstance(s["data"], dict):
                        st.json(s["data"])
                    else:
                        st.text(str(s["data"])[:500])
            elif s["type"] == "response" and s["content"] != item.get("final_answer"):
                st.info(s["content"])

        # 목표 원문
        with st.expander("전달된 목표 원문"):
            st.code(item["goal"], language="text")


# ══════════════════════════════════════════════════════════════
# [서브탭 2] 수신자 관리
# ══════════════════════════════════════════════════════════════
def _render_recipient_manager():
    st.markdown("##### 수신자 등록 · 관리")
    st.caption(f"설정 파일: `{NOTIFY_CONFIG_PATH}`")

    cfg        = load_config()
    recipients = cfg.get("recipients", [])

    if recipients:
        st.markdown("**등록된 수신자**")
        for i, r in enumerate(recipients):
            active = r.get("active", True)
            badge  = "🟢" if active else "⚫"
            with st.expander(
                f"{badge} **{r.get('name','')}** {r.get('role','')} — "
                f"{r.get('email','')}",
                expanded=False
            ):
                c1, c2 = st.columns(2)
                with c1:
                    nn = st.text_input("이름",   value=r.get("name",""),  key=f"rn_{i}")
                    nr = st.text_input("직책",   value=r.get("role",""),  key=f"rr_{i}")
                    ne = st.text_input("이메일", value=r.get("email",""), key=f"re_{i}")
                with c2:
                    ns = st.text_input("슬랙",   value=r.get("slack",""), key=f"rs_{i}")
                    np_ = st.text_input("전화",  value=r.get("phone",""), key=f"rp_{i}")
                    na = st.toggle("활성",       value=active,            key=f"ra_{i}")

                ng = st.multiselect(
                    "알림 등급",
                    ["Critical","High","Medium","Low"],
                    default=r.get("notify_grades",["Critical","High"]),
                    key=f"rg_{i}"
                )
                cs, cd = st.columns([3,1])
                if cs.button("💾 저장", key=f"rsv_{i}", use_container_width=True):
                    cfg["recipients"][i] = {
                        **r,
                        "name":nn,"role":nr,"email":ne,
                        "slack":ns,"phone":np_,"active":na,
                        "notify_grades":ng,
                        "updated_at":datetime.now().strftime("%Y-%m-%d %H:%M")
                    }
                    save_config(cfg)
                    st.success("저장 완료")
                    st.rerun()
                if cd.button("🗑", key=f"rdl_{i}", use_container_width=True):
                    del cfg["recipients"][i]
                    save_config(cfg)
                    st.rerun()
    else:
        st.info("등록된 수신자가 없습니다.")

    st.divider()
    st.markdown("**신규 수신자 추가**")

    with st.form("add_rcpt", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            fn = st.text_input("이름 *",   placeholder="홍길동")
            fr = st.text_input("직책",     placeholder="안전팀장")
            fe = st.text_input("이메일 *", placeholder="safety@railway.kr")
        with c2:
            fs = st.text_input("슬랙",     placeholder="#safety-alert")
            fp = st.text_input("전화",     placeholder="010-1234-5678")
            fa = st.toggle("즉시 활성화",  value=True)
        fg = st.multiselect("알림 등급 *", ["Critical","High","Medium","Low"],
                            default=["Critical","High"])
        if st.form_submit_button("➕ 등록", use_container_width=True, type="primary"):
            if not fn.strip() or not fe.strip():
                st.error("이름·이메일 필수")
            elif not fg:
                st.error("알림 등급 1개 이상 선택")
            else:
                cfg["recipients"].append({
                    "id":len(cfg["recipients"])+1,
                    "name":fn.strip(),"role":fr.strip(),
                    "email":fe.strip(),"slack":fs.strip(),"phone":fp.strip(),
                    "active":fa,"notify_grades":fg,
                    "created_at":datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "updated_at":datetime.now().strftime("%Y-%m-%d %H:%M"),
                })
                save_config(cfg)
                st.success(f"'{fn}' 등록 완료")
                st.rerun()

    st.divider()
    st.markdown("**등급별 알림 채널 규칙**")
    rules = cfg.get("rules", DEFAULT_CONFIG["rules"])
    for grade, color in [("Critical","🔴"),("High","🟠"),("Medium","🟡"),("Low","🟢")]:
        st.multiselect(f"{color} {grade}", ["email","slack","sms","log"],
                       default=rules.get(grade,["log"]), key=f"rule_{grade}")

    if st.button("💾 채널 규칙 저장", use_container_width=True):
        for grade in ["Critical","High","Medium","Low"]:
            rules[grade] = st.session_state.get(f"rule_{grade}", rules.get(grade,["log"]))
        cfg["rules"] = rules
        save_config(cfg)
        st.success("저장 완료")

    st.divider()
    cl, cr = st.columns(2)
    cl.download_button("⬇ 설정 내보내기",
        data=json.dumps(cfg, ensure_ascii=False, indent=2),
        file_name="notify_config.json", mime="application/json",
        use_container_width=True)
    up = cr.file_uploader("⬆ 설정 가져오기", type=["json"], key="cfg_up")
    if up:
        try:
            imported = json.load(up)
            if "recipients" in imported:
                save_config(imported)
                st.success("가져오기 완료")
                st.rerun()
        except Exception as e:
            st.error(str(e))


# ══════════════════════════════════════════════════════════════
# [서브탭 3] 알림 발송 이력
# ══════════════════════════════════════════════════════════════
def _render_notify_log():
    st.markdown("##### 알림 발송 이력")
    cfg  = load_config()
    logs = cfg.get("notify_log", [])

    if not logs:
        st.info("발송된 알림이 없습니다.")
        return

    ch, cc = st.columns([4,1])
    ch.caption(f"총 {len(logs)}건")
    if cc.button("전체 삭제"):
        cfg["notify_log"] = []
        save_config(cfg)
        st.rerun()

    import pandas as pd
    df = pd.DataFrame(logs)
    show = [c for c in ["timestamp","channel","goal","message"] if c in df.columns]
    st.dataframe(
        df[show].rename(columns={"timestamp":"발송시각","channel":"채널",
                                  "goal":"목표","message":"내용"}),
        use_container_width=True, height=380
    )
    st.download_button("⬇ CSV 다운로드",
        data=df[show].to_csv(index=False, encoding="utf-8-sig"),
        file_name=f"notify_log_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv")


# ══════════════════════════════════════════════════════════════
# 단독 실행
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    st.set_page_config(page_title="AI 에이전트", layout="wide", page_icon="🤖")
    st.title("🤖 철도안전 AI 에이전트")
    render_agent_tab()
