ANALYSIS_CSS = """
<style>
/* ── 탭 리스트 ──────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 2px;
    background-color: transparent;
    border-bottom: 1px solid rgba(255,255,255,0.08);
}

/* ── 탭 기본 ────────────────────────────────────── */
.stTabs [data-baseweb="tab"] {
    background-color: transparent;
    border-radius: 8px 8px 0 0;
    color: rgba(200,210,240,0.6);
    padding: 8px 22px;
    font-size: 0.92rem;
    border: none;
    transition: color 0.15s, background 0.15s;
}

/* ── 활성 탭 ────────────────────────────────────── */
.stTabs [aria-selected="true"] {
    background-color: rgba(108, 142, 245, 0.12) !important;
    color: #7c9ef5 !important;
    font-weight: 600 !important;
    border-bottom: 2px solid #7c9ef5 !important;
}

/* ── 탭 hover ───────────────────────────────────── */
.stTabs [data-baseweb="tab"]:hover {
    color: #c8d4ff !important;
    background-color: rgba(255,255,255,0.05) !important;
}

/* ── 탭 패널 상단 여백 ──────────────────────────── */
.stTabs [data-baseweb="tab-panel"] {
    padding-top: 1rem;
}

/* ── dataframe 헤더 배경 (다크) ─────────────────── */
.stDataFrame thead tr th,
.stDataFrame [data-testid="glideDataEditor"] .gdg-header-cell,
[data-testid="stDataFrame"] .dvn-scroll-inner .header-row {
    background-color: #1a1a2e !important;
    color: #c8d0e8 !important;
    font-weight: 600 !important;
}

/* ── dataframe 테두리 정리 ──────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: 8px;
    overflow: hidden;
}
</style>
"""
