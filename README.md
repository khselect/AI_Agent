https://claude.ai/public/artifacts/2a4c1515-0f3e-44f6-aaf8-2e5ea3e4bff7

[railway_ai_explainer.html](https://github.com/user-attachments/files/26256229/railway_ai_explainer.html)
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>철도안전 AI 시스템 기술 해설</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
  :root {
    --navy: #0d1f3c;
    --navy-mid: #1a3560;
    --blue: #1e6fd9;
    --blue-lt: #dbeafe;
    --teal: #0d9488;
    --teal-lt: #ccfbf1;
    --amber: #d97706;
    --amber-lt: #fef3c7;
    --red: #dc2626;
    --red-lt: #fee2e2;
    --green: #16a34a;
    --green-lt: #dcfce7;
    --gray: #64748b;
    --gray-lt: #f1f5f9;
    --text: #0f172a;
    --text-muted: #475569;
    --border: #e2e8f0;
    --white: #ffffff;
    --radius: 10px;
    --shadow: 0 1px 4px rgba(0,0,0,0.08), 0 4px 16px rgba(0,0,0,0.06);
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', 'Noto Sans KR', sans-serif;
    background: #f8fafc;
    color: var(--text);
    line-height: 1.7;
    font-size: 15px;
  }

  /* ── NAV ── */
  nav {
    position: sticky;
    top: 0;
    z-index: 100;
    background: var(--navy);
    display: flex;
    align-items: center;
    gap: 0;
    padding: 0 2rem;
    border-bottom: 2px solid var(--blue);
    overflow-x: auto;
  }
  nav a {
    color: rgba(255,255,255,0.65);
    text-decoration: none;
    font-size: 13px;
    padding: 14px 16px;
    white-space: nowrap;
    transition: color .2s, border-bottom .2s;
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
  }
  nav a:hover, nav a.active { color: #fff; border-bottom-color: var(--teal); }
  nav .nav-brand {
    font-size: 13px;
    font-weight: 600;
    color: #fff;
    margin-right: 1rem;
    padding: 14px 0;
    white-space: nowrap;
    letter-spacing: -.3px;
  }
  nav .nav-sep { width: 1px; height: 20px; background: rgba(255,255,255,0.15); margin: 0 4px; }

  /* ── HERO ── */
  .hero {
    background: linear-gradient(135deg, var(--navy) 0%, var(--navy-mid) 60%, #164e6e 100%);
    color: white;
    padding: 4rem 2rem 3rem;
    text-align: center;
    position: relative;
    overflow: hidden;
  }
  .hero::before {
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 300px; height: 300px;
    border-radius: 50%;
    background: rgba(13,148,136,.12);
  }
  .hero::after {
    content: '';
    position: absolute;
    bottom: -80px; left: -40px;
    width: 240px; height: 240px;
    border-radius: 50%;
    background: rgba(30,111,217,.1);
  }
  .hero-label {
    display: inline-block;
    background: rgba(13,148,136,.25);
    color: #5eead4;
    font-size: 12px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    padding: 4px 14px;
    border-radius: 20px;
    border: 1px solid rgba(94,234,212,.3);
    margin-bottom: 1.2rem;
  }
  .hero h1 {
    font-size: clamp(1.6rem, 4vw, 2.4rem);
    font-weight: 700;
    line-height: 1.3;
    margin-bottom: .8rem;
    letter-spacing: -.5px;
  }
  .hero-sub {
    font-size: 15px;
    color: rgba(255,255,255,.7);
    max-width: 560px;
    margin: 0 auto 2rem;
  }
  .tech-chips {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 8px;
    position: relative;
    z-index: 1;
  }
  .chip {
    background: rgba(255,255,255,.1);
    border: 1px solid rgba(255,255,255,.2);
    color: rgba(255,255,255,.9);
    font-size: 12px;
    padding: 5px 14px;
    border-radius: 20px;
    backdrop-filter: blur(4px);
  }
  .chip.c-teal { background: rgba(13,148,136,.25); border-color: rgba(13,148,136,.5); color: #5eead4; }
  .chip.c-blue { background: rgba(30,111,217,.25); border-color: rgba(30,111,217,.5); color: #93c5fd; }
  .chip.c-amber { background: rgba(217,119,6,.25); border-color: rgba(217,119,6,.5); color: #fcd34d; }

  /* ── SECTIONS ── */
  .section {
    max-width: 900px;
    margin: 0 auto;
    padding: 3rem 2rem;
    scroll-margin-top: 54px;
  }
  .section-header {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    margin-bottom: 2rem;
    padding-bottom: 1.2rem;
    border-bottom: 2px solid var(--border);
  }
  .section-num {
    width: 40px; height: 40px;
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 16px;
    font-weight: 700;
    flex-shrink: 0;
    margin-top: 2px;
  }
  .num-teal { background: var(--teal-lt); color: var(--teal); }
  .num-blue { background: var(--blue-lt); color: var(--blue); }
  .num-amber { background: var(--amber-lt); color: var(--amber); }
  .num-green { background: var(--green-lt); color: var(--green); }
  .section-title-block h2 {
    font-size: 1.4rem;
    font-weight: 700;
    letter-spacing: -.4px;
    margin-bottom: 3px;
  }
  .section-title-block .tech-tag {
    font-size: 11px;
    font-family: 'Courier New', monospace;
    background: var(--gray-lt);
    color: var(--gray);
    padding: 2px 8px;
    border-radius: 4px;
    letter-spacing: .3px;
  }

  /* ── CARDS ── */
  .card {
    background: var(--white);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.5rem;
    box-shadow: var(--shadow);
  }
  .card + .card { margin-top: 1rem; }
  .card-label {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--gray);
    margin-bottom: .6rem;
  }

  /* ── GRID ── */
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
  .grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; }
  .grid-4 { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: .75rem; }
  @media (max-width: 700px) {
    .grid-2, .grid-3, .grid-4 { grid-template-columns: 1fr; }
  }

  /* ── DIVIDER ── */
  .section-divider { border: none; border-top: 1px solid var(--border); margin: 0; }

  /* ── HIGHLIGHT BOX ── */
  .highlight {
    border-left: 4px solid;
    padding: .8rem 1rem;
    border-radius: 0 8px 8px 0;
    font-size: 14px;
    margin: 1rem 0;
  }
  .hl-teal { border-color: var(--teal); background: var(--teal-lt); color: #0f5a53; }
  .hl-blue { border-color: var(--blue); background: var(--blue-lt); color: #1e40af; }
  .hl-amber { border-color: var(--amber); background: var(--amber-lt); color: #92400e; }
  .hl-navy { border-color: var(--navy); background: #e8eef8; color: var(--navy); }

  /* ── STEP FLOW ── */
  .step-flow { display: flex; align-items: stretch; gap: 0; flex-wrap: wrap; margin: 1.2rem 0; }
  .step-box {
    flex: 1;
    min-width: 110px;
    background: var(--white);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: .8rem .6rem;
    text-align: center;
    position: relative;
    box-shadow: var(--shadow);
  }
  .step-box .step-icon { font-size: 20px; margin-bottom: 4px; }
  .step-box .step-name { font-size: 12px; font-weight: 600; color: var(--text); }
  .step-box .step-desc { font-size: 11px; color: var(--text-muted); margin-top: 2px; line-height: 1.4; }
  .step-arrow {
    display: flex; align-items: center; justify-content: center;
    width: 24px; flex-shrink: 0; color: var(--gray); font-size: 16px;
  }

  /* ── DIAGRAM BOX ── */
  .diagram-box {
    background: var(--white);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.5rem;
    box-shadow: var(--shadow);
    overflow: hidden;
  }

  /* ── MINI BADGE ── */
  .badge {
    display: inline-block;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 4px;
    margin: 0 2px;
  }
  .badge-red { background: var(--red-lt); color: var(--red); }
  .badge-amber { background: var(--amber-lt); color: var(--amber); }
  .badge-yellow { background: #fef9c3; color: #a16207; }
  .badge-green { background: var(--green-lt); color: var(--green); }
  .badge-blue { background: var(--blue-lt); color: var(--blue); }
  .badge-teal { background: var(--teal-lt); color: var(--teal); }
  .badge-gray { background: var(--gray-lt); color: var(--gray); }

  /* ── CODE INLINE ── */
  code {
    font-family: 'Courier New', monospace;
    font-size: 12px;
    background: #f1f5f9;
    color: #c026d3;
    padding: 1px 5px;
    border-radius: 3px;
  }

  /* ── TABLE ── */
  .compare-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .compare-table th {
    background: var(--navy);
    color: white;
    padding: 8px 12px;
    text-align: left;
    font-weight: 600;
  }
  .compare-table td { padding: 8px 12px; border-bottom: 1px solid var(--border); vertical-align: top; }
  .compare-table tr:last-child td { border-bottom: none; }
  .compare-table tr:nth-child(even) td { background: var(--gray-lt); }

  /* ── OLLAMA ANIMATION ── */
  @keyframes pulse-dot {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: .5; transform: scale(.8); }
  }
  @keyframes flow-right {
    0% { stroke-dashoffset: 20; }
    100% { stroke-dashoffset: 0; }
  }
  @keyframes fade-in-up {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .animate-in { animation: fade-in-up .5s ease forwards; }
  .dot-pulse { animation: pulse-dot 1.2s ease-in-out infinite; }
  .flow-line { stroke-dasharray: 6 4; animation: flow-right .8s linear infinite; }

  /* ── LANGGRAPH ANIMATION ── */
  @keyframes loop-glow {
    0%, 100% { opacity: .3; }
    50% { opacity: .9; }
  }
  .loop-arrow { animation: loop-glow 2s ease-in-out infinite; }

  /* RISK FORMULA */
  .formula-block {
    background: var(--navy);
    color: #e2e8f0;
    border-radius: 8px;
    padding: 1rem 1.5rem;
    font-family: 'Courier New', monospace;
    font-size: 13px;
    line-height: 2;
    overflow-x: auto;
  }
  .formula-block .comment { color: #94a3b8; }
  .formula-block .keyword { color: #7dd3fc; }
  .formula-block .number { color: #86efac; }
  .formula-block .string { color: #fde68a; }
  .formula-block .func { color: #c4b5fd; }

  /* MODEL SELECTOR */
  .model-tabs { display: flex; gap: 0; border-bottom: 2px solid var(--border); margin-bottom: 1rem; flex-wrap: wrap; }
  .model-tab {
    padding: 8px 16px;
    font-size: 13px;
    cursor: pointer;
    border: none;
    background: none;
    color: var(--text-muted);
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
    transition: all .2s;
  }
  .model-tab:hover { color: var(--text); }
  .model-tab.active { color: var(--blue); border-bottom-color: var(--blue); font-weight: 600; }

  /* RISK MATRIX */
  .risk-matrix-grid {
    display: grid;
    grid-template-columns: 40px repeat(4, 1fr);
    grid-template-rows: repeat(5, 1fr);
    gap: 3px;
    font-size: 11px;
    text-align: center;
    margin: 1rem 0;
  }
  .rm-cell {
    padding: 6px 4px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 11px;
  }
  .rm-label { background: none; color: var(--text-muted); display: flex; align-items: center; justify-content: center; font-size: 10px; }
  .rm-critical { background: #fee2e2; color: #991b1b; }
  .rm-high { background: #ffedd5; color: #9a3412; }
  .rm-medium { background: #fef9c3; color: #854d0e; }
  .rm-low { background: #dcfce7; color: #166534; }

  /* FOOTER */
  footer {
    text-align: center;
    padding: 2rem;
    font-size: 12px;
    color: var(--gray);
    border-top: 1px solid var(--border);
    background: var(--white);
    margin-top: 2rem;
  }
</style>
</head>
<body>

<!-- NAV -->
<nav id="main-nav">
  <span class="nav-brand">🚆 철도안전 AI 기술 해설</span>
  <div class="nav-sep"></div>
  <a href="#sec-ollama">01 Ollama</a>
  <a href="#sec-langchain">02 LangChain</a>
  <a href="#sec-langgraph">03 LangGraph</a>
  <a href="#sec-ml">04 ML 예측 모델</a>
  <a href="#sec-integration">05 통합 구조</a>
</nav>

<!-- HERO -->
<div class="hero">
  <div class="hero-label">Technical Overview</div>
  <h1>철도안전 AI 에이전트<br>핵심 기술 해설서</h1>
  <p class="hero-sub">
    사고조사보고서 자동 분석부터 위험 예측까지 — 시스템을 구성하는 4가지 기술이<br>
    철도안전 업무에서 어떻게 작동하는지 설명합니다.
  </p>
  <div class="tech-chips">
    <span class="chip c-teal">Ollama · 로컬 LLM</span>
    <span class="chip c-blue">LangChain · 파이프라인</span>
    <span class="chip c-amber">LangGraph · 자율 에이전트</span>
    <span class="chip">scikit-learn · ML 예측</span>
    <span class="chip">DuckDB · 임베디드 DB</span>
  </div>
</div>


<!-- ══════════════════════════════════════════════
     SECTION 1. OLLAMA
═══════════════════════════════════════════════ -->
<div class="section" id="sec-ollama">
  <div class="section-header">
    <div class="section-num num-teal">01</div>
    <div class="section-title-block">
      <h2>Ollama — 로컬 AI 언어 모델</h2>
      <span class="tech-tag">langchain_ollama · ChatOllama · qwen2.5:3b</span>
    </div>
  </div>

  <div class="highlight hl-teal">
    <strong>한 줄 정의:</strong> 인터넷 없이 업무용 PC에서 직접 구동되는 AI 언어 모델 실행 엔진입니다.<br>
    사고조사보고서(PDF) 안의 비정형 텍스트를 43개 표준 필드로 자동 추출할 때 사용됩니다.
  </div>

  <!-- 클라우드 vs 로컬 비교 -->
  <div class="grid-2" style="margin:1.5rem 0;">
    <div class="card" style="border-top:3px solid #94a3b8;">
      <div class="card-label">기존 방식 — 클라우드 LLM</div>
      <svg viewBox="0 0 300 160" width="100%" style="margin:.5rem 0;">
        <rect x="10" y="10" width="90" height="50" rx="6" fill="#f1f5f9" stroke="#cbd5e1"/>
        <text x="55" y="30" text-anchor="middle" font-size="10" fill="#475569">사고보고서 PDF</text>
        <text x="55" y="46" text-anchor="middle" font-size="9" fill="#94a3b8">(보안 문서)</text>
        <line x1="100" y1="35" x2="140" y2="35" stroke="#94a3b8" stroke-dasharray="4 3"/>
        <text x="120" y="28" text-anchor="middle" font-size="9" fill="#ef4444">인터넷 전송 ⚠</text>
        <rect x="140" y="10" width="80" height="50" rx="6" fill="#fee2e2" stroke="#fca5a5"/>
        <text x="180" y="30" text-anchor="middle" font-size="10" fill="#dc2626">외부 클라우드</text>
        <text x="180" y="44" text-anchor="middle" font-size="9" fill="#ef4444">OpenAI / 기타</text>
        <rect x="20" y="80" width="260" height="32" rx="4" fill="#fff7ed" stroke="#fed7aa"/>
        <text x="150" y="100" text-anchor="middle" font-size="10" fill="#c2410c">⚠ 보안 문서가 외부 서버로 전송됨 — 법적·규정 위반 위험</text>
        <rect x="20" y="120" width="260" height="22" rx="4" fill="#fef2f2" stroke="#fecaca"/>
        <text x="150" y="135" text-anchor="middle" font-size="10" fill="#dc2626">⚠ 네트워크 의존 — 망분리 환경 사용 불가</text>
      </svg>
    </div>
    <div class="card" style="border-top:3px solid var(--teal);">
      <div class="card-label">Ollama 방식 — 로컬 LLM</div>
      <svg viewBox="0 0 300 160" width="100%" style="margin:.5rem 0;">
        <rect x="10" y="10" width="90" height="50" rx="6" fill="#f1f5f9" stroke="#cbd5e1"/>
        <text x="55" y="30" text-anchor="middle" font-size="10" fill="#475569">사고보고서 PDF</text>
        <text x="55" y="46" text-anchor="middle" font-size="9" fill="#94a3b8">(보안 문서)</text>
        <line x1="100" y1="35" x2="130" y2="35" stroke="#0d9488" stroke-width="2"/>
        <polygon points="128,31 136,35 128,39" fill="#0d9488"/>
        <rect x="130" y="10" width="100" height="50" rx="6" fill="#ccfbf1" stroke="#5eead4"/>
        <text x="180" y="30" text-anchor="middle" font-size="10" fill="#0f5a53">업무용 PC 내부</text>
        <text x="180" y="44" text-anchor="middle" font-size="9" fill="#0d9488">Ollama 로컬 서버</text>
        <line x1="232" y1="35" x2="262" y2="35" stroke="#0d9488" stroke-width="2"/>
        <polygon points="260,31 268,35 260,39" fill="#0d9488"/>
        <rect x="238" y="18" width="44" height="34" rx="4" fill="#f0fdf4" stroke="#86efac"/>
        <text x="260" y="33" text-anchor="middle" font-size="9" fill="#166534">분석</text>
        <text x="260" y="44" text-anchor="middle" font-size="9" fill="#166534">결과</text>
        <rect x="10" y="78" width="280" height="24" rx="4" fill="#f0fdf4" stroke="#bbf7d0"/>
        <text x="150" y="94" text-anchor="middle" font-size="10" fill="#166534">✅ 데이터가 외부로 나가지 않음 — 망분리 환경 완벽 지원</text>
        <rect x="10" y="108" width="280" height="24" rx="4" fill="#ecfdf5" stroke="#bbf7d0"/>
        <text x="150" y="124" text-anchor="middle" font-size="10" fill="#166534">✅ 127.0.0.1:11434 소켓 통신 — 완전 오프라인 작동</text>
        <rect x="10" y="134" width="280" height="18" rx="4" fill="#ecfdf5" stroke="#bbf7d0"/>
        <text x="150" y="147" text-anchor="middle" font-size="9" fill="#166534">✅ 모델: qwen2.5:3b (3억 파라미터) — GPU 없이 실행 가능</text>
      </svg>
    </div>
  </div>

  <!-- PDF → 구조화 데이터 파이프라인 -->
  <p style="font-size:14px; color:var(--text-muted); margin-bottom:1rem;">
    Ollama가 처리하는 핵심 작업은 <strong>비정형 텍스트 → 표준 필드 추출</strong>입니다. 사고조사보고서는 기관마다 형식이 다르고 자연어로 서술된 내용이 많아 규칙 기반 파싱만으로는 한계가 있습니다.
  </p>

  <div class="diagram-box" style="margin:1rem 0;">
    <div class="card-label" style="margin-bottom:1rem;">PDF 사고보고서 → 43개 표준 필드 자동 추출 과정</div>
    <div class="step-flow">
      <div class="step-box" style="border-top:3px solid #94a3b8;">
        <div class="step-icon">📄</div>
        <div class="step-name">PDF 원문</div>
        <div class="step-desc">기관별 상이한 양식<br>자연어 서술문</div>
      </div>
      <div class="step-arrow">→</div>
      <div class="step-box" style="border-top:3px solid var(--blue);">
        <div class="step-icon">📝</div>
        <div class="step-name">pymupdf4llm</div>
        <div class="step-desc">PDF → Markdown<br>텍스트 변환</div>
      </div>
      <div class="step-arrow">→</div>
      <div class="step-box" style="border-top:3px solid var(--teal);">
        <div class="step-icon">🤖</div>
        <div class="step-name">Ollama LLM</div>
        <div class="step-desc">qwen2.5:3b<br>필드 이해·추출</div>
      </div>
      <div class="step-arrow">→</div>
      <div class="step-box" style="border-top:3px solid var(--amber);">
        <div class="step-icon">🔍</div>
        <div class="step-name">JSON 파싱</div>
        <div class="step-desc">구조화 응답<br>유효성 검증</div>
      </div>
      <div class="step-arrow">→</div>
      <div class="step-box" style="border-top:3px solid var(--green);">
        <div class="step-icon">🗄️</div>
        <div class="step-name">DuckDB 저장</div>
        <div class="step-desc">43개 필드<br>위험도 산정</div>
      </div>
    </div>
  </div>

  <!-- 추출 필드 예시 -->
  <div class="grid-3" style="margin-top:1rem;">
    <div class="card" style="font-size:13px;">
      <div class="card-label">기본 식별 정보</div>
      <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:.3rem;">
        <span class="badge badge-blue">발생일자</span>
        <span class="badge badge-blue">발생시간</span>
        <span class="badge badge-blue">등록기관</span>
        <span class="badge badge-blue">철도구분</span>
        <span class="badge badge-blue">노선</span>
        <span class="badge badge-blue">발생역</span>
      </div>
    </div>
    <div class="card" style="font-size:13px;">
      <div class="card-label">사고 분류 (이벤트)</div>
      <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:.3rem;">
        <span class="badge badge-amber">이벤트대분류</span>
        <span class="badge badge-amber">이벤트중분류</span>
        <span class="badge badge-amber">이벤트소분류</span>
        <span class="badge badge-amber">주원인</span>
        <span class="badge badge-amber">직접원인</span>
        <span class="badge badge-amber">근본원인</span>
      </div>
    </div>
    <div class="card" style="font-size:13px;">
      <div class="card-label">피해 규모</div>
      <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:.3rem;">
        <span class="badge badge-red">사망자수</span>
        <span class="badge badge-red">부상자수</span>
        <span class="badge badge-amber">피해액</span>
        <span class="badge badge-amber">지연열차수</span>
        <span class="badge badge-amber">최대지연시간</span>
      </div>
    </div>
  </div>
</div>

<hr class="section-divider">


<!-- ══════════════════════════════════════════════
     SECTION 2. LANGCHAIN
═══════════════════════════════════════════════ -->
<div class="section" id="sec-langchain">
  <div class="section-header">
    <div class="section-num num-blue">02</div>
    <div class="section-title-block">
      <h2>LangChain — LLM 연결 파이프라인</h2>
      <span class="tech-tag">langchain_ollama · ChatOllama · HumanMessage · SystemMessage</span>
    </div>
  </div>

  <div class="highlight hl-blue">
    <strong>한 줄 정의:</strong> LLM(언어 모델)을 다양한 도구·데이터 소스와 연결하는 프레임워크입니다.<br>
    "Ollama 모델을 어떻게 호출하고, 프롬프트를 어떻게 구성하고, 응답을 어떻게 처리할까"를 표준화합니다.
  </div>

  <!-- 비유 설명 -->
  <div class="card" style="margin:1rem 0; background: linear-gradient(135deg, #eff6ff, #dbeafe);">
    <div style="display:flex;align-items:flex-start;gap:1rem;">
      <div style="font-size:2rem;flex-shrink:0;">🚦</div>
      <div>
        <p style="font-size:14px; color:#1e40af; font-weight:600; margin-bottom:.3rem;">철도 관제 비유</p>
        <p style="font-size:13px; color:#1e3a8a; line-height:1.6;">
          LangChain은 <strong>관제 시스템의 표준 통신 프로토콜</strong>과 같습니다.<br>
          다양한 신호설비(LLM 종류)가 있어도, 관제사(코드)는 같은 방식으로 명령을 내리고 응답을 받을 수 있습니다.
          Ollama로 교체해도, 나중에 다른 모델로 바꿔도 나머지 코드는 변경 없이 동작합니다.
        </p>
      </div>
    </div>
  </div>

  <!-- LangChain 핵심 구조 SVG -->
  <div class="diagram-box">
    <div class="card-label" style="margin-bottom:1rem;">LangChain 메시지 구조 — 철도안전 에이전트 적용</div>
    <svg viewBox="0 0 700 320" width="100%">
      <!-- System Message -->
      <rect x="20" y="20" width="300" height="120" rx="8" fill="#eff6ff" stroke="#93c5fd"/>
      <rect x="20" y="20" width="300" height="30" rx="8" fill="#1e6fd9"/>
      <text x="30" y="40" font-size="12" fill="white" font-weight="600">SystemMessage (역할 정의)</text>
      <text x="30" y="70" font-size="10" fill="#1e3a8a">당신은 철도안전 AI 에이전트입니다.</text>
      <text x="30" y="86" font-size="10" fill="#1e3a8a">사망자 발생 사고는 반드시 High 이상 분류.</text>
      <text x="30" y="102" font-size="10" fill="#1e3a8a">위험도 High/Critical 시 notify_tool 즉시 실행.</text>
      <text x="30" y="118" font-size="10" fill="#1e3a8a">목표 달성 시 "완료:" 로 시작하는 응답 반환.</text>

      <!-- Human Message -->
      <rect x="20" y="160" width="300" height="80" rx="8" fill="#f0fdf4" stroke="#86efac"/>
      <rect x="20" y="160" width="300" height="30" rx="8" fill="#16a34a"/>
      <text x="30" y="180" font-size="12" fill="white" font-weight="600">HumanMessage (목표 지시)</text>
      <text x="30" y="210" font-size="10" fill="#14532d">"이번 주 High 이상 사고 조회 후</text>
      <text x="30" y="226" font-size="10" fill="#14532d"> 담당자에게 알림 발송해줘."</text>

      <!-- Arrow -->
      <line x1="320" y1="150" x2="360" y2="150" stroke="#64748b" stroke-width="1.5" marker-end="url(#arr2)"/>
      <defs>
        <marker id="arr2" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M2 1L8 5L2 9" fill="none" stroke="#64748b" stroke-width="1.5"/>
        </marker>
        <marker id="arr3" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M2 1L8 5L2 9" fill="none" stroke="#0d9488" stroke-width="1.5"/>
        </marker>
      </defs>

      <!-- LLM Box -->
      <rect x="360" y="80" width="160" height="140" rx="10" fill="#ccfbf1" stroke="#2dd4bf"/>
      <rect x="360" y="80" width="160" height="36" rx="10" fill="#0d9488"/>
      <text x="440" y="103" text-anchor="middle" font-size="12" fill="white" font-weight="600">ChatOllama</text>
      <text x="440" y="138" text-anchor="middle" font-size="11" fill="#0f5a53">model=qwen2.5:3b</text>
      <text x="440" y="154" text-anchor="middle" font-size="11" fill="#0f5a53">temperature=0</text>
      <text x="440" y="170" text-anchor="middle" font-size="11" fill="#0f5a53">num_ctx=16384</text>
      <text x="440" y="187" text-anchor="middle" font-size="10" fill="#134e4a">bind_tools(TOOLS)</text>
      <text x="440" y="203" text-anchor="middle" font-size="10" fill="#134e4a">↑ 7개 도구 연결</text>

      <!-- Output Arrow -->
      <line x1="520" y1="150" x2="560" y2="150" stroke="#0d9488" stroke-width="1.5" marker-end="url(#arr3)"/>

      <!-- Output Box -->
      <rect x="560" y="80" width="120" height="140" rx="8" fill="#fff7ed" stroke="#fed7aa"/>
      <rect x="560" y="80" width="120" height="30" rx="8" fill="#d97706"/>
      <text x="620" y="100" text-anchor="middle" font-size="11" fill="white" font-weight="600">AIMessage</text>
      <text x="620" y="132" text-anchor="middle" font-size="10" fill="#92400e">tool_calls:</text>
      <text x="620" y="148" text-anchor="middle" font-size="9" fill="#78350f">query_db_tool(</text>
      <text x="620" y="162" text-anchor="middle" font-size="9" fill="#78350f"> risk_grade=</text>
      <text x="620" y="176" text-anchor="middle" font-size="9" fill="#78350f"> "High")</text>
      <text x="620" y="196" text-anchor="middle" font-size="9" fill="#92400e">→ LangGraph가</text>
      <text x="620" y="208" text-anchor="middle" font-size="9" fill="#92400e">  도구 실행</text>

      <!-- Label at bottom -->
      <text x="350" y="290" text-anchor="middle" font-size="11" fill="#475569">LangChain은 SystemMessage + HumanMessage + AIMessage 형식으로 대화 맥락을 관리합니다.</text>
      <text x="350" y="308" text-anchor="middle" font-size="11" fill="#64748b">bind_tools()로 7개 도구를 LLM에 연결 — LLM이 스스로 어떤 도구를 쓸지 판단합니다.</text>
    </svg>
  </div>

  <!-- bind_tools 설명 -->
  <div class="grid-2" style="margin-top:1rem;">
    <div class="card">
      <div class="card-label">LangChain 없이 (직접 구현)</div>
      <div class="formula-block" style="font-size:11px; padding:.8rem 1rem; line-height:1.8;">
<span class="comment"># HTTP 요청 직접 구성</span>
payload = {
  <span class="string">"model"</span>: <span class="string">"qwen2.5:3b"</span>,
  <span class="string">"messages"</span>: [...],
  <span class="string">"tools"</span>: [...],  <span class="comment"># 직접 스키마 작성</span>
}
resp = requests.post(<span class="string">"http://..."</span>, json=payload)
tool_calls = resp.json()[<span class="string">"message"</span>][<span class="string">"tool_calls"</span>]
<span class="comment"># 에러처리, 재시도, 스트리밍... 모두 직접 구현</span>
      </div>
    </div>
    <div class="card">
      <div class="card-label">LangChain 사용 (실제 코드)</div>
      <div class="formula-block" style="font-size:11px; padding:.8rem 1rem; line-height:1.8;">
<span class="keyword">from</span> langchain_ollama <span class="keyword">import</span> ChatOllama
llm = ChatOllama(
  model=<span class="string">"qwen2.5:3b"</span>,
  temperature=<span class="number">0</span>,
  num_ctx=<span class="number">16384</span>
)
<span class="comment"># 도구 자동 스키마 생성 + 바인딩</span>
llm_with_tools = llm.bind_tools(TOOLS)
<span class="comment"># 호출 — 에러처리·재시도 내장</span>
response = llm_with_tools.invoke(messages)
      </div>
    </div>
  </div>
</div>

<hr class="section-divider">


<!-- ══════════════════════════════════════════════
     SECTION 3. LANGGRAPH
═══════════════════════════════════════════════ -->
<div class="section" id="sec-langgraph">
  <div class="section-header">
    <div class="section-num num-amber">03</div>
    <div class="section-title-block">
      <h2>LangGraph — 자율 판단 에이전트 루프</h2>
      <span class="tech-tag">StateGraph · ToolNode · AgentState · supervisor_node</span>
    </div>
  </div>

  <div class="highlight hl-amber">
    <strong>한 줄 정의:</strong> LLM이 목표를 받아 스스로 계획을 세우고, 도구를 실행하고, 결과를 보고, 다음 행동을 결정하는 <strong>자율 반복 루프</strong>를 만드는 프레임워크입니다.
  </div>

  <!-- 비유 -->
  <div class="card" style="margin:1rem 0; background: linear-gradient(135deg, #fffbeb, #fef3c7);">
    <div style="display:flex;align-items:flex-start;gap:1rem;">
      <div style="font-size:2rem;flex-shrink:0;">🎯</div>
      <div>
        <p style="font-size:14px; color:#92400e; font-weight:600; margin-bottom:.3rem;">관제 지휘관 비유</p>
        <p style="font-size:13px; color:#78350f; line-height:1.6;">
          LangGraph는 <strong>현장 대응 지휘관</strong>과 같습니다.<br>
          "이번 주 고위험 사고 조회 후 담당자 알림"이라는 목표를 받으면 → DB 조회 → 결과 분석 → 조건 확인 → 알림 발송 → 완료 판단까지
          단계별로 스스로 판단하며 실행합니다. 중간에 오류가 있으면 다른 방법을 찾아 재시도합니다.
        </p>
      </div>
    </div>
  </div>

  <!-- StateGraph 다이어그램 -->
  <div class="diagram-box" style="margin:1rem 0;">
    <div class="card-label" style="margin-bottom:.5rem;">LangGraph StateGraph 실행 구조</div>
    <svg viewBox="0 0 700 380" width="100%">
      <defs>
        <marker id="ag" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M2 1L8 5L2 9" fill="none" stroke="#475569" stroke-width="1.5"/>
        </marker>
        <marker id="ag-blue" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M2 1L8 5L2 9" fill="none" stroke="#1e6fd9" stroke-width="1.5"/>
        </marker>
        <marker id="ag-teal" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M2 1L8 5L2 9" fill="none" stroke="#0d9488" stroke-width="1.5"/>
        </marker>
        <marker id="ag-green" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M2 1L8 5L2 9" fill="none" stroke="#16a34a" stroke-width="1.5"/>
        </marker>
        <marker id="ag-red" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M2 1L8 5L2 9" fill="none" stroke="#dc2626" stroke-width="1.5"/>
        </marker>
      </defs>

      <!-- START -->
      <ellipse cx="100" cy="50" rx="70" ry="24" fill="#1a3560" stroke="#1a3560"/>
      <text x="100" y="55" text-anchor="middle" font-size="12" fill="white" font-weight="600">START</text>
      <text x="100" y="22" text-anchor="middle" font-size="10" fill="#64748b">"이번 주 High 이상</text>
      <text x="100" y="35" text-anchor="middle" font-size="10" fill="#64748b">사고 조회 후 알림"</text>

      <!-- Arrow START → SUPERVISOR -->
      <line x1="100" y1="74" x2="100" y2="114" stroke="#475569" stroke-width="1.5" marker-end="url(#ag)"/>

      <!-- SUPERVISOR NODE -->
      <rect x="30" y="114" width="140" height="80" rx="10" fill="#dbeafe" stroke="#1e6fd9" stroke-width="2"/>
      <rect x="30" y="114" width="140" height="32" rx="10" fill="#1e6fd9"/>
      <text x="100" y="135" text-anchor="middle" font-size="12" fill="white" font-weight="600">Supervisor Node</text>
      <text x="100" y="162" text-anchor="middle" font-size="10" fill="#1e3a8a">LLM이 현재 상태 분석</text>
      <text x="100" y="176" text-anchor="middle" font-size="10" fill="#1e3a8a">다음 행동 결정</text>
      <text x="100" y="190" text-anchor="middle" font-size="9" fill="#64748b">iteration: 0 → 15 (상한)</text>

      <!-- AgentState box -->
      <rect x="240" y="100" width="200" height="130" rx="8" fill="#f8fafc" stroke="#cbd5e1"/>
      <rect x="240" y="100" width="200" height="26" rx="8" fill="#64748b"/>
      <text x="340" y="117" text-anchor="middle" font-size="11" fill="white" font-weight="600">AgentState (공유 상태)</text>
      <text x="254" y="144" font-size="10" fill="#475569">messages:</text>
      <text x="340" y="144" font-size="10" fill="#1e3a8a"> 대화 히스토리</text>
      <text x="254" y="158" font-size="10" fill="#475569">goal:</text>
      <text x="340" y="158" font-size="10" fill="#1e3a8a">     현재 목표</text>
      <text x="254" y="172" font-size="10" fill="#475569">results:</text>
      <text x="340" y="172" font-size="10" fill="#1e3a8a">   도구 실행 결과</text>
      <text x="254" y="186" font-size="10" fill="#475569">iteration:</text>
      <text x="340" y="186" font-size="10" fill="#1e3a8a"> 반복 횟수</text>
      <text x="340" y="220" text-anchor="middle" font-size="9" fill="#94a3b8">→ 모든 노드가 이 상태를 읽고 씁니다</text>

      <!-- should_continue diamond -->
      <polygon points="100,220 140,250 100,280 60,250" fill="#fff7ed" stroke="#d97706" stroke-width="1.5"/>
      <text x="100" y="247" text-anchor="middle" font-size="10" fill="#92400e" font-weight="600">분기</text>
      <text x="100" y="261" text-anchor="middle" font-size="9" fill="#92400e">판단</text>
      <line x1="100" y1="194" x2="100" y2="220" stroke="#475569" stroke-width="1.5" marker-end="url(#ag)"/>

      <!-- TOOL NODE -->
      <rect x="30" y="300" width="140" height="66" rx="10" fill="#ccfbf1" stroke="#0d9488" stroke-width="2"/>
      <rect x="30" y="300" width="140" height="28" rx="10" fill="#0d9488"/>
      <text x="100" y="318" text-anchor="middle" font-size="12" fill="white" font-weight="600">Tool Node</text>
      <text x="100" y="344" text-anchor="middle" font-size="10" fill="#0f5a53">7개 도구 실행</text>
      <text x="100" y="358" text-anchor="middle" font-size="9" fill="#134e4a">결과를 ToolMessage로 반환</text>

      <!-- Arrow: 분기 → tool (tool_calls 있음) -->
      <line x1="76" y1="268" x2="70" y2="300" stroke="#0d9488" stroke-width="1.5" marker-end="url(#ag-teal)"/>
      <text x="38" y="287" font-size="9" fill="#0d9488">tool_calls</text>
      <text x="38" y="298" font-size="9" fill="#0d9488">있음</text>

      <!-- Arrow: tool → supervisor (재계획) -->
      <path d="M170 333 Q230 333 230 154 Q230 114 170 130" fill="none" stroke="#1e6fd9" stroke-width="1.5" stroke-dasharray="5 3" marker-end="url(#ag-blue)"/>
      <text x="210" y="256" font-size="9" fill="#1e6fd9">재계획</text>
      <text x="210" y="268" font-size="9" fill="#1e6fd9">루프</text>

      <!-- END: 완료 -->
      <ellipse cx="480" cy="250" rx="70" ry="24" fill="#16a34a" stroke="#16a34a"/>
      <text x="480" y="255" text-anchor="middle" font-size="12" fill="white" font-weight="600">END (완료)</text>

      <!-- Arrow: 분기 → END (완료) -->
      <line x1="140" y1="250" x2="408" y2="250" stroke="#16a34a" stroke-width="1.5" marker-end="url(#ag-green)"/>
      <text x="270" y="242" text-anchor="middle" font-size="9" fill="#16a34a">"완료:" 응답 or 반복 초과</text>

      <!-- Tool 목록 -->
      <rect x="490" y="80" width="190" height="220" rx="8" fill="#f8fafc" stroke="#e2e8f0"/>
      <rect x="490" y="80" width="190" height="26" rx="8" fill="#374151"/>
      <text x="585" y="97" text-anchor="middle" font-size="11" fill="white" font-weight="600">7개 등록 도구 (Tools)</text>
      <text x="500" y="120" font-size="10" fill="#374151">① extract_pdf_tool</text>
      <text x="500" y="136" font-size="9" fill="#6b7280">  PDF → 43개 필드 추출</text>
      <text x="500" y="152" font-size="10" fill="#374151">② save_db_tool</text>
      <text x="500" y="168" font-size="9" fill="#6b7280">  DB 저장 + 위험도 산정</text>
      <text x="500" y="184" font-size="10" fill="#374151">③ query_db_tool</text>
      <text x="500" y="200" font-size="9" fill="#6b7280">  사고 DB 조회·필터링</text>
      <text x="500" y="216" font-size="10" fill="#374151">④ assess_risk_tool</text>
      <text x="500" y="232" font-size="9" fill="#6b7280">  위험도 즉시 산정</text>
      <text x="500" y="248" font-size="10" fill="#374151">⑤ scenario_tool</text>
      <text x="500" y="264" font-size="9" fill="#6b7280">  Bow-Tie 시나리오 생성</text>
      <text x="500" y="280" font-size="10" fill="#374151">⑥ web_collect_tool</text>
      <text x="500" y="296" font-size="9" fill="#6b7280">  외부 URL 데이터 수집</text>
      <rect x="490" y="274" width="190" height="26" rx="0"/>
      <text x="500" y="312" font-size="10" fill="#d97706">⑦ notify_tool</text>
      <text x="500" y="328" font-size="9" fill="#78350f">  담당자 알림 발송</text>

      <!-- 반복횟수 표시 -->
      <rect x="460" y="310" width="120" height="44" rx="6" fill="#fef2f2" stroke="#fecaca"/>
      <text x="520" y="330" text-anchor="middle" font-size="10" fill="#dc2626" font-weight="600">무한루프 방지</text>
      <text x="520" y="346" text-anchor="middle" font-size="9" fill="#b91c1c">iteration ≥ 15 → 강제 종료</text>
    </svg>
  </div>

  <!-- 실행 시나리오 예시 -->
  <div class="card" style="margin-top:1rem;">
    <div class="card-label">실행 시나리오 예시 — "이번 주 High 이상 사고 조회 후 알림"</div>
    <div style="margin-top:.8rem; display:flex; flex-direction:column; gap:6px;">
      <div style="display:flex;align-items:center;gap:10px;padding:8px 12px;background:#f1f5f9;border-radius:6px;font-size:13px;">
        <span style="background:#1e6fd9;color:white;padding:2px 8px;border-radius:4px;font-size:11px;white-space:nowrap;">iter 1</span>
        <span><strong>Supervisor:</strong> "DB 조회가 필요하다" → <code>query_db_tool(risk_grade="High", last_years=0)</code> 호출</span>
      </div>
      <div style="display:flex;align-items:center;gap:10px;padding:8px 12px;background:#f1f5f9;border-radius:6px;font-size:13px;">
        <span style="background:#0d9488;color:white;padding:2px 8px;border-radius:4px;font-size:11px;white-space:nowrap;">Tool</span>
        <span>DB에서 High/Critical 사고 5건 반환 → AgentState.results에 저장</span>
      </div>
      <div style="display:flex;align-items:center;gap:10px;padding:8px 12px;background:#f1f5f9;border-radius:6px;font-size:13px;">
        <span style="background:#1e6fd9;color:white;padding:2px 8px;border-radius:4px;font-size:11px;white-space:nowrap;">iter 2</span>
        <span><strong>Supervisor:</strong> "결과 확인 — 알림 발송 필요" → <code>notify_tool(risk_grade="High", message="...")</code> 호출</span>
      </div>
      <div style="display:flex;align-items:center;gap:10px;padding:8px 12px;background:#f1f5f9;border-radius:6px;font-size:13px;">
        <span style="background:#0d9488;color:white;padding:2px 8px;border-radius:4px;font-size:11px;white-space:nowrap;">Tool</span>
        <span>이메일/로그 채널 알림 발송 완료</span>
      </div>
      <div style="display:flex;align-items:center;gap:10px;padding:8px 12px;background:#dcfce7;border-radius:6px;font-size:13px;border:1px solid #86efac;">
        <span style="background:#16a34a;color:white;padding:2px 8px;border-radius:4px;font-size:11px;white-space:nowrap;">iter 3</span>
        <span><strong>Supervisor:</strong> "완료: High 이상 사고 5건 조회 및 담당자 알림 발송 완료" → END</span>
      </div>
    </div>
  </div>
</div>

<hr class="section-divider">


<!-- ══════════════════════════════════════════════
     SECTION 4. ML 예측 모델
═══════════════════════════════════════════════ -->
<div class="section" id="sec-ml">
  <div class="section-header">
    <div class="section-num num-green">04</div>
    <div class="section-title-block">
      <h2>ML 예측 모델 — 사고 예측과 위험도 분류</h2>
      <span class="tech-tag">scikit-learn · IsolationForest · LinearRegression · RandomForest · EFI</span>
    </div>
  </div>

  <div class="highlight hl-navy">
    <strong>한 줄 정의:</strong> 축적된 사고 이력 데이터로부터 패턴을 학습해 미래의 사고 발생 가능성을 예측하고, 개별 사고의 위험 등급을 자동 분류합니다.
  </div>

  <!-- ML 2개 축 설명 -->
  <div class="grid-2" style="margin:1rem 0;">
    <div class="card" style="border-top:3px solid var(--blue);">
      <div class="card-label" style="color:var(--blue);">축 1 — 시계열 예측 (월별 사고 발생 추이)</div>
      <p style="font-size:13px; color:var(--text-muted); margin:.5rem 0;">과거 월별 사고 건수 데이터를 학습해 <strong>향후 1~24개월의 사고 발생 건수</strong>를 예측합니다. 4가지 모델을 제공해 현황에 맞게 선택할 수 있습니다.</p>
      <div style="display:flex;gap:4px;flex-wrap:wrap;margin-top:.5rem;">
        <span class="badge badge-blue">선형 회귀</span>
        <span class="badge badge-blue">2차 다항 회귀</span>
        <span class="badge badge-blue">이동평균 3M</span>
        <span class="badge badge-blue">지수평활</span>
      </div>
    </div>
    <div class="card" style="border-top:3px solid var(--red);">
      <div class="card-label" style="color:var(--red);">축 2 — 위험도 점수 산정 (EFI 모델)</div>
      <p style="font-size:13px; color:var(--text-muted); margin:.5rem 0;">개별 사고의 사망자·부상자·피해액·지연시간을 <strong>등가사망지수(EFI)</strong> 기반으로 0~100점으로 환산, Critical/High/Medium/Low 4등급 분류합니다.</p>
      <div style="display:flex;gap:4px;flex-wrap:wrap;margin-top:.5rem;">
        <span class="badge badge-red">Critical ≥ 80</span>
        <span class="badge badge-amber">High ≥ 60</span>
        <span class="badge badge-yellow">Medium ≥ 25</span>
        <span class="badge badge-green">Low &lt; 25</span>
      </div>
    </div>
  </div>

  <!-- 시계열 예측 차트 -->
  <div class="diagram-box" style="margin:1rem 0;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem;flex-wrap:wrap;gap:.5rem;">
      <div class="card-label" style="margin:0;">월별 사고 발생 예측 — 4가지 모델 비교</div>
      <div class="model-tabs" style="border-bottom:none; margin:0;">
        <button class="model-tab active" onclick="switchModel(this,'linear')">선형 회귀</button>
        <button class="model-tab" onclick="switchModel(this,'poly')">2차 다항</button>
        <button class="model-tab" onclick="switchModel(this,'ma')">이동평균</button>
        <button class="model-tab" onclick="switchModel(this,'exp')">지수평활</button>
      </div>
    </div>
    <div style="position:relative;height:280px;">
      <canvas id="forecastChart"></canvas>
    </div>
    <div id="model-desc" style="margin-top:.8rem;padding:.6rem 1rem;background:var(--gray-lt);border-radius:6px;font-size:12px;color:var(--text-muted);"></div>
  </div>

  <!-- EFI 위험도 공식 -->
  <div class="card" style="margin-top:1.5rem;">
    <div class="card-label">등가사망지수(EFI) 기반 위험도 산정 공식</div>
    <div class="formula-block" style="margin-top:.8rem;">
<span class="comment"># 인명피해 점수 (최대 40점)</span>
efi = <span class="keyword">dead</span> + <span class="keyword">injured</span> / <span class="number">100.0</span>   <span class="comment"># 부상자 100명 = 사망자 1명</span>
score = <span class="func">min</span>(efi × <span class="number">20</span>, <span class="number">40</span>)

<span class="comment"># 물적 피해 (최대 20점), 운행 지연 (최대 15점)</span>
score += <span class="func">min</span>(damage / <span class="number">50</span>, <span class="number">20</span>)     <span class="comment"># 단위: 백만원</span>
score += <span class="func">min</span>(delay / <span class="number">40</span>, <span class="number">15</span>)      <span class="comment"># 단위: 분</span>

<span class="comment"># 이벤트 유형 가중치 (최대 15점)</span>
<span class="keyword">if</span> 이벤트소분류 in [탈선, 충돌, 화재, 폭발, 추락]: score += <span class="number">15</span>

<span class="comment"># ★ 철도안전 절대 기준 (Hard Constraint)</span>
<span class="keyword">if</span> dead >= <span class="number">1</span>: score = <span class="func">max</span>(score, <span class="number">60.0</span>)   <span class="comment"># 반드시 High 이상</span>
<span class="keyword">if</span> dead >= <span class="number">3</span> <span class="keyword">or</span> injured >= <span class="number">20</span>: score = <span class="func">max</span>(score, <span class="number">80.0</span>)  <span class="comment"># Critical</span>
<span class="keyword">if</span> dead >= <span class="number">5</span>: score = <span class="func">max</span>(score, <span class="number">90.0</span>)   <span class="comment"># Critical 최상위</span>
    </div>
    <div class="highlight hl-teal" style="margin-top:.8rem;">
      <strong>Hard Constraint 원칙:</strong> 사망자가 1명이라도 있으면, 다른 피해 수치가 낮더라도 <strong>반드시 High 이상(60점)으로 강제 상향</strong>됩니다.
      단순 통계적 점수만으로는 인명 사고를 과소평가할 수 있기 때문에, 철도안전 기준을 코드로 구현한 것입니다.
    </div>
  </div>

  <!-- 위험 등급 시각화 -->
  <div class="card" style="margin-top:1rem;">
    <div class="card-label">위험 등급 분류 기준 및 예시</div>
    <div style="overflow-x:auto; margin-top:.8rem;">
      <table class="compare-table">
        <tr>
          <th>등급</th><th>점수 범위</th><th>사망자 기준</th><th>부상자 기준</th><th>대응 원칙</th>
        </tr>
        <tr>
          <td><span class="badge badge-red">Critical</span></td>
          <td>80 ~ 100점</td>
          <td>3명 이상 또는 5명+ → 90점</td>
          <td>20명 이상</td>
          <td>즉시 임원 보고 + notify_tool 발동</td>
        </tr>
        <tr>
          <td><span class="badge badge-amber">High</span></td>
          <td>60 ~ 79점</td>
          <td>1명 이상 (절대 하한)</td>
          <td>10명 이상 or 대형 피해</td>
          <td>안전관리팀 즉시 알림</td>
        </tr>
        <tr>
          <td><span class="badge badge-yellow">Medium</span></td>
          <td>25 ~ 59점</td>
          <td>0명</td>
          <td>1~9명 또는 고비용 손실</td>
          <td>정기 보고 + 예방 계획 수립</td>
        </tr>
        <tr>
          <td><span class="badge badge-green">Low</span></td>
          <td>0 ~ 24점</td>
          <td>0명</td>
          <td>0명 (장애류, 경미한 지연)</td>
          <td>데이터 축적 + 통계 분석</td>
        </tr>
      </table>
    </div>
  </div>

  <!-- IsolationForest -->
  <div class="card" style="margin-top:1rem; border-top:3px solid #7c3aed;">
    <div class="card-label" style="color:#7c3aed;">추가 — IsolationForest 이상 탐지</div>
    <div class="grid-2" style="margin-top:.8rem;">
      <div>
        <p style="font-size:13px; color:var(--text-muted); line-height:1.7;">
          <code>IsolationForest</code>는 정상 사고 패턴에서 크게 벗어난 <strong>"비정상적으로 심각한 사고"를 자동 탐지</strong>하는 비지도학습 모델입니다.
          기존 위험도 점수가 모든 지표를 선형으로 합산한다면, IsolationForest는
          여러 변수의 조합이 평소와 얼마나 다른지를 기준으로 판단합니다.
        </p>
        <div class="highlight hl-teal" style="margin-top:.5rem; font-size:13px;">
          예: 사망자 없는 탈선이라도 피해액이 극도로 크고 지연 시간이 이례적으로 길면 → 이상 탐지
        </div>
      </div>
      <div>
        <svg viewBox="0 0 280 160" width="100%">
          <!-- 정상 클러스터 -->
          <ellipse cx="120" cy="100" rx="70" ry="45" fill="#dbeafe" stroke="#93c5fd" stroke-width="1"/>
          <text x="120" y="96" text-anchor="middle" font-size="10" fill="#1e40af" font-weight="600">정상 사고 패턴</text>
          <text x="120" y="110" text-anchor="middle" font-size="9" fill="#3b82f6">대부분의 사고</text>
          <!-- 점들 -->
          <circle cx="100" cy="95" r="3" fill="#3b82f6" opacity=".7"/>
          <circle cx="125" cy="85" r="3" fill="#3b82f6" opacity=".7"/>
          <circle cx="115" cy="110" r="3" fill="#3b82f6" opacity=".7"/>
          <circle cx="140" cy="100" r="3" fill="#3b82f6" opacity=".7"/>
          <circle cx="105" cy="115" r="3" fill="#3b82f6" opacity=".7"/>
          <circle cx="130" cy="90" r="3" fill="#3b82f6" opacity=".7"/>

          <!-- 이상치 점들 -->
          <circle cx="230" cy="30" r="6" fill="#dc2626"/>
          <circle cx="240" cy="35" r="2" fill="none" stroke="#dc2626" stroke-width="1.5"/>
          <circle cx="230" cy="30" r="12" fill="none" stroke="#fca5a5" stroke-width="1" stroke-dasharray="3 2"/>
          <text x="248" y="28" font-size="10" fill="#dc2626" font-weight="600">이상탐지</text>
          <text x="248" y="40" font-size="9" fill="#ef4444">비정상 패턴</text>

          <circle cx="20" cy="140" r="5" fill="#f97316"/>
          <circle cx="20" cy="140" r="10" fill="none" stroke="#fed7aa" stroke-width="1" stroke-dasharray="3 2"/>
          <text x="30" y="138" font-size="9" fill="#c2410c">이상 의심</text>

          <!-- 분리선 설명 -->
          <text x="140" y="150" text-anchor="middle" font-size="9" fill="#64748b">클러스터 밖 고립도 = 이상 점수</text>
        </svg>
      </div>
    </div>
  </div>
</div>

<hr class="section-divider">


<!-- ══════════════════════════════════════════════
     SECTION 5. 통합 구조
═══════════════════════════════════════════════ -->
<div class="section" id="sec-integration">
  <div class="section-header">
    <div class="section-num" style="background:#f3e8ff;color:#7c3aed;">05</div>
    <div class="section-title-block">
      <h2>통합 아키텍처 — 4개 기술이 함께 작동하는 방식</h2>
      <span class="tech-tag">safety_analytics.py · railway_safety_agent.py · DuckDB</span>
    </div>
  </div>

  <div class="diagram-box">
    <svg viewBox="0 0 700 400" width="100%">
      <defs>
        <marker id="ma" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M2 1L8 5L2 9" fill="none" stroke="#475569" stroke-width="1.5"/>
        </marker>
        <marker id="ma-b" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M2 1L8 5L2 9" fill="none" stroke="#1e6fd9" stroke-width="1.5"/>
        </marker>
        <marker id="ma-t" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M2 1L8 5L2 9" fill="none" stroke="#0d9488" stroke-width="1.5"/>
        </marker>
        <marker id="ma-g" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M2 1L8 5L2 9" fill="none" stroke="#16a34a" stroke-width="1.5"/>
        </marker>
        <marker id="ma-v" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M2 1L8 5L2 9" fill="none" stroke="#7c3aed" stroke-width="1.5"/>
        </marker>
      </defs>

      <!-- 사고 발생 (입력) -->
      <rect x="10" y="160" width="90" height="60" rx="8" fill="#f1f5f9" stroke="#cbd5e1"/>
      <text x="55" y="186" text-anchor="middle" font-size="11" fill="#475569" font-weight="600">사고 발생</text>
      <text x="55" y="200" text-anchor="middle" font-size="10" fill="#64748b">조사보고서</text>
      <text x="55" y="213" text-anchor="middle" font-size="10" fill="#64748b">PDF</text>

      <!-- Ollama -->
      <rect x="130" y="130" width="110" height="90" rx="10" fill="#ccfbf1" stroke="#0d9488" stroke-width="1.5"/>
      <rect x="130" y="130" width="110" height="28" rx="10" fill="#0d9488"/>
      <text x="185" y="149" text-anchor="middle" font-size="11" fill="white" font-weight="600">① Ollama</text>
      <text x="185" y="175" text-anchor="middle" font-size="10" fill="#0f5a53">로컬 LLM</text>
      <text x="185" y="189" text-anchor="middle" font-size="10" fill="#134e4a">qwen2.5:3b</text>
      <text x="185" y="203" text-anchor="middle" font-size="9" fill="#134e4a">43필드 추출</text>
      <line x1="100" y1="190" x2="128" y2="190" stroke="#0d9488" stroke-width="1.5" marker-end="url(#ma-t)"/>

      <!-- LangChain -->
      <rect x="270" y="130" width="110" height="90" rx="10" fill="#dbeafe" stroke="#1e6fd9" stroke-width="1.5"/>
      <rect x="270" y="130" width="110" height="28" rx="10" fill="#1e6fd9"/>
      <text x="325" y="149" text-anchor="middle" font-size="11" fill="white" font-weight="600">② LangChain</text>
      <text x="325" y="175" text-anchor="middle" font-size="10" fill="#1e3a8a">메시지 관리</text>
      <text x="325" y="189" text-anchor="middle" font-size="10" fill="#1e3a8a">도구 바인딩</text>
      <text x="325" y="203" text-anchor="middle" font-size="9" fill="#3b82f6">ChatOllama 연결</text>
      <line x1="240" y1="190" x2="268" y2="190" stroke="#1e6fd9" stroke-width="1.5" marker-end="url(#ma-b)"/>

      <!-- LangGraph -->
      <rect x="410" y="130" width="110" height="90" rx="10" fill="#fff7ed" stroke="#d97706" stroke-width="1.5"/>
      <rect x="410" y="130" width="110" height="28" rx="10" fill="#d97706"/>
      <text x="465" y="149" text-anchor="middle" font-size="11" fill="white" font-weight="600">③ LangGraph</text>
      <text x="465" y="175" text-anchor="middle" font-size="10" fill="#92400e">자율 에이전트</text>
      <text x="465" y="189" text-anchor="middle" font-size="10" fill="#92400e">7개 도구 실행</text>
      <text x="465" y="203" text-anchor="middle" font-size="9" fill="#a16207">재계획 루프</text>
      <line x1="380" y1="190" x2="408" y2="190" stroke="#d97706" stroke-width="1.5" marker-end="url(#ma)"/>

      <!-- DuckDB -->
      <rect x="270" y="260" width="110" height="70" rx="10" fill="#f3e8ff" stroke="#7c3aed" stroke-width="1.5"/>
      <rect x="270" y="260" width="110" height="26" rx="10" fill="#7c3aed"/>
      <text x="325" y="277" text-anchor="middle" font-size="11" fill="white" font-weight="600">DuckDB</text>
      <text x="325" y="298" text-anchor="middle" font-size="10" fill="#4c1d95">사고 데이터</text>
      <text x="325" y="312" text-anchor="middle" font-size="9" fill="#5b21b6">위험도 포함</text>
      <line x1="325" y1="220" x2="325" y2="258" stroke="#7c3aed" stroke-width="1.5" marker-end="url(#ma-v)"/>
      <text x="338" y="245" font-size="9" fill="#7c3aed">저장</text>

      <!-- ML 모델 -->
      <rect x="410" y="260" width="110" height="70" rx="10" fill="#dcfce7" stroke="#16a34a" stroke-width="1.5"/>
      <rect x="410" y="260" width="110" height="26" rx="10" fill="#16a34a"/>
      <text x="465" y="277" text-anchor="middle" font-size="11" fill="white" font-weight="600">④ ML 모델</text>
      <text x="465" y="298" text-anchor="middle" font-size="10" fill="#14532d">EFI 위험도</text>
      <text x="465" y="312" text-anchor="middle" font-size="9" fill="#166534">시계열 예측</text>
      <line x1="465" y1="220" x2="465" y2="258" stroke="#16a34a" stroke-width="1.5" marker-end="url(#ma-g)"/>
      <text x="476" y="245" font-size="9" fill="#16a34a">분석</text>

      <!-- DB ↔ ML -->
      <line x1="380" y1="295" x2="408" y2="295" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="4 3"/>

      <!-- 결과 출력 -->
      <rect x="560" y="155" width="120" height="130" rx="10" fill="#f8fafc" stroke="#e2e8f0"/>
      <rect x="560" y="155" width="120" height="26" rx="10" fill="#374151"/>
      <text x="620" y="172" text-anchor="middle" font-size="11" fill="white" font-weight="600">결과 출력</text>
      <text x="568" y="200" font-size="10" fill="#374151">📊 대시보드 (탭1~4)</text>
      <text x="568" y="216" font-size="10" fill="#374151">🔮 미래 예측 차트</text>
      <text x="568" y="232" font-size="10" fill="#374151">🎯 Bow-Tie 분석</text>
      <text x="568" y="248" font-size="10" fill="#374151">🔔 담당자 알림</text>
      <text x="568" y="264" font-size="10" fill="#374151">📥 CSV 보고서</text>
      <line x1="520" y1="190" x2="558" y2="200" stroke="#475569" stroke-width="1.5" marker-end="url(#ma)"/>

      <!-- 타이틀 -->
      <text x="350" y="30" text-anchor="middle" font-size="14" fill="#0f172a" font-weight="700">철도안전 AI 시스템 전체 데이터 흐름</text>
      <text x="350" y="48" text-anchor="middle" font-size="11" fill="#64748b">사고조사보고서 PDF → 자동 분석 → 위험도 산정 → 예측 → 알림</text>

      <!-- 하단 범례 -->
      <rect x="10" y="358" width="14" height="8" rx="2" fill="#0d9488"/>
      <text x="28" y="367" font-size="10" fill="#475569">Ollama</text>
      <rect x="90" y="358" width="14" height="8" rx="2" fill="#1e6fd9"/>
      <text x="108" y="367" font-size="10" fill="#475569">LangChain</text>
      <rect x="190" y="358" width="14" height="8" rx="2" fill="#d97706"/>
      <text x="208" y="367" font-size="10" fill="#475569">LangGraph</text>
      <rect x="295" y="358" width="14" height="8" rx="2" fill="#16a34a"/>
      <text x="313" y="367" font-size="10" fill="#475569">ML 모델</text>
      <rect x="380" y="358" width="14" height="8" rx="2" fill="#7c3aed"/>
      <text x="398" y="367" font-size="10" fill="#475569">DuckDB</text>
      <line x1="460" y1="362" x2="480" y2="362" stroke="#94a3b8" stroke-dasharray="4 3"/>
      <text x="484" y="367" font-size="10" fill="#475569">데이터 연동</text>
    </svg>
  </div>

  <!-- 역할 요약 카드 -->
  <div class="grid-4" style="margin-top:1rem;">
    <div class="card" style="text-align:center; border-top:3px solid var(--teal);">
      <div style="font-size:1.4rem;margin-bottom:.3rem;">🤖</div>
      <div style="font-size:13px;font-weight:600;color:var(--teal);">Ollama</div>
      <div style="font-size:11px;color:var(--text-muted);margin-top:.3rem;">오프라인 LLM<br>보안 문서 처리</div>
    </div>
    <div class="card" style="text-align:center; border-top:3px solid var(--blue);">
      <div style="font-size:1.4rem;margin-bottom:.3rem;">🔗</div>
      <div style="font-size:13px;font-weight:600;color:var(--blue);">LangChain</div>
      <div style="font-size:11px;color:var(--text-muted);margin-top:.3rem;">LLM 표준 인터페이스<br>도구 연결 프레임워크</div>
    </div>
    <div class="card" style="text-align:center; border-top:3px solid var(--amber);">
      <div style="font-size:1.4rem;margin-bottom:.3rem;">🎯</div>
      <div style="font-size:13px;font-weight:600;color:var(--amber);">LangGraph</div>
      <div style="font-size:11px;color:var(--text-muted);margin-top:.3rem;">자율 판단 루프<br>멀티 스텝 실행</div>
    </div>
    <div class="card" style="text-align:center; border-top:3px solid var(--green);">
      <div style="font-size:1.4rem;margin-bottom:.3rem;">📈</div>
      <div style="font-size:13px;font-weight:600;color:var(--green);">ML 모델</div>
      <div style="font-size:11px;color:var(--text-muted);margin-top:.3rem;">EFI 위험도 산정<br>시계열 예측</div>
    </div>
  </div>
</div>

<footer>
  철도안전 AI 에이전트 기술 해설서 · 철도안전 도메인 전문가 대상 내부 자료
</footer>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
// ── NAV 활성화 ──────────────────────────────────────────────
const sections = document.querySelectorAll('.section');
const navLinks = document.querySelectorAll('nav a');
const io = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      navLinks.forEach(a => {
        a.classList.toggle('active', a.getAttribute('href') === '#' + e.target.id);
      });
    }
  });
}, { rootMargin: '-30% 0px -60% 0px' });
sections.forEach(s => io.observe(s));

// ── 시계열 예측 데이터 ─────────────────────────────────────
const labels = ['23.01','23.02','23.03','23.04','23.05','23.06',
                 '23.07','23.08','23.09','23.10','23.11','23.12',
                 '24.01','24.02','24.03','24.04','24.05','24.06'];
const hist = [14,18,12,16,22,17,19,25,21,23,28,24,20,26,18,24,29,22];
const futureLabels = ['24.07','24.08','24.09','24.10','24.11','24.12'];

const models = {
  linear: {
    fc: [24, 25, 26, 27, 28, 29],
    lo: [20, 20, 21, 21, 22, 22],
    hi: [28, 30, 31, 33, 34, 36],
    desc: '선형 회귀 (Linear Regression): 과거 추세선을 직선으로 외삽합니다. 꾸준한 증가/감소 추세에서 가장 신뢰성이 높습니다. 해석이 용이하고 데이터 수가 적어도 안정적으로 작동합니다.'
  },
  poly: {
    fc: [25, 28, 31, 35, 38, 42],
    lo: [20, 22, 24, 27, 29, 31],
    hi: [30, 34, 38, 43, 47, 53],
    desc: '2차 다항 회귀 (Polynomial Regression): 곡선 형태의 추세를 포착합니다. 사고가 특정 시점 이후 급격히 증가하는 가속 패턴을 잘 표현하지만, 장기 예측 시 과대 추정 위험이 있습니다.'
  },
  ma: {
    fc: [22, 22, 22, 22, 22, 22],
    lo: [17, 17, 17, 17, 17, 17],
    hi: [27, 27, 27, 27, 27, 27],
    desc: '이동평균 3M (Moving Average 3-Month): 최근 3개월 평균을 예측값으로 사용합니다. 단기 변동성이 큰 데이터에서 안정적인 기준선을 제공합니다. 추세 변화에는 다소 늦게 반응합니다.'
  },
  exp: {
    fc: [23, 23, 24, 24, 24, 25],
    lo: [18, 18, 18, 19, 19, 19],
    hi: [28, 28, 30, 29, 29, 31],
    desc: '지수평활 (Exponential Smoothing): 최근 데이터에 더 높은 가중치를 부여합니다. 최근 수준 변화에 빠르게 반응하므로, 사고 빈도가 최근 급변한 노선이나 기간 분석에 적합합니다.'
  }
};

let currentModel = 'linear';
let chart;

function buildDatasets(modelKey) {
  const m = models[modelKey];
  const allLabels = [...labels, ...futureLabels];
  const histData = hist.map((v,i) => ({x: labels[i], y: v}));
  const fcData = futureLabels.map((l,i) => ({x: l, y: m.fc[i]}));
  const loData = futureLabels.map((l,i) => ({x: l, y: m.lo[i]}));
  const hiData = futureLabels.map((l,i) => ({x: l, y: m.hi[i]}));
  return { allLabels, histData, fcData, loData, hiData };
}

function initChart(modelKey) {
  const ctx = document.getElementById('forecastChart').getContext('2d');
  const { allLabels, histData, fcData, loData, hiData } = buildDatasets(modelKey);

  chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: allLabels,
      datasets: [
        {
          label: '실제 사고 건수',
          data: [...hist, ...new Array(futureLabels.length).fill(null)],
          borderColor: '#1e6fd9',
          backgroundColor: 'rgba(30,111,217,0.08)',
          borderWidth: 2,
          pointRadius: 4,
          pointBackgroundColor: '#1e6fd9',
          fill: false,
          tension: 0.3,
        },
        {
          label: '예측값',
          data: [...new Array(labels.length).fill(null), ...models[modelKey].fc],
          borderColor: '#d97706',
          backgroundColor: 'rgba(217,119,6,0.08)',
          borderWidth: 2.5,
          borderDash: [6, 3],
          pointRadius: 5,
          pointBackgroundColor: '#d97706',
          fill: false,
          tension: 0.3,
        },
        {
          label: '신뢰 구간 상한 (90%)',
          data: [...new Array(labels.length).fill(null), ...models[modelKey].hi],
          borderColor: 'rgba(217,119,6,0.3)',
          backgroundColor: 'rgba(217,119,6,0.08)',
          borderWidth: 1,
          pointRadius: 0,
          fill: '+1',
          tension: 0.3,
        },
        {
          label: '신뢰 구간 하한 (90%)',
          data: [...new Array(labels.length).fill(null), ...models[modelKey].lo],
          borderColor: 'rgba(217,119,6,0.3)',
          backgroundColor: 'rgba(217,119,6,0.08)',
          borderWidth: 1,
          pointRadius: 0,
          fill: false,
          tension: 0.3,
        },
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y !== null ? ctx.parsed.y + '건' : '-'}`
          }
        },
        annotation: {
          annotations: {
            divLine: {
              type: 'line',
              xMin: labels.length - 0.5,
              xMax: labels.length - 0.5,
              borderColor: '#94a3b8',
              borderWidth: 1.5,
              borderDash: [5, 4],
              label: {
                display: true,
                content: '예측 시작',
                font: { size: 10 },
                color: '#64748b',
                position: 'start'
              }
            }
          }
        }
      },
      scales: {
        x: {
          ticks: {
            font: { size: 10 },
            maxRotation: 45,
            autoSkip: false,
          },
          grid: { color: 'rgba(0,0,0,0.04)' }
        },
        y: {
          beginAtZero: true,
          title: { display: true, text: '월별 사고 건수', font: { size: 11 } },
          ticks: { font: { size: 11 } },
          grid: { color: 'rgba(0,0,0,0.06)' }
        }
      }
    }
  });

  document.getElementById('model-desc').textContent = models[modelKey].desc;
}

function switchModel(btn, modelKey) {
  document.querySelectorAll('.model-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  currentModel = modelKey;
  chart.data.datasets[1].data = [...new Array(labels.length).fill(null), ...models[modelKey].fc];
  chart.data.datasets[2].data = [...new Array(labels.length).fill(null), ...models[modelKey].hi];
  chart.data.datasets[3].data = [...new Array(labels.length).fill(null), ...models[modelKey].lo];
  chart.update('active');
  document.getElementById('model-desc').textContent = models[modelKey].desc;
}

initChart('linear');

// ── 커스텀 범례 삽입 ────────────────────────────────────────
const legendEl = document.createElement('div');
legendEl.style.cssText = 'display:flex;gap:20px;font-size:12px;color:#475569;margin-bottom:8px;flex-wrap:wrap;';
legendEl.innerHTML = `
  <span style="display:flex;align-items:center;gap:5px;"><span style="width:18px;height:3px;background:#1e6fd9;border-radius:2px;display:inline-block"></span>실제 사고 건수</span>
  <span style="display:flex;align-items:center;gap:5px;"><span style="width:18px;height:3px;background:#d97706;border-radius:2px;display:inline-block;border-top:2px dashed #d97706"></span>예측값</span>
  <span style="display:flex;align-items:center;gap:5px;"><span style="width:18px;height:8px;background:rgba(217,119,6,0.15);border-radius:2px;display:inline-block"></span>90% 신뢰구간</span>
  <span style="display:flex;align-items:center;gap:5px;"><span style="width:18px;height:2px;background:#94a3b8;border-top:2px dashed #94a3b8;display:inline-block"></span>예측 시작선</span>
`;
const chartContainer = document.getElementById('forecastChart').parentElement;
chartContainer.parentElement.insertBefore(legendEl, chartContainer);
</script>
</body>
</html>
