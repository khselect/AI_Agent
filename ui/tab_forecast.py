"""
ui/tab_forecast.py — 탭5: ML 시계열 예측 대시보드
"""
from datetime import datetime

import numpy as np
import pandas as pd
import altair as alt
import streamlit as st

from safety_core import get_all_accidents


def render_forecast_tab():
    """탭5 ML 시계열 예측 대시보드 UI."""
    st.subheader("🔮 사고 발생 예측 대시보드 (ML 시계열 분석)")
    st.caption("사고조사보고서 DB를 학습한 머신러닝 모델로 향후 이벤트 유형별 사고 발생 확률을 예측합니다.")

    df_fc = get_all_accidents()
    n_fc  = len(df_fc)

    if n_fc < 10:
        st.info(f"예측 모델 실행을 위해 최소 10건이 필요합니다. (현재 {n_fc}건)")
        return

    # ── 전처리 ────────────────────────────────────────────
    df_fc = df_fc.copy()
    df_fc["발생일자"] = pd.to_datetime(df_fc["발생일자"], errors="coerce")
    df_fc = df_fc.dropna(subset=["발생일자"])
    df_fc["YM"] = df_fc["발생일자"].dt.to_period("M")

    if len(df_fc) < 10:
        st.info("날짜 파싱 가능한 데이터가 부족합니다.")
        return

    # ── 설정 패널 ─────────────────────────────────────────
    st.markdown("##### ⚙️ 예측 설정")
    cfg1, cfg2, cfg3, cfg4 = st.columns([2, 1.5, 2, 2])
    with cfg1:
        forecast_months = st.slider(
            "예측 기간 (개월)", 3, 24, 12, key="fc_months"
        )
    with cfg2:
        ci_label = st.selectbox(
            "신뢰 구간", ["80%", "90%", "95%"], index=1, key="fc_ci"
        )
    with cfg3:
        model_choice = st.selectbox(
            "예측 모델",
            ["선형 회귀", "2차 다항 회귀", "이동평균 (3M)", "지수평활"],
            key="fc_model",
        )
    with cfg4:
        _all_lines_fc = sorted(df_fc["노선"].dropna().unique().tolist())
        filter_lines = st.multiselect(
            "노선 필터 (비어있으면 전체)",
            _all_lines_fc, default=[], key="fc_lines",
        )

    ci_z = {"80%": 1.28, "90%": 1.645, "95%": 1.96}[ci_label]
    if filter_lines:
        df_fc = df_fc[df_fc["노선"].isin(filter_lines)]

    # 이벤트 유형 선택
    if "이벤트소분류" in df_fc.columns:
        _top_evt_all = df_fc["이벤트소분류"].value_counts().head(8).index.tolist()
    else:
        _top_evt_all = []
    if _top_evt_all:
        if "fc_events" in st.session_state:
            _valid = [e for e in st.session_state["fc_events"] if e in _top_evt_all]
            if not _valid:
                _valid = _top_evt_all[:min(5, len(_top_evt_all))]
            st.session_state["fc_events"] = _valid
        sel_events = st.multiselect(
            "📊 분석 이벤트 유형 선택 (최대 8종)",
            _top_evt_all,
            default=_top_evt_all[:min(5, len(_top_evt_all))],
            key="fc_events",
        )
    else:
        sel_events = []

    st.divider()

    # ── 상수 ──────────────────────────────────────────
    GRADES_FC  = ["Critical", "High", "Medium", "Low"]
    GRADE_CLRS = {
        "Critical": "#C0392B", "High": "#E67E22",
        "Medium":   "#F1C40F", "Low":  "#27AE60",
    }
    MODEL_DESC = {
        "선형 회귀":       "과거의 선형 추세를 외삽합니다. 단순하고 해석이 용이합니다.",
        "2차 다항 회귀":   "가속·감속 곡선 추세를 포착합니다. 선형보다 유연하나 과적합 주의.",
        "이동평균 (3M)":   "최근 3개월 평균을 기준으로 예측합니다. 단기 변동에 강건합니다.",
        "지수평활":        "최근 값에 높은 가중치를 부여합니다. 수준 변화에 빠르게 반응합니다.",
    }

    # ── 월별 집계 ──────────────────────────────────────
    monthly = (
        df_fc.groupby("YM")
        .agg(
            건수         = ("id",        "count"),
            평균위험점수 = ("risk_score", "mean"),
            Critical     = ("risk_grade", lambda x: (x == "Critical").sum()),
            High         = ("risk_grade", lambda x: (x == "High").sum()),
            Medium       = ("risk_grade", lambda x: (x == "Medium").sum()),
            Low          = ("risk_grade", lambda x: (x == "Low").sum()),
        )
        .reset_index()
        .sort_values("YM")
    )
    monthly["YM_str"]       = monthly["YM"].astype(str)
    monthly["평균위험점수"] = monthly["평균위험점수"].fillna(0)

    hist_ym    = monthly["YM_str"].tolist()
    last_ym    = monthly["YM"].iloc[-1]
    future_ym  = pd.period_range(start=last_ym + 1, periods=forecast_months, freq="M")
    future_str = [str(p) for p in future_ym]
    all_ym_domain = hist_ym + future_str

    # ── 예측 모델 함수 ─────────────────────────────────
    def _do_forecast(y: np.ndarray, steps: int, z: float, method: str):
        y = y.astype(float)
        if len(y) == 0:
            z0 = np.zeros(steps)
            return z0, z0.copy(), z0.copy(), 0.0, 0.0

        if method == "선형 회귀":
            try:
                from sklearn.linear_model import LinearRegression
                t  = np.arange(len(y)).reshape(-1, 1)
                lr = LinearRegression().fit(t, y)
                resid = y - lr.predict(t)
                std   = float(np.std(resid))
                t_f   = np.arange(len(y), len(y) + steps).reshape(-1, 1)
                fc    = np.maximum(lr.predict(t_f), 0)
                return (fc, np.maximum(fc - z*std, 0), fc + z*std,
                        float(lr.coef_[0]), float(lr.score(t, y)))
            except Exception:
                pass

        elif method == "2차 다항 회귀":
            try:
                from sklearn.preprocessing import PolynomialFeatures
                from sklearn.linear_model import LinearRegression
                from sklearn.pipeline import make_pipeline
                t  = np.arange(len(y)).reshape(-1, 1)
                md = make_pipeline(PolynomialFeatures(2), LinearRegression())
                md.fit(t, y)
                ph  = md.predict(t)
                std = float(np.std(y - ph))
                t_f = np.arange(len(y), len(y) + steps).reshape(-1, 1)
                fc  = np.maximum(md.predict(t_f), 0)
                ss_res = float(np.sum((y - ph)**2))
                ss_tot = float(np.sum((y - np.mean(y))**2))
                r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
                sl = float(md.predict([[len(y)]]) - md.predict([[len(y)-1]])) if len(y) > 1 else 0.0
                return fc, np.maximum(fc - z*std, 0), fc + z*std, sl, r2
            except Exception:
                pass

        elif method == "이동평균 (3M)":
            w    = min(3, len(y))
            base = float(np.mean(y[-w:]))
            std  = float(np.std(y[-w:])) if w > 1 else 0.0
            fc   = np.full(steps, max(base, 0))
            return fc, np.maximum(fc - z*std, 0), fc + z*std, 0.0, 0.0

        elif method == "지수평활":
            alpha = 0.3
            s     = float(y[0])
            sm    = [s]
            for v in y[1:]:
                s = alpha * float(v) + (1 - alpha) * s
                sm.append(s)
            fc  = np.full(steps, max(s, 0))
            std = float(np.std(y - np.array(sm)))
            return fc, np.maximum(fc - z*std, 0), fc + z*std, 0.0, 0.0

        # 폴백: 평균
        avg = float(np.mean(y))
        std = float(np.std(y)) if len(y) > 1 else 0.0
        fc  = np.full(steps, max(avg, 0))
        return fc, np.maximum(fc - z*std, 0), fc + z*std, 0.0, 0.0

    # ── 전체 발생건수 예측 ─────────────────────────────
    y_cnt   = monthly["건수"].values.astype(float)
    y_score = monthly["평균위험점수"].values.astype(float)
    fc_cnt,   lo_cnt,   hi_cnt,   slope_cnt,   r2_cnt   = _do_forecast(y_cnt,   forecast_months, ci_z, model_choice)
    fc_score, _,        _,        _,           _        = _do_forecast(y_score, forecast_months, ci_z, model_choice)
    fc_score = np.clip(fc_score, 0, 100)

    # ── 등급 비율 예측 ─────────────────────────────────
    grade_fc = {}
    for g in GRADES_FC:
        y_g = (monthly[g] / monthly["건수"].replace(0, 1)).values.astype(float)
        fg, lg, hg, _, _ = _do_forecast(y_g, forecast_months, ci_z, model_choice)
        grade_fc[g] = {
            "fc": np.clip(fg, 0, 1),
            "lo": np.clip(lg, 0, 1),
            "hi": np.clip(hg, 0, 1),
        }
    for i in range(forecast_months):
        tot = sum(grade_fc[g]["fc"][i] for g in GRADES_FC)
        if tot > 0:
            for g in GRADES_FC:
                grade_fc[g]["fc"][i] /= tot

    # ── RF 교차검증 정확도 ─────────────────────────────
    rf_accuracy = None
    if n_fc >= 50:
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.model_selection import cross_val_score
            _feats = ["사망자수", "부상자수", "피해액(백만원)", "최대지연시간(분)"]
            _X = df_fc[_feats].copy()
            for _c in _feats:
                _X[_c] = pd.to_numeric(_X[_c], errors="coerce").fillna(0)
            _y    = df_fc["risk_grade"].fillna("Low")
            _mask = _y.notna() & _X.notna().all(axis=1)
            if _mask.sum() >= 20:
                _clf    = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
                _scores = cross_val_score(
                    _clf, _X[_mask], _y[_mask],
                    cv=min(5, _mask.sum() // 5), scoring="accuracy",
                )
                rf_accuracy = float(_scores.mean())
        except Exception:
            pass

    # ══════════════════════════════════════════════════
    # KPI 카드
    # ══════════════════════════════════════════════════
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.markdown(
        "<div style='font-size:15px;color:#888;text-align:center'>학습 데이터</div>"
        f"<div style='font-size:20px;font-weight:bold;text-align:center;white-space:nowrap'>{n_fc}건</div>",
        unsafe_allow_html=True
    )
    k2.markdown(
        "<div style='font-size:15px;color:#888;text-align:center'>시계열 범위</div>"
        f"<div style='font-size:20px;font-weight:bold;text-align:center;white-space:nowrap'>{hist_ym[0]} ~ {hist_ym[-1]}</div>",
        unsafe_allow_html=True
    )
    k3.markdown(
        "<div style='font-size:15px;color:#888;text-align:center'>월평균 발생건수</div>"
        f"<div style='font-size:20px;font-weight:bold;text-align:center;white-space:nowrap'>{y_cnt.mean():.1f}건</div>",
        unsafe_allow_html=True
    )
    _trend_val = f"{'▲' if slope_cnt > 0 else '▼'} {abs(slope_cnt):.2f}건/월"
    _trend_color = "#e74c3c" if slope_cnt > 0 else "#27ae60"
    k4.markdown(
        "<div style='font-size:15px;color:#888;text-align:center'>발생 추세</div>"
        f"<div style='font-size:20px;font-weight:bold;text-align:center;white-space:nowrap;color:{_trend_color}'>{_trend_val}</div>",
        unsafe_allow_html=True
    )
    _acc_val = f"{rf_accuracy*100:.0f}%" if rf_accuracy else "N/A (50건 미만)"
    k5.markdown(
        "<div style='font-size:15px;color:#888;text-align:center'>RF 분류 정확도</div>"
        f"<div style='font-size:20px;font-weight:bold;text-align:center;white-space:nowrap'>{_acc_val}</div>",
        unsafe_allow_html=True
    )
    st.divider()

    # ══════════════════════════════════════════════════
    # [A] 이벤트 유형별 실제+예측+신뢰구간 통합 차트
    # ══════════════════════════════════════════════════
    st.markdown("#### 📈 이벤트 유형별 발생 추이 및 예측 (신뢰구간 포함)")

    def _mk_x() -> alt.X:
        return alt.X(
            "YM:O", title="연월",
            axis=alt.Axis(labelAngle=-45),
            scale=alt.Scale(domain=all_ym_domain),
        )

    _all_rows: list = []

    # 전체 발생건수
    for j, ym in enumerate(hist_ym):
        _all_rows.append({
            "YM": ym, "유형": "▶ 전체",
            "건수": float(y_cnt[j]),
            "하한": float(y_cnt[j]), "상한": float(y_cnt[j]),
            "구분": "실제",
        })
    for j, ym in enumerate(future_str):
        _all_rows.append({
            "YM": ym, "유형": "▶ 전체",
            "건수": float(fc_cnt[j]),
            "하한": float(lo_cnt[j]), "상한": float(hi_cnt[j]),
            "구분": "예측",
        })

    # 이벤트 유형별
    _evt_slope: dict = {}
    for evt in (sel_events or []):
        _y_e = (
            df_fc[df_fc["이벤트소분류"] == evt]
            .groupby("YM").size()
            .reindex(monthly["YM"], fill_value=0)
            .values.astype(float)
        )
        _fc_e, _lo_e, _hi_e, _sl_e, _ = _do_forecast(
            _y_e, forecast_months, ci_z, model_choice
        )
        _evt_slope[evt] = _sl_e
        for j, ym in enumerate(hist_ym):
            _all_rows.append({
                "YM": ym, "유형": evt,
                "건수": float(_y_e[j]),
                "하한": float(_y_e[j]), "상한": float(_y_e[j]),
                "구분": "실제",
            })
        for j, ym in enumerate(future_str):
            _all_rows.append({
                "YM": ym, "유형": evt,
                "건수": float(_fc_e[j]),
                "하한": float(_lo_e[j]), "상한": float(_hi_e[j]),
                "구분": "예측",
            })

    _combined = pd.DataFrame(_all_rows)
    _pred_df  = _combined[_combined["구분"] == "예측"].copy()
    _hist_df  = _combined[_combined["구분"] == "실제"].copy()

    _ci_band = (
        alt.Chart(_pred_df)
        .mark_area(opacity=0.15)
        .encode(
            x=_mk_x(),
            y=alt.Y("하한:Q", title="발생건수"),
            y2=alt.Y2("상한:Q"),
            color=alt.Color(
                "유형:N",
                legend=alt.Legend(title="이벤트 유형", orient="right"),
            ),
        )
    )
    _pred_line = (
        alt.Chart(_pred_df)
        .mark_line(strokeDash=[5, 3], strokeWidth=2, opacity=0.9)
        .encode(
            x=_mk_x(),
            y=alt.Y("건수:Q"),
            color=alt.Color("유형:N", legend=None),
            tooltip=[
                alt.Tooltip("YM:O",   title="연월"),
                alt.Tooltip("유형:N", title="이벤트 유형"),
                alt.Tooltip("건수:Q", format=".1f", title="예측 건수"),
                alt.Tooltip("하한:Q", format=".1f", title=f"하한({ci_label})"),
                alt.Tooltip("상한:Q", format=".1f", title=f"상한({ci_label})"),
            ],
        )
    )
    _hist_line = (
        alt.Chart(_hist_df)
        .mark_line(strokeWidth=2.5)
        .encode(
            x=_mk_x(),
            y=alt.Y("건수:Q"),
            color=alt.Color(
                "유형:N",
                legend=alt.Legend(title="이벤트 유형", orient="right"),
            ),
            tooltip=[
                alt.Tooltip("YM:O",   title="연월"),
                alt.Tooltip("유형:N", title="이벤트 유형"),
                alt.Tooltip("건수:Q", format=".0f", title="실제 건수"),
            ],
        )
    )
    _hist_pts = (
        alt.Chart(_hist_df)
        .mark_point(size=40, filled=True, opacity=0.8)
        .encode(
            x=_mk_x(),
            y="건수:Q",
            color=alt.Color("유형:N", legend=None),
        )
    )
    _div_line = (
        alt.Chart(pd.DataFrame({"YM": [future_str[0]]}))
        .mark_rule(strokeDash=[4, 4], color="#666", strokeWidth=1.5)
        .encode(x=alt.X("YM:O", scale=alt.Scale(domain=all_ym_domain)))
    ) if future_str else None

    _layers = [_ci_band, _hist_line, _hist_pts, _pred_line]
    if _div_line:
        _layers.append(_div_line)

    st.altair_chart(
        alt.layer(*_layers)
        .properties(height=380)
        .resolve_scale(color="shared"),
        use_container_width=True,
    )
    st.caption(
        f"실선+점=실제 │ 점선+음영=예측({ci_label} 신뢰구간) │ "
        f"수직점선=예측 시작 │ 모델: **{model_choice}** │ "
        f"전체 트렌드 R²={r2_cnt:.2f}"
    )

    # 이벤트 유형별 예측 요약 카드
    if sel_events:
        _card_cols = st.columns(min(len(sel_events) + 1, 4))
        _total_pred_avg = float(np.mean(fc_cnt))
        with _card_cols[0]:
            _sl_icon = "📈" if slope_cnt > 0.05 else ("📉" if slope_cnt < -0.05 else "➡️")
            st.markdown(
                f"<div style='border:2px solid #2c3e50;border-radius:8px;"
                f"padding:10px;margin:4px 0;text-align:center;background:#f8f9fa'>"
                f"<div style='font-size:12px;font-weight:bold;color:#2c3e50'>▶ 전체</div>"
                f"<div style='font-size:20px;color:#2c3e50;font-weight:bold'>{_total_pred_avg:.1f}"
                f"<span style='font-size:10px;color:#888'>건/월</span></div>"
                f"<div style='font-size:12px;color:#555'>{_sl_icon} {'증가' if slope_cnt > 0.05 else ('감소' if slope_cnt < -0.05 else '보합')}</div></div>",
                unsafe_allow_html=True,
            )
        for _i, _evt in enumerate(sel_events):
            _pred_vals = [r["건수"] for r in _all_rows if r["유형"] == _evt and r["구분"] == "예측"]
            if not _pred_vals:
                continue
            _avg_c = float(np.mean(_pred_vals))
            _sl    = _evt_slope.get(_evt, 0)
            _ico   = "📈" if _sl > 0.05 else ("📉" if _sl < -0.05 else "➡️")
            _lbl   = "증가" if _sl > 0.05 else ("감소" if _sl < -0.05 else "보합")
            with _card_cols[(_i + 1) % 4]:
                st.markdown(
                    f"<div style='border:1px solid #ddd;border-radius:8px;"
                    f"padding:10px;margin:4px 0;text-align:center'>"
                    f"<div style='font-size:12px;font-weight:bold;color:#444'>{_evt}</div>"
                    f"<div style='font-size:20px;color:#2980b9;font-weight:bold'>{_avg_c:.1f}"
                    f"<span style='font-size:10px;color:#888'>건/월</span></div>"
                    f"<div style='font-size:12px;color:#555'>{_ico} {_lbl}</div></div>",
                    unsafe_allow_html=True,
                )

    # ══════════════════════════════════════════════════
    # [B] 위험 등급 확률 분포 예측
    # ══════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("#### 🎯 향후 위험 등급 확률 분포 예측")

    _grade_rows: list = []
    for _, _row in monthly.iterrows():
        _tot = max(_row["건수"], 1)
        for g in GRADES_FC:
            _grade_rows.append({
                "YM": _row["YM_str"], "등급": g,
                "비율": _row[g] / _tot, "구분": "실제",
            })
    for i, ym in enumerate(future_str):
        for g in GRADES_FC:
            _grade_rows.append({
                "YM": ym, "등급": g,
                "비율": float(grade_fc[g]["fc"][i]), "구분": "예측",
            })

    _all_grade_df = pd.DataFrame(_grade_rows)
    _x_grade = alt.X(
        "YM:O", title="연월",
        axis=alt.Axis(labelAngle=-45),
        scale=alt.Scale(domain=all_ym_domain),
    )

    gcol1, gcol2 = st.columns([2, 1])
    with gcol1:
        _grade_area = (
            alt.Chart(_all_grade_df)
            .mark_area(opacity=0.82)
            .encode(
                x=_x_grade,
                y=alt.Y("비율:Q", stack="normalize",
                        axis=alt.Axis(format="%"), title="비율(%)"),
                color=alt.Color(
                    "등급:N",
                    scale=alt.Scale(
                        domain=GRADES_FC,
                        range=[GRADE_CLRS[g] for g in GRADES_FC],
                    ),
                    legend=alt.Legend(title="위험 등급"),
                ),
                order=alt.Order("등급:N"),
                tooltip=[
                    "YM:O", "등급:N",
                    alt.Tooltip("비율:Q", format=".1%"),
                    "구분:N",
                ],
            )
            .properties(height=260)
        )
        if future_str:
            _vline_g = (
                alt.Chart(pd.DataFrame({"YM": [future_str[0]]}))
                .mark_rule(strokeDash=[4, 4], color="#777", strokeWidth=1.5)
                .encode(x=alt.X("YM:O", scale=alt.Scale(domain=all_ym_domain)))
            )
            st.altair_chart(
                alt.layer(_grade_area, _vline_g).properties(height=260),
                use_container_width=True,
            )
        else:
            st.altair_chart(_grade_area, use_container_width=True)
        st.caption("점선 왼쪽=실제 │ 점선 오른쪽=예측 구간")

    with gcol2:
        st.markdown("##### 예측 기간 평균 확률")
        _avg_g = {g: float(grade_fc[g]["fc"].mean()) for g in GRADES_FC}
        _tot_g = sum(_avg_g.values())
        if _tot_g > 0:
            _avg_g = {g: v / _tot_g for g, v in _avg_g.items()}
        for g in GRADES_FC:
            _pct = _avg_g[g] * 100
            _c   = GRADE_CLRS[g]
            st.markdown(
                f"<div style='background:{_c}22;border-left:4px solid {_c};"
                f"padding:8px 12px;margin:4px 0;border-radius:0 6px 6px 0;'>"
                f"<b style='color:{_c}'>{g}</b>"
                f"<span style='float:right;font-size:18px;font-weight:bold;"
                f"color:{_c}'>{_pct:.1f}%</span></div>",
                unsafe_allow_html=True,
            )
        _high_sum = _avg_g.get("Critical", 0) + _avg_g.get("High", 0)
        if _high_sum > 0.35:
            st.warning(
                f"⚠️ 고위험(Critical+High) 예측 비율 {_high_sum*100:.0f}% — "
                "예방 조치 강화 필요"
            )

    # ══════════════════════════════════════════════════
    # [C] 예측 요약 테이블
    # ══════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("#### 📋 월별 예측 상세")

    _sum_rows: list = []
    for i, ym in enumerate(future_str):
        _dom = max(GRADES_FC, key=lambda g: grade_fc[g]["fc"][i])
        _sum_rows.append({
            "예측 연월":              ym,
            "예측 발생건수":          round(float(fc_cnt[i]),   1),
            f"하한({ci_label})":      round(float(lo_cnt[i]),   1),
            f"상한({ci_label})":      round(float(hi_cnt[i]),   1),
            "예측 위험점수":          round(float(fc_score[i]), 1),
            "Critical 확률":          f"{grade_fc['Critical']['fc'][i]*100:.1f}%",
            "High 확률":              f"{grade_fc['High']['fc'][i]*100:.1f}%",
            "Medium 확률":            f"{grade_fc['Medium']['fc'][i]*100:.1f}%",
            "Low 확률":               f"{grade_fc['Low']['fc'][i]*100:.1f}%",
            "주요 예측 등급":         _dom,
        })
    _sum_df = pd.DataFrame(_sum_rows)

    _GBGV = {"Critical": "#FADBD8", "High": "#FDEBD0", "Medium": "#FEF9E7", "Low": "#EAFAF1"}
    def _hl_sum(val):
        return f"background-color: {_GBGV.get(val, 'white')}"

    st.dataframe(
        _sum_df.style.map(_hl_sum, subset=["주요 예측 등급"]),
        use_container_width=True, hide_index=True, height=380,
    )

    _csv_fc = _sum_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        "📥 예측 결과 CSV", _csv_fc,
        file_name=f"사고예측_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv", key="fc_csv3",
    )

    # ── 모델 설명 ──────────────────────────────────────
    with st.expander(f"ℹ️ 선택 모델 상세 설명: {model_choice}"):
        st.markdown(f"**{model_choice}**: {MODEL_DESC[model_choice]}")
        st.markdown(f"""
**적용 구조:**
- 월별 발생건수 → {model_choice} → {forecast_months}개월 외삽
- 신뢰구간: 예측값 ± {ci_z} × 잔차 표준편차 ({ci_label} 신뢰수준)
- 위험 등급 비율: 등급별 독립 예측 후 합산 정규화 → 확률 분포
{'- RandomForest 분류 정확도(5-fold CV): ' + f'{rf_accuracy*100:.0f}%' if rf_accuracy else '- RandomForest: 50건 이상 시 활성화'}

| 모델 | 특징 | 적합 상황 |
|---|---|---|
| 선형 회귀 | 직선 추세 외삽, 해석 용이 | 꾸준한 증가·감소 |
| 2차 다항 회귀 | 곡선 추세, 가속·감속 포착 | 비선형 변화 구간 |
| 이동평균 (3M) | 최근 3개월 평균, 변동 완화 | 불규칙 변동이 큰 데이터 |
| 지수평활 | 최근값 가중치 강조 | 최근 수준 변화에 민감 반응 |

> **주의:** 통계적 추세 기반 예측이므로 실제 운영 의사결정 전 전문가 검토가 필요합니다.
        """)
