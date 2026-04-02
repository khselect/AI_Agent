"""
ui/tab_dashboard.py — 탭3: 사고 데이터 대시보드 (전문화 개선판)
"""
from __future__ import annotations

import warnings
from datetime import datetime

import numpy as np
import pandas as pd
import altair as alt
import streamlit as st

from safety_core import get_all_accidents

# ──────────────────────────────────────────────
# 43개 컬럼 그룹 정의
# ──────────────────────────────────────────────
FIELD_GROUPS: dict[str, dict] = {
    "기본정보": {
        "icon": "📋",
        "color": "#2980B9",
        "fields": [
            "발생일자", "발생시간", "등록기관", "철도구분", "노선",
            "이벤트대분류", "이벤트중분류", "이벤트소분류", "주원인",
        ],
    },
    "원인분석": {
        "icon": "🔍",
        "color": "#8E44AD",
        "fields": [
            "근본원인그룹", "근본원인유형", "근본원인상세", "직접원인",
            "운행영향유형", "지연여부", "지연원인", "지연원인상세", "지연열차수",
        ],
    },
    "피해현황": {
        "icon": "💥",
        "color": "#C0392B",
        "fields": [
            "최대지연시간(분)", "총피해인원", "사망자수", "부상자수",
            "피해액(백만원)", "행정구역", "발생역A", "발생역B",
        ],
    },
    "위치/환경": {
        "icon": "🌍",
        "color": "#27AE60",
        "fields": [
            "장소대분류", "장소중분류", "상세위치", "기상상태",
            "온도", "강우량", "적설량", "대상구분",
        ],
    },
    "기술/결과": {
        "icon": "⚙️",
        "color": "#E67E22",
        "fields": [
            "열차종류", "선로유형", "신호시스템유형", "고장부품명",
            "고장현상", "고장원인", "조치내용", "이벤트개요", "데이터출처",
        ],
    },
}

GRADE_COLOR = {
    "Critical": "#C0392B",
    "High":     "#E67E22",
    "Medium":   "#F1C40F",
    "Low":      "#27AE60",
}
GRADE_SCALE = alt.Scale(
    domain=["Critical", "High", "Medium", "Low"],
    range=["#C0392B", "#E67E22", "#F1C40F", "#27AE60"],
)


# ──────────────────────────────────────────────
# 기존 공개 함수 (인터페이스 유지)
# ──────────────────────────────────────────────
def analyze_trends(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    return {
        "total": len(df),
        "high_risk": int(df["risk_grade"].isin(["High", "Critical"]).sum()) if "risk_grade" in df.columns else 0,
        "avg_risk_score": float(df["risk_score"].mean()) if "risk_score" in df.columns else 0,
        "total_deaths": int(df["사망자수"].fillna(0).sum()) if "사망자수" in df.columns else 0,
        "total_injured": int(df["부상자수"].fillna(0).sum()) if "부상자수" in df.columns else 0,
        "total_damage": float(df["피해액(백만원)"].fillna(0).sum()) if "피해액(백만원)" in df.columns else 0,
    }


def run_anomaly_detection(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) < 10:
        return df.assign(anomaly_score=None, is_anomaly=False)
    try:
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import LabelEncoder
        warnings.filterwarnings("ignore")
        nums = ["사망자수", "부상자수", "피해액(백만원)", "최대지연시간(분)", "지연열차수", "risk_score"]
        cats = ["이벤트소분류", "근본원인그룹", "기상상태"]
        work = df.copy()
        for c in nums:
            work[c] = pd.to_numeric(work.get(c, pd.Series([0] * len(work))), errors="coerce").fillna(0)
        for c in cats:
            if c in work.columns:
                le = LabelEncoder()
                work[c + "_enc"] = le.fit_transform(work[c].fillna("unknown"))
        X_cols = nums + [c + "_enc" for c in cats if c in work.columns]
        X = work[[c for c in X_cols if c in work.columns]].values
        model = IsolationForest(contamination=0.1, random_state=42)
        sc = model.fit_predict(X)
        df = df.copy()
        df["anomaly_score"] = np.round(-model.decision_function(X) * 100, 1)
        df["is_anomaly"] = sc == -1
        return df
    except Exception:
        return df.assign(anomaly_score=None, is_anomaly=False)


# ──────────────────────────────────────────────
# 내부 헬퍼 함수
# ──────────────────────────────────────────────
def _inject_dashboard_css() -> None:
    st.markdown(
        """
        <style>
        /* ── KPI 카드 ── */
        .kpi-card {
            background: #FFFFFF;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            padding: 16px 18px 12px 18px;
            border-top: 4px solid #2980B9;
            margin-bottom: 6px;
        }
        .kpi-card.critical { border-top-color: #C0392B; }
        .kpi-card.high     { border-top-color: #E67E22; }
        .kpi-card.medium   { border-top-color: #F1C40F; }
        .kpi-card.low      { border-top-color: #27AE60; }
        .kpi-card.anomaly  { border-top-color: #8E44AD; }
        .kpi-label {
            font-size: 0.78rem;
            color: #7F8C8D;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 4px;
        }
        .kpi-value {
            font-size: 1.65rem;
            font-weight: 800;
            color: #2C3E50;
            line-height: 1.1;
        }
        .kpi-sub {
            font-size: 0.72rem;
            color: #95A5A6;
            margin-top: 2px;
        }
        /* ── 섹션 헤더 ── */
        .section-header {
            border-left: 4px solid #2980B9;
            padding-left: 10px;
            font-size: 1.05rem;
            font-weight: 700;
            color: #2C3E50;
            margin: 8px 0 4px 0;
        }
        /* ── 필드 카드 (상세 뷰) ── */
        .field-card {
            background: #F8F9FA;
            border: 1px solid #E0E0E0;
            border-radius: 6px;
            padding: 8px 12px;
            margin: 3px 0;
            min-height: 54px;
        }
        .field-label {
            display: block;
            font-size: 0.70rem;
            color: #95A5A6;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            margin-bottom: 2px;
        }
        .field-value {
            display: block;
            font-size: 0.90rem;
            font-weight: 700;
            color: #2C3E50;
            word-break: break-all;
        }
        .field-value.empty { color: #BDC3C7; font-weight: 400; }
        /* ── 위험등급 배지 ── */
        .grade-badge {
            display: inline-block;
            border-radius: 12px;
            padding: 2px 10px;
            font-size: 0.78rem;
            font-weight: 700;
            color: #FFFFFF;
        }
        .grade-Critical { background: #C0392B; }
        .grade-High     { background: #E67E22; }
        .grade-Medium   { background: #F1C40F; color: #2C3E50; }
        .grade-Low      { background: #27AE60; }
        /* ── 이벤트개요 박스 ── */
        .overview-box {
            background: #EBF5FB;
            border-left: 4px solid #2980B9;
            border-radius: 0 6px 6px 0;
            padding: 12px 16px;
            font-size: 0.88rem;
            color: #2C3E50;
            line-height: 1.55;
        }
        /* ── 위험점수 미니 카드 ── */
        .risk-mini {
            background: #FDFEFE;
            border: 1px solid #E0E0E0;
            border-radius: 8px;
            padding: 10px 14px;
            text-align: center;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _kpi_card_html(label: str, value: str, sub: str = "", css_cls: str = "") -> str:
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return (
        f'<div class="kpi-card {css_cls}">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f"{sub_html}"
        f"</div>"
    )


def _build_kpi_row(df: pd.DataFrame, trends: dict) -> None:
    total      = trends.get("total", 0)
    high_risk  = trends.get("high_risk", 0)
    avg_score  = trends.get("avg_risk_score", 0)
    deaths     = trends.get("total_deaths", 0)
    injured    = trends.get("total_injured", 0)
    damage     = trends.get("total_damage", 0)
    n_anomaly  = int(df["is_anomaly"].sum()) if "is_anomaly" in df.columns else 0
    high_pct   = f"{high_risk/total*100:.0f}%" if total > 0 else "—"

    cols = st.columns(7)
    cards = [
        (cols[0], "총 사고 건수",       f"{total:,}건",              "",                   ""),
        (cols[1], "위험(H+C) 건수",     f"{high_risk:,}건",          f"전체의 {high_pct}",  "critical"),
        (cols[2], "평균 위험점수",       f"{avg_score:.1f}점",        "100점 만점",          "high"),
        (cols[3], "총 사망자",           f"{deaths:,}명",             "",                   "critical"),
        (cols[4], "총 부상자",           f"{injured:,}명",            "",                   "high"),
        (cols[5], "총 피해액(백만원)",   f"{damage:,.0f}M",           "",                   "medium"),
        (cols[6], "이상탐지 건수",       f"{n_anomaly:,}건",          "Isolation Forest",   "anomaly" if n_anomaly > 0 else ""),
    ]
    for col, label, value, sub, cls in cards:
        col.markdown(_kpi_card_html(label, value, sub, cls), unsafe_allow_html=True)


def _build_anomaly_banner(df: pd.DataFrame) -> None:
    if "is_anomaly" not in df.columns:
        st.caption(f"💡 {len(df)}/50건 — 50건 이상 시 이상탐지 활성화")
        return
    n_anom = int(df["is_anomaly"].sum())
    if n_anom > 0:
        with st.expander(f"⚠️ Isolation Forest: {n_anom}건 이상 패턴 탐지 — 클릭하여 목록 확인", expanded=False):
            anom_cols = [c for c in ["id", "발생일자", "노선", "이벤트소분류", "사망자수", "risk_grade", "risk_score", "anomaly_score"] if c in df.columns]
            st.dataframe(
                df[df["is_anomaly"]][anom_cols].sort_values("anomaly_score", ascending=False),
                use_container_width=True,
                hide_index=True,
                height=220,
            )
    else:
        st.success(f"✅ 이상탐지 완료 — {len(df)}건 중 이상 패턴 없음")


def _build_filter_panel(df_all: pd.DataFrame) -> pd.DataFrame:
    with st.expander("🔍 필터 및 검색", expanded=False):
        r1 = st.columns(4)
        grades_all = ["Critical", "High", "Medium", "Low"]
        sel_grades = r1[0].multiselect(
            "위험 등급", grades_all, default=grades_all, key="dash_grades"
        )
        # 연도 목록
        years = ["전체"]
        if "발생일자" in df_all.columns:
            yr_series = pd.to_datetime(df_all["발생일자"], errors="coerce").dt.year.dropna().astype(int)
            years += sorted(yr_series.unique().tolist(), reverse=True)
        sel_year = r1[1].selectbox("연도", years, key="dash_year")

        lines = ["전체"] + sorted(df_all["노선"].dropna().unique().tolist()) if "노선" in df_all.columns else ["전체"]
        sel_line = r1[2].selectbox("노선", lines, key="dash_line")

        rails = ["전체"] + sorted(df_all["철도구분"].dropna().unique().tolist()) if "철도구분" in df_all.columns else ["전체"]
        sel_rail = r1[3].selectbox("철도구분", rails, key="dash_rail")

        r2 = st.columns([3, 1, 2])
        search_q = r2[0].text_input("🔎 텍스트 검색 (노선/이벤트/원인/역명/개요)", key="dash_search")
        weathers = ["전체"] + sorted(df_all["기상상태"].dropna().unique().tolist()) if "기상상태" in df_all.columns else ["전체"]
        sel_weather = r2[1].selectbox("기상상태", weathers, key="dash_weather")
        date_range = r2[2].date_input("발생 기간", value=(), key="dash_dates")

    df = df_all.copy()
    if sel_grades and "risk_grade" in df.columns:
        df = df[df["risk_grade"].isin(sel_grades)]
    if sel_year != "전체" and "발생일자" in df.columns:
        df = df[pd.to_datetime(df["발생일자"], errors="coerce").dt.year == int(sel_year)]
    if sel_line != "전체" and "노선" in df.columns:
        df = df[df["노선"] == sel_line]
    if sel_rail != "전체" and "철도구분" in df.columns:
        df = df[df["철도구분"] == sel_rail]
    if sel_weather != "전체" and "기상상태" in df.columns:
        df = df[df["기상상태"] == sel_weather]
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2 and "발생일자" in df.columns:
        start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
        dt_col = pd.to_datetime(df["발생일자"], errors="coerce")
        df = df[(dt_col >= start) & (dt_col <= end)]
    if search_q.strip():
        search_cols = [c for c in ["노선", "이벤트소분류", "근본원인그룹", "주원인", "발생역A", "이벤트개요"] if c in df.columns]
        mask = pd.Series(False, index=df.index)
        for c in search_cols:
            mask |= df[c].astype(str).str.contains(search_q.strip(), case=False, na=False)
        df = df[mask]

    st.caption(f"필터 결과: **{len(df):,}건** / 전체 {len(df_all):,}건")
    return df


def _build_risk_overview_charts(df: pd.DataFrame) -> None:
    st.markdown('<div class="section-header">위험 현황 개요</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.caption("위험 등급 분포")
        if "risk_grade" in df.columns and not df.empty:
            gc = df["risk_grade"].value_counts().reset_index()
            gc.columns = ["등급", "건수"]
            chart = (
                alt.Chart(gc)
                .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                .encode(
                    x=alt.X("등급:N", sort=["Critical", "High", "Medium", "Low"], axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("건수:Q"),
                    color=alt.Color("등급:N", scale=GRADE_SCALE, legend=None),
                    tooltip=["등급", "건수"],
                )
                .properties(height=220)
            )
            st.altair_chart(chart, use_container_width=True)

    with c2:
        st.caption("노선별 사고 건수 (Top 10)")
        if "노선" in df.columns and not df.empty:
            top_lines = df["노선"].value_counts().head(10).index.tolist()
            ldf = df[df["노선"].isin(top_lines)].copy()
            # 노선별 지배 등급
            dom_grade = (
                ldf.groupby("노선")["risk_grade"]
                .agg(lambda x: x.value_counts().index[0] if len(x) > 0 else "Low")
                .reset_index()
            )
            lc = ldf["노선"].value_counts().reset_index()
            lc.columns = ["노선", "건수"]
            lc = lc.merge(dom_grade, on="노선", how="left")
            chart = (
                alt.Chart(lc)
                .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
                .encode(
                    x=alt.X("건수:Q"),
                    y=alt.Y("노선:N", sort="-x"),
                    color=alt.Color("risk_grade:N", scale=GRADE_SCALE, legend=None),
                    tooltip=["노선", "건수", "risk_grade"],
                )
                .properties(height=220)
            )
            st.altair_chart(chart, use_container_width=True)

    with c3:
        st.caption("근본원인 분포")
        if "근본원인그룹" in df.columns and not df.empty:
            cc = df.dropna(subset=["근본원인그룹"]).groupby("근본원인그룹").agg(
                건수=("근본원인그룹", "count"),
                평균위험=("risk_score", "mean") if "risk_score" in df.columns else ("근본원인그룹", "count"),
            ).reset_index()
            cc.columns = ["원인", "건수", "평균위험점수"]
            cc["평균위험점수"] = cc["평균위험점수"].round(1)
            chart = (
                alt.Chart(cc)
                .mark_arc(innerRadius=45)
                .encode(
                    theta="건수:Q",
                    color=alt.Color("원인:N", legend=alt.Legend(orient="bottom", labelLimit=150)),
                    tooltip=["원인", "건수", "평균위험점수"],
                )
                .properties(height=220)
            )
            st.altair_chart(chart, use_container_width=True)

    with c4:
        st.caption("이벤트 소분류 Top 10")
        if "이벤트소분류" in df.columns and not df.empty:
            top_ev = df["이벤트소분류"].dropna().value_counts().head(10).index.tolist()
            edf = df[df["이벤트소분류"].isin(top_ev)].copy()
            avg_score = (
                edf.groupby("이벤트소분류")["risk_score"].mean().reset_index()
                if "risk_score" in edf.columns else None
            )
            ec = edf["이벤트소분류"].value_counts().reset_index()
            ec.columns = ["유형", "건수"]
            if avg_score is not None:
                avg_score.columns = ["유형", "평균위험점수"]
                ec = ec.merge(avg_score, on="유형", how="left")
                ec["평균위험점수"] = ec["평균위험점수"].round(1)
                color_enc = alt.Color(
                    "평균위험점수:Q",
                    scale=alt.Scale(scheme="orangered", domain=[0, 100]),
                    legend=None,
                )
                tooltip = ["유형", "건수", "평균위험점수"]
            else:
                color_enc = alt.value("#E67E22")
                tooltip = ["유형", "건수"]
            chart = (
                alt.Chart(ec)
                .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
                .encode(
                    x=alt.X("건수:Q"),
                    y=alt.Y("유형:N", sort="-x"),
                    color=color_enc,
                    tooltip=tooltip,
                )
                .properties(height=220)
            )
            st.altair_chart(chart, use_container_width=True)


def _build_temporal_charts(df: pd.DataFrame) -> None:
    if df.empty or "발생일자" not in df.columns:
        return
    df = df.copy()
    df["_dt"] = pd.to_datetime(df["발생일자"], errors="coerce")
    df = df.dropna(subset=["_dt"])
    if df.empty:
        return

    st.markdown('<div class="section-header">시간대별 패턴 분석</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        st.caption("월별 사고 건수 추이 (등급별)")
        if "risk_grade" in df.columns:
            monthly = df.copy()
            monthly["YM"] = monthly["_dt"].dt.to_period("M").dt.to_timestamp()
            mg = monthly.groupby(["YM", "risk_grade"]).size().reset_index(name="건수")
            chart = (
                alt.Chart(mg)
                .mark_area(opacity=0.85)
                .encode(
                    x=alt.X("YM:T", title="발생월", axis=alt.Axis(format="%y.%m", labelAngle=-30)),
                    y=alt.Y("건수:Q", stack="normalize", title="비율", axis=alt.Axis(format="%")),
                    color=alt.Color("risk_grade:N", scale=GRADE_SCALE, legend=alt.Legend(title="등급")),
                    tooltip=["YM:T", "risk_grade:N", "건수:Q"],
                )
                .properties(height=230)
            )
            st.altair_chart(chart, use_container_width=True)

    with c2:
        st.caption("발생 요일 × 시간대 히트맵")
        tdf = df.copy()
        if "발생시간" in tdf.columns:
            tdf["hour"] = tdf["발생시간"].astype(str).str[:2].replace("na", "00").apply(
                lambda x: int(x) if x.isdigit() else 0
            )
        else:
            tdf["hour"] = 0
        tdf["weekday"] = tdf["_dt"].dt.weekday  # 0=월
        DAY_MAP = {0: "월", 1: "화", 2: "수", 3: "목", 4: "금", 5: "토", 6: "일"}
        tdf["요일"] = tdf["weekday"].map(DAY_MAP)
        tdf["시간대"] = (tdf["hour"] // 3 * 3).astype(str).str.zfill(2) + "시"
        hm = tdf.groupby(["요일", "시간대"]).size().reset_index(name="건수")
        chart = (
            alt.Chart(hm)
            .mark_rect(cornerRadius=2)
            .encode(
                x=alt.X("시간대:O", title="시간대", sort=[f"{h:02d}시" for h in range(0, 24, 3)], axis=alt.Axis(labelAngle=0)),
                y=alt.Y("요일:O", sort=["월", "화", "수", "목", "금", "토", "일"]),
                color=alt.Color("건수:Q", scale=alt.Scale(scheme="orangered"), legend=alt.Legend(title="건수")),
                tooltip=["요일:N", "시간대:O", "건수:Q"],
            )
            .properties(height=230)
        )
        st.altair_chart(chart, use_container_width=True)


def _build_damage_cause_charts(df: pd.DataFrame) -> None:
    if df.empty:
        return
    st.markdown('<div class="section-header">원인 × 피해 교차 분석</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        st.caption("근본원인그룹 × 위험등급 스택 바")
        if "근본원인그룹" in df.columns and "risk_grade" in df.columns:
            cg = df.groupby(["근본원인그룹", "risk_grade"]).size().reset_index(name="건수")
            chart = (
                alt.Chart(cg)
                .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
                .encode(
                    x=alt.X("근본원인그룹:N", axis=alt.Axis(labelAngle=-15)),
                    y=alt.Y("건수:Q", stack="zero"),
                    color=alt.Color("risk_grade:N", scale=GRADE_SCALE, legend=alt.Legend(title="등급")),
                    order=alt.Order("risk_grade:N", sort="ascending"),
                    tooltip=["근본원인그룹:N", "risk_grade:N", "건수:Q"],
                )
                .properties(height=230)
            )
            st.altair_chart(chart, use_container_width=True)

    with c2:
        st.caption("기상상태 × 위험점수 분포")
        if "기상상태" in df.columns and "risk_score" in df.columns:
            wdf = df.dropna(subset=["기상상태", "risk_score"]).copy()
            wdf["risk_score"] = pd.to_numeric(wdf["risk_score"], errors="coerce")
            if not wdf.empty:
                median_df = wdf.groupby("기상상태")["risk_score"].median().reset_index()
                median_df.columns = ["기상상태", "median_score"]
                strip = (
                    alt.Chart(wdf)
                    .mark_circle(size=28, opacity=0.4)
                    .encode(
                        x=alt.X("기상상태:N", axis=alt.Axis(labelAngle=-15)),
                        y=alt.Y("risk_score:Q", scale=alt.Scale(domain=[0, 100]), title="위험점수"),
                        color=alt.Color("risk_grade:N", scale=GRADE_SCALE, legend=None) if "risk_grade" in wdf.columns else alt.value("#E67E22"),
                        tooltip=["기상상태:N", "risk_score:Q", "이벤트소분류:N"] if "이벤트소분류" in wdf.columns else ["기상상태:N", "risk_score:Q"],
                    )
                )
                med_rule = (
                    alt.Chart(median_df)
                    .mark_rule(color="#2C3E50", strokeWidth=2)
                    .encode(
                        x="기상상태:N",
                        y="median_score:Q",
                        tooltip=["기상상태:N", alt.Tooltip("median_score:Q", title="중앙값")],
                    )
                )
                st.altair_chart((strip + med_rule).properties(height=230), use_container_width=True)


def _build_risk_histogram(df: pd.DataFrame) -> None:
    if "risk_score" not in df.columns or df["risk_score"].isna().all():
        return
    st.markdown('<div class="section-header">위험점수 분포</div>', unsafe_allow_html=True)
    hd = df[["risk_score"]].dropna()
    chart = (
        alt.Chart(hd)
        .mark_bar(color="#C0392B", opacity=0.7, cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("risk_score:Q", bin=alt.Bin(maxbins=20), title="위험점수"),
            y=alt.Y("count():Q", title="건수"),
            tooltip=[alt.Tooltip("risk_score:Q", bin=True, title="점수구간"), "count()"],
        )
        .properties(height=160)
    )
    st.altair_chart(chart, use_container_width=True)


def _render_field_card(field: str, value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)) or str(value).strip() in ("", "nan", "None"):
        val_str, val_cls = "—", "empty"
    else:
        val_str, val_cls = str(value), ""
    return (
        f'<div class="field-card">'
        f'<span class="field-label">{field}</span>'
        f'<span class="field-value {val_cls}">{val_str}</span>'
        f'</div>'
    )


def _build_record_detail(row: pd.Series) -> None:
    """43개 필드를 5개 그룹 탭으로 표시."""
    grade = row.get("risk_grade", "Low")
    score = row.get("risk_score", 0)
    grade_color = GRADE_COLOR.get(grade, "#95A5A6")

    # 위험도 요약 배너
    b1, b2, b3 = st.columns([1, 1, 4])
    b1.markdown(
        f'<div class="risk-mini">'
        f'<div style="font-size:0.7rem;color:#7F8C8D;font-weight:600;">위험등급</div>'
        f'<div style="font-size:1.4rem;font-weight:900;color:{grade_color};">{grade}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    b2.markdown(
        f'<div class="risk-mini">'
        f'<div style="font-size:0.7rem;color:#7F8C8D;font-weight:600;">위험점수</div>'
        f'<div style="font-size:1.4rem;font-weight:900;color:{grade_color};">{score:.0f}점</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    b3.markdown(
        f'<div style="padding:6px 0;font-size:0.82rem;color:#555;">'
        f'ID: <b>{row.get("id","—")}</b> &nbsp;|&nbsp; '
        f'발생일시: <b>{row.get("발생일자","—")} {row.get("발생시간","")}</b> &nbsp;|&nbsp; '
        f'노선: <b>{row.get("노선","—")}</b> &nbsp;|&nbsp; '
        f'등록기관: <b>{row.get("등록기관","—")}</b>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    tab_labels = [f"{v['icon']} {k}" for k, v in FIELD_GROUPS.items()]
    tabs = st.tabs(tab_labels)

    for tab, (group_name, group_info) in zip(tabs, FIELD_GROUPS.items()):
        with tab:
            fields = group_info["fields"]
            # 이벤트개요는 전체 너비로 별도 처리
            overview_field = "이벤트개요" if group_name == "기술/결과" else None
            regular_fields = [f for f in fields if f != overview_field]

            # 3열 그리드
            rows_count = (len(regular_fields) + 2) // 3
            for row_i in range(rows_count):
                cols = st.columns(3)
                for col_i in range(3):
                    idx = row_i * 3 + col_i
                    if idx < len(regular_fields):
                        field = regular_fields[idx]
                        cols[col_i].markdown(
                            _render_field_card(field, row.get(field)),
                            unsafe_allow_html=True,
                        )

            if overview_field and overview_field in row.index:
                overview_val = row.get(overview_field)
                if overview_val and str(overview_val).strip() not in ("", "nan", "None"):
                    st.markdown(
                        f'<div class="overview-box">'
                        f'<div style="font-size:0.72rem;color:#2980B9;font-weight:700;margin-bottom:6px;">이벤트개요</div>'
                        f'{overview_val}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )


def _build_record_explorer(df: pd.DataFrame, delete_fn) -> None:
    st.markdown('<div class="section-header">📋 사고 기록 탐색기</div>', unsafe_allow_html=True)

    if df.empty:
        st.info("조회 결과가 없습니다. 필터를 조정하세요.")
        return

    # ── 정렬 ──
    sort_options = {"위험점수 높은순": ("risk_score", False), "발생일 최신순": ("발생일자", False), "발생일 오래된순": ("발생일자", True)}
    sel_sort = st.radio("정렬 기준", list(sort_options.keys()), horizontal=True, key="dash_sort")
    sort_col, sort_asc = sort_options[sel_sort]
    if sort_col in df.columns:
        df = df.sort_values(sort_col, ascending=sort_asc)

    # ── 요약 테이블 ──
    disp_cols = [c for c in [
        "id", "발생일자", "노선", "이벤트소분류", "근본원인그룹",
        "사망자수", "부상자수", "피해액(백만원)", "최대지연시간(분)",
        "risk_score", "risk_grade",
    ] if c in df.columns]
    if "is_anomaly" in df.columns:
        disp_cols.append("is_anomaly")

    col_cfg: dict = {
        "risk_score": st.column_config.ProgressColumn("위험점수", format="%.0f", min_value=0, max_value=100),
        "발생일자": st.column_config.DateColumn("발생일자"),
        "사망자수": st.column_config.NumberColumn("사망자수", format="%d명"),
        "부상자수": st.column_config.NumberColumn("부상자수", format="%d명"),
        "피해액(백만원)": st.column_config.NumberColumn("피해액(백만원)", format="₩%.0fM"),
        "최대지연시간(분)": st.column_config.NumberColumn("최대지연(분)", format="%d분"),
    }
    if "is_anomaly" in df.columns:
        col_cfg["is_anomaly"] = st.column_config.CheckboxColumn("이상탐지")

    # Streamlit 버전 확인 후 selection 지원 여부 결정
    try:
        _ver = tuple(int(x) for x in st.__version__.split(".")[:2])
        _supports_selection = _ver >= (1, 35)
    except Exception:
        _supports_selection = False

    display_df = df[disp_cols].reset_index(drop=True)

    if _supports_selection:
        event = st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            height=340,
            column_config=col_cfg,
            on_select="rerun",
            selection_mode="single-row",
            key="dash_table_sel",
        )
        selected_rows = event.selection.rows if hasattr(event, "selection") else []
    else:
        st.dataframe(display_df, use_container_width=True, hide_index=True, height=340, column_config=col_cfg)
        selected_rows = []

    # ── CSV 내보내기 ──
    csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        "📥 현재 필터 결과 CSV 다운로드",
        csv_bytes,
        file_name=f"대시보드_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        key="dash_csv",
    )

    # ── 43개 필드 상세 뷰 ──
    if _supports_selection and selected_rows:
        row_idx = selected_rows[0]
        selected_id = display_df.iloc[row_idx]["id"] if "id" in display_df.columns else None
        src_row = df[df["id"] == selected_id].iloc[0] if selected_id is not None else df.iloc[row_idx]
        with st.expander("🔎 선택 레코드 상세 정보 (43개 필드)", expanded=True):
            _build_record_detail(src_row)
    else:
        # Fallback: ID로 직접 선택
        with st.expander("🔎 레코드 상세 보기 (ID 입력)", expanded=False):
            if "id" in df.columns:
                id_list = sorted(df["id"].dropna().astype(int).tolist())
                if id_list:
                    sel_id = st.selectbox("레코드 ID 선택", id_list, key="dash_detail_id")
                    detail_row = df[df["id"] == sel_id]
                    if not detail_row.empty:
                        _build_record_detail(detail_row.iloc[0])

    st.divider()
    with st.expander("🗑️ 데이터 삭제"):
        del_id = st.number_input("삭제할 ID", min_value=1, step=1, key="dash_del_id")
        if st.button("삭제", type="primary", key="dash_del_btn"):
            delete_fn(int(del_id))
            st.success(f"ID {del_id} 삭제")
            st.rerun()


# ──────────────────────────────────────────────
# 메인 진입점
# ──────────────────────────────────────────────
def render_dashboard_tab(delete_accident_fn):
    """탭3 대시보드 UI."""
    st.subheader("📊 사고 데이터 대시보드")
    df_all = get_all_accidents()

    if df_all.empty:
        st.info("데이터 없음. Tab 1에서 보고서를 입력하세요.")
        return

    _inject_dashboard_css()
    trends = analyze_trends(df_all)

    if len(df_all) >= 50:
        df_all = run_anomaly_detection(df_all)

    # KPI 행
    _build_kpi_row(df_all, trends)
    st.write("")

    # 이상탐지 배너
    _build_anomaly_banner(df_all)
    st.divider()

    # 필터 패널 → df_filtered
    df_filtered = _build_filter_panel(df_all)
    st.divider()

    # 차트 섹션
    _build_risk_overview_charts(df_filtered)
    st.write("")
    _build_temporal_charts(df_filtered)
    st.write("")
    _build_damage_cause_charts(df_filtered)
    st.write("")
    _build_risk_histogram(df_filtered)
    st.divider()

    # 탐색기 + 상세 뷰 + 삭제
    _build_record_explorer(df_filtered, delete_accident_fn)
