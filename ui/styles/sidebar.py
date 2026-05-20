SIDEBAR_CSS = """
<style>
/* ── 사이드바 배경 ─────────────────────────────── */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div:first-child {
    background-color: #13131f !important;
}

/* ── 사이드바 텍스트 색상 ───────────────────────── */
section[data-testid="stSidebar"] * {
    color: #ffffff;
}

section[data-testid="stSidebar"] .stCaption {
    color: rgba(255,255,255,0.6) !important;
}

/* ── 버튼 기본 (비활성) + focus/active/focus-visible 일괄 처리 ── */
.stSidebar .stButton > button,
.stSidebar .stButton > button:focus,
.stSidebar .stButton > button:active,
.stSidebar .stButton > button:focus-visible {
    width: 100%;
    background: transparent !important;
    color: #ffffff !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    text-align: left;
    padding: 11px 16px;
    border-radius: 8px;
    font-size: 0.92rem;
    letter-spacing: 0.01em;
    margin-bottom: 3px;
    outline: none !important;
    box-shadow: none !important;
    transition: background 0.15s;
}

/* ── hover ─────────────────────────────────────── */
.stSidebar .stButton > button:hover {
    background: rgba(255,255,255,0.1) !important;
    color: #ffffff !important;
    border-color: rgba(255,255,255,0.15) !important;
}

/* ── 활성(primary) 버튼 ─────────────────────────── */
.stSidebar .stButton > button[kind="primary"],
.stSidebar .stButton > button[kind="primary"]:focus,
.stSidebar .stButton > button[kind="primary"]:active,
.stSidebar .stButton > button[kind="primary"]:focus-visible {
    background: rgba(255,255,255,0.18) !important;
    color: #ffffff !important;
    font-weight: 600 !important;
    border-color: rgba(255,255,255,0.15) !important;
    outline: none !important;
    box-shadow: none !important;
}

.stSidebar .stButton > button[kind="primary"]:hover {
    background: rgba(255,255,255,0.25) !important;
}
</style>
"""
