"""
gen_data.py ─ 철도 사고 가상 데이터 생성기 v3.1
─────────────────────────────────────────────────────
목표 분포: Critical 15% / High 20% / Medium 35% / Low 30%

인명사고 원칙:
  사망자 ≥ 1  → score ≥ 60  (High 이상) ← C=1~3 데이터 사망자=0
  사망자 ≥ 3  → score ≥ 80  (Critical)
  부상자 ≥ 20 → score ≥ 80  (Critical)
  사망자 ≥ 5  → score ≥ 90
"""
import duckdb, random, os, json
from datetime import date, timedelta, datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "shared", "railway_accidents.duckdb")
random.seed(42)

# ── 이벤트 카탈로그 ───────────────────────────────────────────
EVT = [
    # idx  대        중       소            원인그룹      원인유형
    ("사고","차량",  "탈선",        "기술적요인","궤도·차량 결함"),   # 0
    ("사고","차량",  "충돌",        "인적요인",  "운전취급 오류"),    # 1
    ("사고","차량",  "화재",        "기술적요인","전기·기계 결함"),   # 2
    ("사고","차량",  "폭발",        "기술적요인","압력계통 결함"),    # 3
    ("사고","인적",  "추락",        "인적요인",  "승객 부주의"),      # 4
    ("사고","인적",  "투신",        "인적요인",  "외부인 침입"),      # 5
    ("사고","인적",  "인명사상",    "인적요인",  "선로 무단 침입"),   # 6
    ("사고","시설",  "시설물손괴",  "환경적요인","자연재해·외력"),    # 7
    ("장애","신호",  "신호장애",    "기술적요인","신호설비 결함"),    # 8
    ("장애","신호",  "신호무응답",  "기술적요인","S/W 오류"),         # 9
    ("장애","신호",  "ATC장애",     "기술적요인","ATC 장치 오류"),    # 10
    ("장애","전력",  "전력장애",    "기술적요인","급전설비 결함"),    # 11
    ("장애","전력",  "전력고장",    "기술적요인","변전소 이상"),      # 12
    ("장애","전력",  "가선단선",    "환경적요인","기상·외력"),        # 13
    ("장애","차량",  "차량고장",    "기술적요인","차량 노후화"),      # 14
    ("장애","차량",  "제동장치고장","기술적요인","제동계통 결함"),    # 15
    ("장애","차량",  "출입문고장",  "기술적요인","도어 시스템 결함"), # 16
    ("장애","차량",  "문고장",      "기술적요인","도어 기계 결함"),   # 17
    ("장애","차량",  "공조장치고장","기술적요인","냉난방 장치 결함"), # 18
    ("장애","차량",  "차축·차륜결함","기술적요인","차륜·베어링 마모"),# 19
    ("장애","선로",  "궤도고장",    "기술적요인","레일 결함"),        # 20
    ("장애","선로",  "궤도틀림",    "기술적요인","선로 유지보수 미흡"),# 21
    ("장애","선로",  "분기기결함",  "기술적요인","분기기 전환 불량"), # 22
    ("장애","선로",  "선로침입",    "환경적요인","외부인 침입"),      # 23
    ("장애","운행",  "운행장애",    "인적요인",  "관제 오류"),        # 24
    ("장애","통신",  "통신장애",    "기술적요인","통신설비 결함"),    # 25
    ("장애","전철기","전철기고장",  "기술적요인","전철기 구동 결함"), # 26
    ("장애","역설비","검표기장애",  "기술적요인","역설비 결함"),      # 27
]

# ── score 계산 (safety_analytics.py와 동일) ─────────────────
HIGH_KW = ['탈선','충돌','화재','폭발','추락','붕괴']
def calc_score(dead, inj, dmg, delay, sub):
    efi = dead + inj / 100.0
    s  = min(efi * 20, 40)
    s += min(dmg / 50, 20)
    s += min(delay / 40, 15)
    if any(k in sub for k in HIGH_KW):        s += 15
    elif any(k in sub for k in ['인명','손괴','투신']): s += 10
    else:                                      s +=  5
    if dead >= 1:              s = max(s, 60.0)
    if dead >= 3 or inj >= 20: s = max(s, 80.0)
    if dead >= 5:              s = max(s, 90.0)
    return min(round(s, 1), 100.0)

# ── Tier 정의 (파라미터 범위 실측 기반) ─────────────────────
# Critical-A: 사망 3+ (score floor 80)
# Critical-B: 부상 20+ (score floor 80, 사망=0)
# High       : 사망 1명 (score floor 60, inj<20 유지)
# Medium     : 사망 0, 부상 0~19, 高피해+高위험이벤트 → 25~59
# Low        : 사망 0, 부상 0, 장애류만 → <25

TIERS = [
    # ── Critical-A (사망3+) ──────────────────────────────────
    {"tier":"Critical","count":45,"_min":80,"_max":100,
     "dead":(3,8),"inj":(2,15),"dmg":(200,1500),"delay":(60,400),
     "evt_idx":[0,1,2,3,4,5,6,7],"evt_wt":[18,22,18,8,6,4,10,4]},
    # ── Critical-B (부상20+) ────────────────────────────────
    {"tier":"Critical","count":30,"_min":80,"_max":100,
     "dead":(0,0),"inj":(20,50),"dmg":(200,1500),"delay":(60,300),
     "evt_idx":[0,1,2,3,4,6,7],"evt_wt":[18,22,18,8,8,12,6]},
    # ── High (사망1명) ──────────────────────────────────────
    {"tier":"High","count":100,"_min":60,"_max":79,
     "dead":(1,1),"inj":(0,15),"dmg":(30,800),"delay":(20,250),
     "evt_idx":[0,1,2,4,5,6,7,8,11,14],"evt_wt":[14,18,12,8,5,8,6,8,8,6]},
    # ── Medium ──────────────────────────────────────────────
    # 사망 없음, 부상 8~19, 高위험이벤트(+15), 충분한 피해
    # score 구간 확보: efi(0.08~0.19)*20 + dmg/50 + delay/40 + 15
    {"tier":"Medium","count":175,"_min":25,"_max":59,
     "dead":(0,0),"inj":(8,19),"dmg":(300,2000),"delay":(40,250),
     "evt_idx":[0,1,2,3,4,6,7],"evt_wt":[18,22,18,8,8,12,6]},
    # ── Low ────────────────────────────────────────────────
    {"tier":"Low","count":150,"_min":0,"_max":24,
     "dead":(0,0),"inj":(0,2),"dmg":(0,70),"delay":(0,25),
     "evt_idx":list(range(8,len(EVT))),"evt_wt":None},
]

# ── 보조 데이터 ───────────────────────────────────────────────
LINES=[("도시철도","서울1호선"),("도시철도","서울2호선"),("도시철도","서울3호선"),
       ("도시철도","서울4호선"),("도시철도","서울5호선"),("도시철도","서울7호선"),
       ("도시철도","부산1호선"),("도시철도","부산2호선"),
       ("도시철도","대구1호선"),("도시철도","인천1호선"),("도시철도","인천2호선"),("도시철도","인천7호선"),
       ("일반철도","경부선"),("일반철도","경인선"),("일반철도","중앙선"),
       ("고속철도","KTX경부"),("고속철도","SRT")]
AGENCIES={"서울1호선":"서울교통공사","서울2호선":"서울교통공사","서울3호선":"서울교통공사",
           "서울4호선":"서울교통공사","서울5호선":"서울교통공사","서울7호선":"서울교통공사",
           "부산1호선":"부산교통공사","부산2호선":"부산교통공사",
           "대구1호선":"대구도시철도","인천1호선":"인천교통공사","인천2호선":"인천교통공사",
           "인천7호선":"인천교통공사",
           "경부선":"KORAIL","경인선":"KORAIL","중앙선":"KORAIL",
           "KTX경부":"KORAIL","SRT":"SR"}
STATIONS=["서울역","용산역","영등포역","신도림역","구로역","수원역","인천역",
          "부산역","동대구역","대전역","강남역","홍대입구역","신촌역","왕십리역","대구역"]
WEATHERS=["맑음"]*6+["흐림"]*2+["비","눈","안개"]
LOCS=[("역","승강장","승강장"),("역","구내선로","역구내 선로"),
      ("본선","본선","본선 상"),("기지","차량기지","차량기지 내")]
ACTIONS=["현장 점검 및 즉시 복구 조치","관련 설비 교체 및 정기 점검 강화",
         "비상 운전 전환 후 복구","운전 취급 절차 재교육 실시",
         "해당 구간 서행 운전 지시","전문 기술 팀 긴급 투입",
         "시스템 재기동 및 이중화 점검","현장 통제 후 안전 점검 완료"]
TRAIN_MAP={"도시철도":"전동열차","일반철도":"여객열차","고속철도":"KTX"}
TRACKS=["지하","지상","교량"]
SIGS=["ATP/ATO","ATP","자동폐색","CTC"]

def make_rec(tc, retries=20):
    """tier 목표 score 범위 내 레코드 생성 (최대 retries회 시도)"""
    lo, hi = tc["_min"], tc["_max"]
    for _ in range(retries):
        idxs=tc["evt_idx"]; wts=tc["evt_wt"]
        ei = random.choices(idxs,weights=wts,k=1)[0] if wts else random.choice(idxs)
        大,中,小,원인그룹,원인유형 = EVT[ei]
        dead = random.randint(*tc["dead"])
        inj  = random.randint(*tc["inj"])
        dmg  = round(random.uniform(*tc["dmg"]),1)
        delay= random.randint(*tc["delay"])
        sc   = calc_score(dead, inj, dmg, delay, 小)
        if lo <= sc <= hi:
            break
    # 범위 초과 시 score를 범위 내로 강제 클램프 (score는 정보용)
    sc = min(max(sc, lo), hi) if not (lo<=sc<=hi) else sc

    start = date(2020, 1, 1)
    end   = date(2026, 3, 24)
    d     = start + timedelta(days=random.randint(0, (end - start).days))
    hr = random.choices(range(24),
         weights=[1,1,1,1,1,1,3,8,5,3,3,3,3,5,3,3,5,8,5,3,2,2,1,1],k=1)[0]
    mn = random.randint(0,59)
    철도구분,노선 = random.choice(LINES)
    기관 = AGENCIES[노선]
    loc  = random.choice(LOCS)
    역A  = random.choice(STATIONS)
    역B  = random.choice([s for s in STATIONS if s!=역A])
    날씨 = random.choice(WEATHERS)
    온도 = round(random.uniform(-10,35),1)
    강우 = round(random.uniform(0,50),1) if 날씨=="비" else 0.0
    적설 = round(random.uniform(0,20),1) if 날씨=="눈" else 0.0
    지연여= "지연" if delay>0 else "무지연"
    지연수= random.randint(1,15) if delay>0 else 0
    grade=("Critical" if sc>=80 else "High" if sc>=60 else "Medium" if sc>=25 else "Low")
    개요 = (f"{d} {hr:02d}:{mn:02d} {노선} {역A} 구간에서 {小} 발생. "
            f"사망 {dead}명 부상 {inj}명. {delay}분 운행 영향.")
    return {
        "발생일자":str(d),"발생시간":f"{hr:02d}:{mn:02d}",
        "등록기관":기관,"철도구분":철도구분,"노선":노선,
        "이벤트대분류":大,"이벤트중분류":中,"이벤트소분류":小,
        "주원인":원인유형,"근본원인그룹":원인그룹,"근본원인유형":원인유형,
        "근본원인상세":f"{원인유형}에 의한 {小}","직접원인":f"{원인유형} 미조치",
        "운행영향유형":"운행중단" if delay>60 else ("지연운행" if delay>0 else "해당없음"),
        "지연여부":지연여,"지연원인":f"{小} 발생 지연" if delay>0 else "",
        "지연원인상세":f"{小} 복구 소요" if delay>0 else "",
        "지연열차수":지연수,"최대지연시간(분)":delay,
        "총피해인원":dead+inj,"사망자수":dead,"부상자수":inj,"피해액(백만원)":dmg,
        "행정구역":"서울특별시" if "서울" in 노선 else "기타",
        "발생역A":역A,"발생역B":역B,"장소대분류":loc[0],"장소중분류":loc[1],"상세위치":loc[2],
        "기상상태":날씨,"온도":온도,"강우량":강우,"적설량":적설,
        "대상구분":"열차","열차종류":TRAIN_MAP.get(철도구분,"전동열차"),
        "선로유형":random.choice(TRACKS),"신호시스템유형":random.choice(SIGS),
        "고장부품명":f"{小} 관련 부품","고장현상":f"{小} 현상","고장원인":원인유형,
        "조치내용":random.choice(ACTIONS),"이벤트개요":개요,
        "데이터 출처":"가상데이터(gen_data_v3)",
        "_score":sc,"_grade":grade,
    }

def rebuild_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH); print("🗑  기존 DB 삭제")
    conn = duckdb.connect(DB_PATH)
    conn.execute("CREATE SEQUENCE accidents_seq START 1")
    conn.execute("""
    CREATE TABLE accidents (
        id INTEGER PRIMARY KEY, created_at TIMESTAMP, source_file VARCHAR,
        발생일자 VARCHAR, 발생시간 VARCHAR, 등록기관 VARCHAR, 철도구분 VARCHAR, 노선 VARCHAR,
        이벤트대분류 VARCHAR, 이벤트중분류 VARCHAR, 이벤트소분류 VARCHAR, 주원인 VARCHAR,
        근본원인그룹 VARCHAR, 근본원인유형 VARCHAR, 근본원인상세 VARCHAR, 직접원인 VARCHAR,
        운행영향유형 VARCHAR, 지연여부 VARCHAR, 지연원인 VARCHAR, 지연원인상세 VARCHAR,
        지연열차수 INTEGER, "최대지연시간(분)" INTEGER,
        총피해인원 INTEGER, 사망자수 INTEGER, 부상자수 INTEGER, "피해액(백만원)" DOUBLE,
        행정구역 VARCHAR, 발생역A VARCHAR, 발생역B VARCHAR,
        장소대분류 VARCHAR, 장소중분류 VARCHAR, 상세위치 VARCHAR,
        기상상태 VARCHAR, 온도 DOUBLE, 강우량 DOUBLE, 적설량 DOUBLE,
        대상구분 VARCHAR, 열차종류 VARCHAR, 선로유형 VARCHAR, 신호시스템유형 VARCHAR,
        고장부품명 VARCHAR, 고장현상 VARCHAR, 고장원인 VARCHAR, 조치내용 VARCHAR,
        이벤트개요 VARCHAR, 데이터출처 VARCHAR,
        risk_score DOUBLE, risk_grade VARCHAR, raw_json VARCHAR
    )""")

    buckets={"Critical":0,"High":0,"Medium":0,"Low":0}
    total=0
    for tc in TIERS:
        recs=[make_rec(tc) for _ in range(tc["count"])]
        for r in recs:
            rid=conn.execute("SELECT nextval('accidents_seq')").fetchone()[0]
            conn.execute("INSERT INTO accidents VALUES ("+",".join(["?"]*49)+")",[
                rid,datetime.now(),"gen_data_v3",
                r["발생일자"],r["발생시간"],r["등록기관"],r["철도구분"],r["노선"],
                r["이벤트대분류"],r["이벤트중분류"],r["이벤트소분류"],r["주원인"],
                r["근본원인그룹"],r["근본원인유형"],r["근본원인상세"],r["직접원인"],
                r["운행영향유형"],r["지연여부"],r["지연원인"],r["지연원인상세"],
                r["지연열차수"],r["최대지연시간(분)"],
                r["총피해인원"],r["사망자수"],r["부상자수"],r["피해액(백만원)"],
                r["행정구역"],r["발생역A"],r["발생역B"],
                r["장소대분류"],r["장소중분류"],r["상세위치"],
                r["기상상태"],r["온도"],r["강우량"],r["적설량"],
                r["대상구분"],r["열차종류"],r["선로유형"],r["신호시스템유형"],
                r["고장부품명"],r["고장현상"],r["고장원인"],r["조치내용"],
                r["이벤트개요"],r["데이터 출처"],
                r["_score"],r["_grade"],json.dumps(r,ensure_ascii=False)])
            bkt=("Critical" if r["_score"]>=80 else
                 "High"     if r["_score"]>=60 else
                 "Medium"   if r["_score"]>=25 else "Low")
            buckets[bkt]+=1; total+=1

        scores=[r["_score"] for r in recs]
        deads =[r["사망자수"] for r in recs]
        print(f"  {tc['tier']:10s} {tc['count']:4d}건 | "
              f"score {min(scores):.0f}~{max(scores):.0f} avg={sum(scores)/len(scores):.1f} | "
              f"사망있음:{sum(1 for d in deads if d>0)}건")
    conn.close()

    print(f"\n✅ 총 {total}건 생성")
    for k,v in buckets.items():
        bar="█"*int(v/total*40)
        print(f"  {k:10s}: {v:4d}건 ({v/total*100:5.1f}%) {bar}")

    conn2=duckdb.connect(DB_PATH,read_only=True)
    bad=conn2.execute("SELECT COUNT(*) FROM accidents WHERE 사망자수>0 AND risk_score<60").fetchone()[0]
    print(f"\n{'✅' if bad==0 else '❌'} [검증] 사망자>0 & score<60 위반: {bad}건")

    print("\n=== C(영향도) 절대기준 시뮬 ===")
    df=conn2.execute("SELECT 이벤트소분류,SUM(사망자수) d,SUM(부상자수) i,COUNT(*) n FROM accidents GROUP BY 1").df()
    df["EFI"]=df["d"]+df["i"]/100
    print(df[df["d"]>0][["이벤트소분류","d","i","n"]].sort_values("d",ascending=False).head(10).to_string())
    conn2.close()

if __name__=="__main__":
    print("="*58)
    print("  철도 사고 가상 데이터 생성기 v3.1")
    print("  Critical 15% / High 20% / Medium 35% / Low 30%")
    print("="*58)
    rebuild_db()
