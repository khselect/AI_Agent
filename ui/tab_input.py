"""
ui/tab_input.py — 탭1: 보고서 입력 (PDF 자동추출 / 수동입력)
"""
import streamlit as st
import pandas as pd
from safety_core import insert_accident, calculate_risk

# PDF 가용성 체크
try:
    import pymupdf4llm
    _PDF_OK = True
except ImportError:
    _PDF_OK = False

_EMPTY = ('', None, 'null', 'NULL', 'None')

_BATCH_NAMES = ["기본정보", "원인·지연", "피해·위치A", "위치·기상", "선로·고장·개요"]


def render_input_tab(model_name: str, extract_from_pdf_fn, columns, batches, column_names):
    """
    탭1 보고서 입력 UI.

    Args:
        model_name: 사이드바에서 선택된 LLM 모델명
        extract_from_pdf_fn: safety_analytics.py 의 extract_from_pdf 함수
        columns: [(필드명, 설명), ...] 리스트
        batches: 배치별 columns 슬라이스
        column_names: 필드명 목록
    """
    st.subheader("📥 사고조사보고서 입력")
    input_mode = st.radio("입력 방식", ["📄 PDF 자동 추출", "✏️ 수동 직접 입력"], horizontal=True)
    st.divider()

    if input_mode == "📄 PDF 자동 추출":
        if not _PDF_OK:
            st.error("pymupdf4llm 미설치: `pip install pymupdf4llm`")
        else:
            uploaded = st.file_uploader("PDF 보고서 업로드", type=["pdf"])
            if uploaded:
                st.success(f"✅ {uploaded.name} ({uploaded.size/1024:.1f} KB)")
                if st.button("🚀 추출 + DB 저장", type="primary"):
                    prog = st.progress(0.0)
                    stat = st.empty()
                    def upd(pct, msg):
                        prog.progress(pct)
                        stat.info(msg)
                    try:
                        extracted, _ = extract_from_pdf_fn(uploaded.getvalue(), model_name, upd)
                        row_id = insert_accident(extracted, uploaded.name)
                        prog.progress(1.0)
                        stat.success(f"🎉 저장 완료! (DB ID: {row_id})")
                        score, grade = calculate_risk(extracted)
                        filled = sum(1 for k in column_names if extracted.get(k) not in _EMPTY)
                        st.session_state["tab1_result"] = {
                            "row_id":    row_id,
                            "source":    uploaded.name,
                            "grade":     grade,
                            "score":     score,
                            "filled":    filled,
                            "extracted": extracted,
                        }
                    except Exception as e:
                        import traceback
                        st.error(f"오류: {e}")
                        st.text(traceback.format_exc())

            if "tab1_result" in st.session_state:
                _r = st.session_state["tab1_result"]
                st.success(f"🎉 저장 완료! (DB ID: {_r['row_id']}) · 파일: {_r['source']}")
                c1, c2, c3 = st.columns(3)
                c1.metric("위험 등급", _r["grade"])
                c2.metric("위험 점수", f"{_r['score']}점")
                c3.metric("추출 필드", f"{_r['filled']}/{len(column_names)}")
                with st.expander("📋 추출 결과 (노란색=미추출)", expanded=True):
                    rows = []
                    for n, desc in columns:
                        val = _r["extracted"].get(n, "")
                        is_empty = (val is None or str(val).strip() in _EMPTY)
                        rows.append({
                            "필드명": n,
                            "추출값": "⬜ 미추출" if is_empty else str(val),
                            "설명":   desc,
                        })
                    df_result = pd.DataFrame(rows)

                    def _hl(row):
                        if row["추출값"] == "⬜ 미추출":
                            return ["background-color:#FFF9C4"] * len(row)
                        return [""] * len(row)

                    st.dataframe(
                        df_result.style.apply(_hl, axis=1),
                        use_container_width=True, hide_index=True, height=520,
                    )
                    batch_stats = []
                    for bi, batch in enumerate(batches):
                        filled_b = sum(
                            1 for n, _ in batch
                            if _r["extracted"].get(n)
                            and str(_r["extracted"].get(n)).strip() not in _EMPTY
                        )
                        batch_stats.append(f"배치{bi+1}({_BATCH_NAMES[bi]}): {filled_b}/{len(batch)}")
                    st.caption("  |  ".join(batch_stats))
    else:
        manual = {}
        with st.form("manual_form"):
            c1, c2 = st.columns(2)
            with c1:
                manual['발생일자']     = st.text_input("발생일자 (YYYY-MM-DD)")
                manual['발생시간']     = st.text_input("발생시간 (HH:MM)")
                manual['등록기관']     = st.text_input("등록기관")
                manual['철도구분']     = st.selectbox("철도구분", ["도시철도","일반철도","고속철도"])
                manual['노선']         = st.text_input("노선")
                manual['이벤트대분류'] = st.selectbox("이벤트대분류", ["사고","장애","고장"])
                manual['이벤트중분류'] = st.text_input("이벤트중분류")
                manual['이벤트소분류'] = st.text_input("이벤트소분류")
            with c2:
                manual['근본원인그룹']      = st.selectbox("근본원인그룹", ["인적요인","기술적요인","환경적요인"])
                manual['주원인']            = st.text_input("주원인")
                manual['사망자수']          = st.number_input("사망자수", 0, 100, 0)
                manual['부상자수']          = st.number_input("부상자수", 0, 999, 0)
                manual['피해액(백만원)']    = st.number_input("피해액(백만원)", 0.0, value=0.0)
                manual['최대지연시간(분)']  = st.number_input("최대지연시간(분)", 0, value=0)
                manual['발생역A']           = st.text_input("발생역A")
                manual['기상상태']          = st.selectbox("기상상태", ["맑음","흐림","비","눈","안개"])
            manual['이벤트개요']  = st.text_area("이벤트 개요", height=80)
            manual['조치내용']    = st.text_area("조치내용", height=60)
            manual['데이터출처']  = st.text_input("데이터 출처", "수동 입력")
            if st.form_submit_button("💾 DB 저장", type="primary", use_container_width=True):
                for k in ['사망자수','부상자수','피해액(백만원)','최대지연시간(분)']:
                    manual[k] = str(manual[k])
                row_id = insert_accident(manual, "수동입력")
                score, grade = calculate_risk(manual)
                st.success(f"✅ 저장 완료 (ID: {row_id}) | 위험등급: {grade} ({score}점)")
                st.rerun()
