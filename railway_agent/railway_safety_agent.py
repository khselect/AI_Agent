"""
railway_safety_agent.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
철도안전 AI 에이전트 (LangGraph 기반)
safety_analytics.py 의 파이프라인을 Tool로 래핑하고
LangGraph StateGraph 로 자율 루프를 구성합니다.

아키텍처:
  사용자 목표 → Supervisor LLM
                 ↓ tool_call
  ┌─────────────────────────────┐
  │  Tool Registry              │
  │  ① extract_pdf_tool         │ ← extract_from_pdf() 래핑
  │  ② save_db_tool             │ ← insert_accident() 래핑
  │  ③ query_db_tool            │ ← get_all_accidents() 래핑
  │  ④ assess_risk_tool         │ ← calculate_risk() 래핑
  │  ⑤ scenario_tool            │ ← generate_scenarios() 래핑
  │  ⑥ web_collect_tool         │ ← 신규: 보고서 URL 수집
  │  ⑦ notify_tool              │ ← 신규: 알림 발송
  └─────────────────────────────┘
                 ↓ observation
  Supervisor → 목표 달성 판단 → 완료 or 재계획

실행:
    python railway_safety_agent.py

필수 패키지:
    pip install langgraph langchain langchain-ollama
    pip install duckdb pymupdf4llm streamlit pandas
"""

import os, json, re
from typing import TypedDict, Annotated, Sequence
from datetime import datetime

# ── LangGraph ────────────────────────────────────────────────
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

# ── LangChain ────────────────────────────────────────────────
from langchain_core.tools import tool
from langchain_core.messages import (
    BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
)

# ── ChatOllama: langchain_ollama 패키지 사용 (bind_tools 지원) ──
# langchain_community 의 ChatOllama 는 bind_tools 미지원 (deprecated)
try:
    from langchain_ollama import ChatOllama
except ImportError:
    raise ImportError(
        "langchain_ollama 패키지가 필요합니다.\n"
        "  pip install -U langchain-ollama"
    )

# ── 기존 safety_analytics 함수 임포트 ────────────────────────
# (safety_analytics.py 와 같은 디렉터리에서 실행 시)
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

try:
    # safety_analytics.py 에서 핵심 함수만 직접 임포트
    # Streamlit 의존성을 피하기 위해 core 모듈로 분리된 경우를 우선 시도
    from safety_core import (
        extract_from_pdf, insert_accident, get_all_accidents,
        calculate_risk, generate_scenarios, get_accident_count
    )
    CORE_AVAILABLE = True
except ImportError:
    # safety_core 미분리 시 — 아래 내장 구현을 사용
    CORE_AVAILABLE = False
    print("[경고] safety_core 미발견 → 내장 구현으로 동작합니다.")
    print("       safety_core.py 분리를 권장합니다. (가이드 참조)")


# ══════════════════════════════════════════════════════════════
# STEP 1. 에이전트 State 정의
# ══════════════════════════════════════════════════════════════
class AgentState(TypedDict):
    """
    그래프 전체에서 공유되는 상태 객체.
    messages : 대화 히스토리 (LLM 이 이를 통해 컨텍스트 유지)
    goal     : 현재 에이전트가 수행 중인 목표 문자열
    results  : 각 Tool 실행 결과 누적 dict
    iteration: 반복 횟수 (무한루프 방지)
    """
    messages : Annotated[Sequence[BaseMessage], lambda a, b: list(a) + list(b)]
    goal     : str
    results  : dict
    iteration: int


# ══════════════════════════════════════════════════════════════
# STEP 2. Tool 정의 (기존 함수 래핑)
# ══════════════════════════════════════════════════════════════

@tool
def extract_pdf_tool(pdf_path: str, model_name: str = "qwen2.5:3b") -> str:
    """
    [Tool ①] PDF 사고조사보고서에서 43개 표준 필드를 자동 추출합니다.
    
    Args:
        pdf_path  : 로컬 PDF 파일 경로 (절대경로 권장)
        model_name: Ollama 모델명 (기본: qwen2.5:3b)
    
    Returns:
        JSON 문자열 — 추출된 43개 필드
    """
    if not os.path.exists(pdf_path):
        return json.dumps({"error": f"파일 없음: {pdf_path}"}, ensure_ascii=False)
    
    if CORE_AVAILABLE:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        extracted, _ = extract_from_pdf(pdf_bytes, model_name)
        return json.dumps(extracted, ensure_ascii=False, default=str)
    else:
        # Fallback: 정규식 기반 간이 추출
        try:
            import pymupdf4llm
            md_text = pymupdf4llm.to_markdown(pdf_path)
            result = _fallback_regex_extract(md_text)
            result["데이터출처"] = os.path.basename(pdf_path)
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
def save_db_tool(extracted_json: str, source_file: str = "") -> str:
    """
    [Tool ②] 추출된 사고 데이터를 DuckDB에 저장하고 위험도를 산정합니다.
    
    Args:
        extracted_json: extract_pdf_tool 의 출력 JSON 문자열
        source_file   : 원본 파일명 (메타데이터용)
    
    Returns:
        저장 결과 — row_id, risk_score, risk_grade 포함
    """
    try:
        extracted = json.loads(extracted_json)
        if "error" in extracted:
            return json.dumps({"error": "추출 데이터에 오류가 있어 저장을 건너뜁니다."})
        
        if CORE_AVAILABLE:
            row_id = insert_accident(extracted, source_file)
            score, grade = calculate_risk(extracted)
            return json.dumps({
                "status"    : "저장 완료",
                "row_id"    : row_id,
                "risk_score": score,
                "risk_grade": grade,
                "노선"      : extracted.get("노선", "미상"),
                "이벤트"    : extracted.get("이벤트소분류", "미상"),
                "발생일자"  : extracted.get("발생일자", "미상"),
            }, ensure_ascii=False)
        else:
            return json.dumps({"status": "저장 건너뜀 (core 모듈 미연결)", "data": extracted})
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
def query_db_tool(
    risk_grade  : str = "",
    date_from   : str = "",
    date_to     : str = "",
    line        : str = "",
    top_n       : int = 10,
    last_years : int = 0   # ← 추가: 0이면 무시, 5면 최근 5년 자동 계산
) -> str:
    """
    [Tool ③] 사고 DB를 조회합니다. 조건을 조합하여 필터링할 수 있습니다.
    
    Args:
        risk_grade : 위험등급 필터 (Critical/High/Medium/Low)
        date_from  : 시작일 (YYYY-MM-DD)
        date_to    : 종료일 (YYYY-MM-DD)
        line       : 노선명 필터 (예: 경부선)
        top_n      : 반환할 최대 건수 (기본 10)
    
    Returns:
        조건에 맞는 사고 목록 JSON
    """
    try:
        if CORE_AVAILABLE:
            import pandas as pd
            df = get_all_accidents()
        else:
            # DuckDB 직접 연결
            import duckdb, pandas as pd
            db_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "..", "shared", "railway_accidents.duckdb"
            )
            conn = duckdb.connect(db_path, read_only=True)
            df = conn.execute("SELECT * FROM accidents").df()
            conn.close()

        if df.empty:
            return json.dumps({"count": 0, "records": [], "message": "데이터 없음"})

        # 필터 적용
        if risk_grade and "risk_grade" in df.columns:
            df = df[df["risk_grade"] == risk_grade]
        if date_from and "발생일자" in df.columns:
            df = df[df["발생일자"] >= date_from]
        if date_to and "발생일자" in df.columns:
            df = df[df["발생일자"] <= date_to]
        if line and "노선" in df.columns:
            df = df[df["노선"].str.contains(line, na=False)]
        if last_years > 0:
            from datetime import date, timedelta
            date_to   = date.today().strftime("%Y-%m-%d")
            date_from = (date.today() - timedelta(days=365 * last_years)).strftime("%Y-%m-%d")
        df = df.head(top_n)
        summary_cols = ["id","발생일자","노선","이벤트소분류","사망자수","부상자수","risk_score","risk_grade"]
        available = [c for c in summary_cols if c in df.columns]
        records = df[available].fillna("").to_dict(orient="records")

        return json.dumps({
            "count"  : len(records),
            "records": records
        }, ensure_ascii=False, default=str)

    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
def assess_risk_tool(extracted_json: str) -> str:
    """
    [Tool ④] 사고 데이터의 위험도를 즉시 산정합니다 (DB 저장 없음).
    
    Args:
        extracted_json: 사고 데이터 JSON (extract_pdf_tool 출력 또는 직접 작성)
    
    Returns:
        위험점수(0~100), 등급, Hard Constraint 적용 여부
    """
    try:
        data = json.loads(extracted_json)
        dead = int(data.get("사망자수", 0) or 0)
        injured = int(data.get("부상자수", 0) or 0)

        if CORE_AVAILABLE:
            score, grade = calculate_risk(data)
        else:
            # 내장 간이 계산
            efi = dead + injured / 100.0
            score = min(efi * 20, 40)
            score += min(float(data.get("피해액(백만원)", 0) or 0) / 50, 20)
            if dead >= 5: score = max(score, 90)
            elif dead >= 3 or injured >= 20: score = max(score, 80)
            elif dead >= 1: score = max(score, 60)
            score = min(round(score, 1), 100)
            grade = "High" if score >= 60 else ("Medium" if score >= 25 else "Low")

        hard_applied = dead >= 1
        constraint_reason = ""
        if dead >= 5: constraint_reason = f"사망자 {dead}명 → Critical 강제"
        elif dead >= 3 or injured >= 20: constraint_reason = f"중대피해 → Critical 권고"
        elif dead >= 1: constraint_reason = f"사망자 {dead}명 → High 이상 강제"

        return json.dumps({
            "risk_score"      : score,
            "risk_grade"      : grade,
            "hard_constraint" : hard_applied,
            "constraint_reason": constraint_reason,
            "efi"             : dead + injured / 100.0,
            "사망자수"         : dead,
            "부상자수"         : injured,
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
def scenario_tool(
    event_type : str,
    cause_group: str,
    line       : str = "",
    weather    : str = "맑음"
) -> str:
    """
    [Tool ⑤] Bow-Tie 시나리오를 자동 생성합니다.
    
    Args:
        event_type : 이벤트소분류 (예: 탈선, 충돌, 화재)
        cause_group: 근본원인그룹 (예: 인적요인, 기술적요인, 환경적요인)
        line       : 노선명 (선택)
        weather    : 기상상태 (선택)
    
    Returns:
        시나리오 목록 JSON (번호, 설명, 심각도, 대응방안)
    """
    if CORE_AVAILABLE:
        scenarios = generate_scenarios(event_type, cause_group, line, weather)
        return json.dumps(scenarios, ensure_ascii=False)
    else:
        # 내장 템플릿
        templates = {
            ("탈선", "인적요인") : "과속 운행 → 곡선 구간 탈선 → 선로 이탈",
            ("탈선", "기술적요인"): "궤도 변형 미점검 → 고속 통과 중 탈선",
            ("충돌", "인적요인") : "신호 무시 → 선행 열차 추돌 → 연쇄 사고",
            ("화재", "기술적요인"): "전장품 과부하 → 발화 → 객실 확산",
        }
        key = (event_type, cause_group)
        desc = templates.get(key, f"{event_type} 발생 → 현장 대응 지연 → 2차 피해")
        if line: desc = f"[{line}] " + desc
        scenarios = [{"no": 1, "scenario": desc, "severity": "High",
                      "mitigation": "정기 안전 점검 강화, 위험 요소 모니터링"}]
        return json.dumps(scenarios, ensure_ascii=False)


@tool
def web_collect_tool(url: str, keyword: str = "사고") -> str:
    """
    [Tool ⑥] 지정 URL에서 철도 사고 관련 텍스트를 수집합니다.
    공공데이터포털, KISIS, 보도자료 페이지 등에 활용합니다.
    
    Args:
        url    : 수집할 페이지 URL
        keyword: 필터링 키워드 (기본: 사고)
    
    Returns:
        수집된 텍스트 요약 (최대 2000자)
    """
    try:
        import urllib.request
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 RailwaySafetyAgent/1.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")

        # 간이 HTML 태그 제거
        text = re.sub(r"<[^>]+>", " ", raw)
        text = re.sub(r"\s+", " ", text).strip()

        # 키워드 주변 컨텍스트 추출
        idx = text.find(keyword)
        if idx >= 0:
            snippet = text[max(0, idx-200): idx+800]
        else:
            snippet = text[:2000]

        return json.dumps({
            "url"    : url,
            "keyword": keyword,
            "content": snippet[:2000],
            "length" : len(text)
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": str(e), "url": url}, ensure_ascii=False)


@tool
def notify_tool(
    message    : str,
    risk_grade : str = "",
    channel    : str = "",
    recipient  : str = ""
) -> str:
    """
    [Tool ⑦] 등록된 수신자에게 알림을 발송합니다.
    수신자는 shared/notify_config.json 에서 자동 조회됩니다.
    에이전트 UI '수신자 관리' 탭에서 수신자를 등록할 수 있습니다.

    Args:
        message   : 알림 내용 (필수)
        risk_grade: 위험등급 — Critical/High/Medium/Low
                    입력 시 해당 등급 구독 수신자에게 자동 발송
        channel   : 채널 직접 지정 (email/slack/sms/log).
                    비워두면 등급별 규칙에서 자동 결정
        recipient : 수신자 직접 지정 (이름 또는 이메일).
                    비워두면 등록 수신자 전체 대상

    Returns:
        발송 결과 JSON — 수신자별 채널·상태 포함
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    urgency   = "🚨 긴급" if risk_grade in ("Critical", "High") else "ℹ️ 알림"

    # ── notify_config.json 로드 ───────────────────────────────
    _base       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(_base, "shared", "notify_config.json")
    config      = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            pass

    all_recipients = config.get("recipients", [])
    rules          = config.get("rules", {
        "Critical": ["email","slack"], "High": ["email","slack"],
        "Medium": ["email"], "Low": ["log"]
    })

    # ── 수신 대상 결정 ────────────────────────────────────────
    if recipient:
        # 직접 지정: 이름 또는 이메일로 매칭
        targets = [
            r for r in all_recipients
            if r.get("active", True) and (
                recipient in r.get("name","") or
                recipient in r.get("email","") or
                recipient in r.get("slack","")
            )
        ]
        if not targets:
            # 매칭 없으면 raw 문자열 그대로 사용
            targets = [{"name": recipient, "email": recipient, "slack": "", "phone": ""}]
    elif risk_grade:
        # 등급 기반: 해당 등급을 구독하는 활성 수신자
        targets = [
            r for r in all_recipients
            if r.get("active", True) and risk_grade in r.get("notify_grades", [])
        ]
    else:
        # 기본: 모든 활성 수신자
        targets = [r for r in all_recipients if r.get("active", True)]

    # 수신자 없으면 로그만
    if not targets:
        targets = [{"name": "시스템 로그", "email": "", "slack": "", "phone": ""}]

    # ── 채널 결정 ─────────────────────────────────────────────
    use_channels = [channel] if channel else rules.get(risk_grade, ["log"])

    # ── 발송 실행 ─────────────────────────────────────────────
    sent_results = []
    for r in targets:
        for ch in use_channels:
            addr = {
                "email": r.get("email",""),
                "slack": r.get("slack",""),
                "sms"  : r.get("phone",""),
                "log"  : "console",
            }.get(ch, "")

            body = f"[{timestamp}] {urgency} | {message} → {r.get('name','')} ({addr})"
            print(f"[NOTIFY/{ch.upper()}] {body}")

            # ── 실운영 확장 포인트 ──────────────────────────
            # if ch == "email" and addr:
            #     import smtplib
            #     from email.mime.text import MIMEText
            #     msg = MIMEText(body)
            #     msg["Subject"] = f"[철도안전] {urgency} 알림"
            #     msg["To"] = addr
            #     with smtplib.SMTP("smtp.yourserver.com", 587) as s:
            #         s.sendmail("noreply@railway.kr", addr, msg.as_string())
            #
            # elif ch == "slack" and addr:
            #     import requests
            #     requests.post(SLACK_WEBHOOK, json={"text": body, "channel": addr})
            #
            # elif ch == "sms" and addr:
            #     # KT/SKT API 연동
            #     send_sms(addr, body)
            # ───────────────────────────────────────────────

            sent_results.append({
                "recipient": r.get("name",""),
                "channel"  : ch,
                "address"  : addr,
                "status"   : "발송 완료" if addr else "주소 없음 (로그만)",
            })

    # ── 이력 저장 ─────────────────────────────────────────────
    try:
        notify_log = config.get("notify_log", [])
        notify_log.insert(0, {
            "timestamp": timestamp,
            "goal"     : "",
            "channel"  : ",".join(use_channels),
            "message"  : message[:200],
        })
        config["notify_log"] = notify_log[:100]
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return json.dumps({
        "status"      : "발송 완료",
        "risk_grade"  : risk_grade,
        "sent_count"  : len(sent_results),
        "sent_results": sent_results,
        "timestamp"   : timestamp,
    }, ensure_ascii=False)


# ══════════════════════════════════════════════════════════════
# STEP 3. LangGraph 그래프 구성
# ══════════════════════════════════════════════════════════════

# 등록할 Tool 목록
TOOLS = [
    extract_pdf_tool,
    save_db_tool,
    query_db_tool,
    assess_risk_tool,
    scenario_tool,
    web_collect_tool,
    notify_tool,
]

def build_agent(model_name: str = "qwen2.5:3b"):
    """
    LangGraph StateGraph 기반 에이전트를 생성합니다.
    
    그래프 구조:
      [START] → supervisor → tool_node → supervisor → ... → [END]
                     ↑___________________________|
                          (재계획 루프)
    """

    # ── LLM 설정 (langchain_ollama.ChatOllama — bind_tools 완전 지원) ──
    llm = ChatOllama(
        model=model_name,
        base_url="http://127.0.0.1:11434",
        temperature=0,
        num_ctx=16384,
    )
    llm_with_tools = llm.bind_tools(TOOLS)  # NotImplementedError 없음

    # ── System Prompt ──────────────────────────────────────────
    SYSTEM_PROMPT = """당신은 철도안전 AI 에이전트입니다.
주어진 목표를 달성하기 위해 사용 가능한 도구를 자율적으로 선택하고 실행합니다.

사용 가능한 도구:
- extract_pdf_tool : PDF 보고서에서 43개 필드 자동 추출
- save_db_tool     : 추출 데이터를 DB에 저장 + 위험도 산정
- query_db_tool    : DB 사고 데이터 조회 및 필터링
- assess_risk_tool : 위험도 즉시 산정 (DB 저장 없음)
- scenario_tool    : Bow-Tie 시나리오 자동 생성
- web_collect_tool : 외부 URL에서 사고 데이터 수집
- notify_tool      : 조사관/담당자 알림 발송

업무 규칙:
1. 사망자가 발생한 사고는 반드시 High 이상으로 분류
2. 위험도가 High/Critical인 경우 notify_tool 로 담당자에게 즉시 알림
3. 도구 실행 결과에 error 가 있으면 다른 방법을 시도
4. 목표가 달성되면 "완료:" 로 시작하는 응답을 반환
"""

    def supervisor_node(state: AgentState) -> AgentState:
        """
        핵심 노드: LLM이 상태를 보고 다음 행동을 결정합니다.
        - Tool을 호출할지
        - 완료로 판단할지
        - 오류 시 재시도할지
        """
        # 반복 횟수 제한 (무한루프 방지)
        if state["iteration"] >= 15:
            return {
                "messages": [AIMessage(content="최대 반복 횟수 초과. 에이전트 종료.")],
                "iteration": state["iteration"] + 1,
                "results": state["results"],
                "goal": state["goal"]
            }

        messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(state["messages"])
        response = llm_with_tools.invoke(messages)

        return {
            "messages": [response],
            "iteration": state["iteration"] + 1,
            "results": state["results"],
            "goal": state["goal"]
        }

    def should_continue(state: AgentState) -> str:
        """
        분기 조건: 다음 노드를 결정합니다.
        - Tool call이 있으면 → tool_node
        - "완료:" 응답이면 → END
        - 반복 초과 → END
        """
        last = state["messages"][-1]

        # AIMessage 에 tool_calls 가 있으면 도구 실행
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tool_node"

        # 완료 또는 반복 초과
        if state["iteration"] >= 15:
            return END

        content = getattr(last, "content", "")
        if isinstance(content, str) and content.startswith("완료:"):
            return END

        return END  # 도구 호출 없이 텍스트 응답 → 완료

    # ── 그래프 조립 ────────────────────────────────────────────
    tool_node = ToolNode(TOOLS)

    graph = StateGraph(AgentState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("tool_node", tool_node)

    graph.set_entry_point("supervisor")
    graph.add_conditional_edges(
        "supervisor",
        should_continue,
        {"tool_node": "tool_node", END: END}
    )
    # Tool 실행 후 항상 supervisor 로 복귀 (재계획)
    graph.add_edge("tool_node", "supervisor")

    return graph.compile()


# ══════════════════════════════════════════════════════════════
# STEP 4. 에이전트 실행 헬퍼
# ══════════════════════════════════════════════════════════════

def run_agent(goal: str, model_name: str = "qwen2.5:3b") -> str:
    """
    에이전트에 목표를 부여하고 실행합니다.
    
    Args:
        goal      : 자연어 목표 (예: "이번 주 High 이상 사고 조회 후 담당자 알림")
        model_name: Ollama 모델명
    
    Returns:
        최종 응답 문자열
    """
    agent = build_agent(model_name)

    init_state: AgentState = {
        "messages" : [HumanMessage(content=goal)],
        "goal"     : goal,
        "results"  : {},
        "iteration": 0,
    }

    print(f"\n{'='*60}")
    print(f"[에이전트 시작] 목표: {goal}")
    print(f"{'='*60}")

    final_state = agent.invoke(init_state)

    # 최종 메시지 추출
    for msg in reversed(final_state["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            print(f"\n[에이전트 완료] {msg.content}")
            return msg.content

    return "에이전트 실행 완료 (응답 없음)"


# ── 폴백 정규식 추출 (safety_core 미연결 시) ──────────────────
def _fallback_regex_extract(text: str) -> dict:
    d = {}
    dm = re.search(r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', text)
    if dm: d['발생일자'] = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
    dead = re.search(r'사망자?\s*(\d+)\s*명', text)
    d['사망자수'] = int(dead.group(1)) if dead else 0
    inj = re.search(r'부상자?\s*(\d+)\s*명', text)
    d['부상자수'] = int(inj.group(1)) if inj else 0
    return d


# ══════════════════════════════════════════════════════════════
# STEP 5. CLI 진입점 & 시나리오 예제
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="철도안전 AI 에이전트")
    parser.add_argument("--goal", type=str, default="", help="목표 문자열")
    parser.add_argument("--model", type=str, default="qwen2.5:3b", help="Ollama 모델명")
    parser.add_argument("--demo", type=str, default="",
                        help="데모 시나리오 선택: query_high / assess / scenario / pdf")
    args = parser.parse_args()

    # ── 데모 시나리오 ──────────────────────────────────────────
    DEMO_GOALS = {
        "query_high": (
            "DB에서 위험등급 High 이상 사고를 최대 5건 조회하고, "
            "각 사고의 노선·이벤트·사망자수를 요약한 후 "
            "log 채널로 안전팀에 알림을 발송해줘."
        ),
        "assess": (
            '다음 사고 데이터의 위험도를 산정해줘: '
            '{"사망자수": 2, "부상자수": 15, "이벤트소분류": "탈선", '
            '"최대지연시간(분)": 180, "피해액(백만원)": 500}'
        ),
        "scenario": (
            "경부선에서 기술적 요인에 의한 탈선 사고가 발생했을 때의 "
            "Bow-Tie 시나리오를 생성하고 주요 대응방안을 정리해줘."
        ),
        "pdf": (
            "shared/sample_report.pdf 파일을 추출하고 DB에 저장한 후, "
            "위험도가 High 이상이면 safety_team@railway.kr 에 이메일 알림을 보내줘."
        ),
    }

    if args.demo and args.demo in DEMO_GOALS:
        goal = DEMO_GOALS[args.demo]
    elif args.goal:
        goal = args.goal
    else:
        # 대화형 모드
        print("철도안전 AI 에이전트 대화형 모드")
        print("종료: 'exit' 입력\n")
        while True:
            goal = input("목표 입력> ").strip()
            if goal.lower() == "exit":
                break
            if goal:
                run_agent(goal, args.model)
        exit()

    run_agent(goal, args.model)
