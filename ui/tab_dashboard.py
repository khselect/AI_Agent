"""
ui/tab_dashboard.py — 탭3: 사고 데이터 대시보드
"""
import numpy as np
import pandas as pd
import altair as alt
import streamlit as st

from safety_core import get_all_accidents


def analyze_trends(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    return {
        'total': len(df),
        'high_risk': int(df['risk_grade'].isin(['High','Critical']).sum()) if 'risk_grade' in df.columns else 0,
        'avg_risk_score': float(df['risk_score'].mean()) if 'risk_score' in df.columns else 0,
        'total_deaths': int(df['사망자수'].fillna(0).sum()) if '사망자수' in df.columns else 0,
        'total_injured': int(df['부상자수'].fillna(0).sum()) if '부상자수' in df.columns else 0,
    }


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


def render_dashboard_tab(delete_accident_fn):
    """
    탭3 대시보드 UI.

    Args:
        delete_accident_fn: UI 전용 delete_accident 함수
    """
    st.subheader("📊 사고 데이터 대시보드")
    df_all = get_all_accidents()

    if df_all.empty:
        st.info("데이터 없음. Tab 1에서 보고서를 입력하세요.")
        return

    trends = analyze_trends(df_all)
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("총 사고",       f"{trends.get('total',0)}건")
    k2.metric("High 위험",     f"{trends.get('high_risk',0)}건")
    k3.metric("평균 위험점수", f"{trends.get('avg_risk_score',0):.1f}점")
    k4.metric("총 사망자",     f"{trends.get('total_deaths',0)}명")
    k5.metric("총 부상자",     f"{trends.get('total_injured',0)}명")
    st.divider()

    if len(df_all) >= 50:
        df_all = run_anomaly_detection(df_all)
        n_anom = int(df_all['is_anomaly'].sum()) if 'is_anomaly' in df_all.columns else 0
        if n_anom > 0:
            st.warning(f"⚠️ Isolation Forest: {n_anom}건 이상 패턴 탐지")
    else:
        st.caption(f"💡 {len(df_all)}/50건 — 50건 이상 시 이상탐지 활성화")

    r1c1, r1c2 = st.columns(2)
    with r1c1:
        st.markdown("##### 위험 등급 분포")
        if 'risk_grade' in df_all.columns:
            gc = df_all['risk_grade'].value_counts().reset_index(); gc.columns=['등급','건수']
            st.altair_chart(alt.Chart(gc).mark_bar(cornerRadiusTopLeft=4,cornerRadiusTopRight=4).encode(
                x=alt.X('등급',sort=['Critical','High','Medium','Low']), y='건수',
                color=alt.Color('등급',scale=alt.Scale(
                    domain=['Critical','High','Medium','Low'],
                    range=['#922B21','#e74c3c','#f39c12','#27ae60']),legend=None),
                tooltip=['등급','건수']).properties(height=250), use_container_width=True)

    with r1c2:
        st.markdown("##### 노선별 사고 건수")
        if '노선' in df_all.columns:
            lc = df_all['노선'].value_counts().head(10).reset_index(); lc.columns=['노선','건수']
            st.altair_chart(alt.Chart(lc).mark_bar(color='#2980b9').encode(
                x='건수', y=alt.Y('노선',sort='-x'), tooltip=['노선','건수']).properties(height=250),
                use_container_width=True)

    r2c1, r2c2 = st.columns(2)
    with r2c1:
        st.markdown("##### 근본원인 분포")
        if '근본원인그룹' in df_all.columns:
            cc = df_all['근본원인그룹'].dropna().value_counts().reset_index(); cc.columns=['원인','건수']
            st.altair_chart(alt.Chart(cc).mark_arc(innerRadius=50).encode(
                theta='건수', color=alt.Color('원인',legend=alt.Legend(orient='right')),
                tooltip=['원인','건수']).properties(height=250), use_container_width=True)

    with r2c2:
        st.markdown("##### 이벤트 소분류 Top 10")
        if '이벤트소분류' in df_all.columns:
            ec = df_all['이벤트소분류'].dropna().value_counts().head(10).reset_index(); ec.columns=['유형','건수']
            st.altair_chart(alt.Chart(ec).mark_bar(color='#8e44ad').encode(
                x='건수', y=alt.Y('유형',sort='-x'), tooltip=['유형','건수']).properties(height=250),
                use_container_width=True)

    if 'risk_score' in df_all.columns and df_all['risk_score'].notna().any():
        st.markdown("##### 위험 점수 분포")
        hd = df_all[['risk_score']].dropna()
        st.altair_chart(alt.Chart(hd).mark_bar(color='#e74c3c',opacity=0.7).encode(
            x=alt.X('risk_score:Q',bin=alt.Bin(maxbins=20),title='위험 점수'),
            y=alt.Y('count()',title='건수'), tooltip=[alt.Tooltip('risk_score:Q',bin=True),'count()']
        ).properties(height=160), use_container_width=True)

    st.divider()
    st.markdown("##### 📋 전체 데이터")
    disp_cols = [c for c in ['id','발생일자','노선','이벤트소분류','근본원인그룹','사망자수',
                              '피해액(백만원)','risk_grade','risk_score'] if c in df_all.columns]
    st.dataframe(df_all[disp_cols].head(200), use_container_width=True, hide_index=True, height=280,
        column_config={'risk_score':st.column_config.ProgressColumn('위험점수',format='%.0f',min_value=0,max_value=100)})

    with st.expander("🗑️ 데이터 삭제"):
        del_id = st.number_input("삭제할 ID", min_value=1, step=1)
        if st.button("삭제", type="primary"):
            delete_accident_fn(int(del_id))
            st.success(f"ID {del_id} 삭제")
            st.rerun()
