# src/text_to_sql/dashboard/components.py
"""
Reusable Streamlit UI components — Phase 6.

Aesthetic: Refined dark Gulf — deep navy backgrounds,
gold accents, clean monospace data display.
Evokes UAE fintech/government dashboards.
"""

import streamlit as st


# ─────────────────────────────────────────────
# CSS INJECTION
# ─────────────────────────────────────────────

def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500&family=Cormorant+Garamond:wght@400;600;700&display=swap');

    /* ── Base — Clean Light Theme ── */
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #f5f3ef !important;
        color: #1a1a2e !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 15px !important;
    }

    [data-testid="stSidebar"] {
        background-color: #ffffff !important;
        border-right: 2px solid #e8e4dc !important;
    }

    /* ── Hide chrome ── */
    #MainMenu, footer, [data-testid="stToolbar"],
    [data-testid="stDecoration"] { display: none !important; }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        background: transparent;
        border-bottom: 2px solid #e8e4dc;
        gap: 0;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent !important;
        color: #8a8a9a !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.85rem !important;
        letter-spacing: 0.12em !important;
        text-transform: uppercase !important;
        padding: 12px 28px !important;
        border: none !important;
        border-bottom: 3px solid transparent !important;
        font-weight: 500 !important;
    }
    .stTabs [aria-selected="true"] {
        color: #b5872a !important;
        border-bottom: 3px solid #b5872a !important;
    }

    /* ── Text area ── */
    .stTextArea textarea {
        background: #ffffff !important;
        border: 2px solid #e8e4dc !important;
        border-radius: 6px !important;
        color: #1a1a2e !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 1rem !important;
        direction: auto !important;
        padding: 12px !important;
    }
    .stTextArea textarea:focus {
        border-color: #b5872a !important;
        box-shadow: 0 0 0 2px #b5872a20 !important;
    }

    /* ── Buttons ── */
    .stButton > button {
        background: #b5872a !important;
        border: none !important;
        color: #ffffff !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.88rem !important;
        letter-spacing: 0.1em !important;
        text-transform: uppercase !important;
        border-radius: 6px !important;
        padding: 12px 24px !important;
        font-weight: 500 !important;
        transition: all 0.15s ease !important;
    }
    .stButton > button:hover {
        background: #9a6f22 !important;
        box-shadow: 0 4px 12px #b5872a40 !important;
    }

    /* ── Selectbox ── */
    .stSelectbox > div > div {
        background: #ffffff !important;
        border: 2px solid #e8e4dc !important;
        border-radius: 6px !important;
        color: #1a1a2e !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.92rem !important;
    }

    /* ── Metrics ── */
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 2px solid #e8e4dc;
        border-radius: 8px;
        padding: 18px 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    [data-testid="stMetricLabel"] {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.75rem !important;
        letter-spacing: 0.15em !important;
        text-transform: uppercase !important;
        color: #8a8a9a !important;
    }
    [data-testid="stMetricValue"] {
        font-family: 'IBM Plex Mono', monospace !important;
        color: #1a1a2e !important;
        font-size: 1.6rem !important;
        font-weight: 600 !important;
    }

    /* ── Divider ── */
    hr { border-color: #e8e4dc !important; }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 4px; }
    ::-webkit-scrollbar-track { background: #f5f3ef; }
    ::-webkit-scrollbar-thumb { background: #d4cfc7; border-radius: 2px; }

    /* ── Code blocks ── */
    code, pre {
        background: #f0ede8 !important;
        color: #b5872a !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.9rem !important;
        border: 1px solid #e8e4dc !important;
        border-radius: 4px !important;
    }

    /* ── General text size boost ── */
    p, li, span, div {
        font-size: 1rem;
        line-height: 1.6;
    }
    </style>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────

def render_header():
    st.html("""
    <div style="
        border-bottom: 1px solid #e8e4dc;
        padding-bottom: 20px;
        margin-bottom: 28px;
    ">
        <div style="
            font-family:'IBM Plex Mono',monospace;
            font-size:0.75rem;
            letter-spacing:0.3em;
            color:#b5872a;
            opacity:0.7;
            margin-bottom:8px;
            text-transform:uppercase;
        ">◈ Bilingual · Arabic / English · Enterprise Grade</div>

        <div style="
            font-family:'Cormorant Garamond',serif;
            font-size:3.0rem;
            font-weight:700;
            color:#0f0f1a;
            letter-spacing:0.02em;
            line-height:1;
        ">Text-to-SQL</div>

        <div style="
            font-family:'IBM Plex Mono',monospace;
            font-size:0.85rem;
            color:#6b6b7e;
            margin-top:6px;
            letter-spacing:0.08em;
        ">SIMPLE CHAIN &nbsp;·&nbsp; CHAIN-OF-THOUGHT &nbsp;·&nbsp; REACT AGENT &nbsp;·&nbsp; SAFETY LAYER</div>
    </div>
    """)


# ─────────────────────────────────────────────
# RESULT CARD
# ─────────────────────────────────────────────

def render_result(data: dict):
    """Render full query result with SQL and response."""
    blocked  = data.get("blocked", False)
    success  = data.get("execution_success", False)
    lang     = data.get("detected_language", "en")
    response = data.get("natural_response", "")
    sql      = data.get("generated_sql", "")
    complex_ = data.get("complexity", "simple")
    retries  = data.get("retries_used", 0)

    if blocked:
        # Blocked card — amber warning
        st.html(f"""
        <div style="
            background:#fffbf0;
            border:1px solid #b5872a;
            border-left:4px solid #b5872a;
            border-radius:3px;
            padding:20px 24px;
            margin-bottom:16px;
        ">
            <div style="
                font-family:'IBM Plex Mono',monospace;
                font-size:0.81rem;
                letter-spacing:0.2em;
                color:#b5872a;
                margin-bottom:10px;
            ">⚠ BLOCKED BY SAFETY LAYER</div>
            <div style="
                font-family:'IBM Plex Mono',monospace;
                font-size:1.02rem;
                color:#b5872a;
                opacity:0.8;
            ">{response}</div>
            <div style="
                font-family:'IBM Plex Mono',monospace;
                font-size:0.78rem;
                color:#6b6b7e;
                margin-top:10px;
            ">{data.get('block_reason', '')}</div>
        </div>
        """)
        return

    if not success:
        st.html("""
        <div style="
            background:#ffffff;
            border:1px solid #ff4b6e40;
            border-radius:3px;
            padding:20px 24px;
            margin-bottom:16px;
        ">
            <div style="
                font-family:'IBM Plex Mono',monospace;
                font-size:0.81rem;
                color:#ff4b6e;
            ">✗ QUERY FAILED</div>
        </div>
        """)
        return

    # Complexity colour
    complexity_colors = {
        "simple":  "#1a6bbf",
        "medium":  "#b5872a",
        "complex": "#7c3aed",
    }
    c_color = complexity_colors.get(complex_, "#1a6bbf")

    # Language badge
    lang_label = "AR عربي" if lang == "ar" else "EN"
    rtl_style  = 'direction:rtl;text-align:right;' if lang == "ar" else ""

    st.html(f"""
    <div style="
        background:#ffffff;
        border:1px solid #e8e4dc;
        border-left:4px solid {c_color};
        border-radius:3px;
        padding:20px 24px;
        margin-bottom:16px;
    ">
        <!-- Meta row -->
        <div style="
            display:flex;
            justify-content:space-between;
            align-items:center;
            margin-bottom:14px;
        ">
            <div style="display:flex;gap:12px;align-items:center;">
                <span style="
                    font-family:'IBM Plex Mono',monospace;
                    font-size:0.75rem;
                    letter-spacing:0.18em;
                    color:{c_color};
                    text-transform:uppercase;
                ">{complex_}</span>
                <span style="
                    font-family:'IBM Plex Mono',monospace;
                    font-size:0.75rem;
                    color:#6b6b7e;
                ">|</span>
                <span style="
                    font-family:'IBM Plex Mono',monospace;
                    font-size:0.75rem;
                    color:#6b6b7e;
                ">{lang_label}</span>
                {f'<span style="font-family:IBM Plex Mono,monospace;font-size:0.75rem;color:#6b6b7e;">| {retries} retries</span>' if retries > 0 else ''}
            </div>
            <span style="
                font-family:'IBM Plex Mono',monospace;
                font-size:0.75rem;
                color:#22aa44;
            ">✓ SUCCESS</span>
        </div>

        <!-- Response -->
        <div style="
            font-family:'IBM Plex Mono',monospace;
            font-size:1.10rem;
            color:#0f0f1a;
            line-height:1.7;
            margin-bottom:16px;
            {rtl_style}
        ">{response}</div>

        <!-- SQL -->
        <div style="
            background:#f5f3ef;
            border:1px solid #e8e4dc;
            border-radius:2px;
            padding:10px 14px;
            font-family:'IBM Plex Mono',monospace;
            font-size:0.93rem;
            color:#1a6bbf;
            word-break:break-all;
            opacity:0.8;
        ">{sql}</div>
    </div>
    """)


# ─────────────────────────────────────────────
# HISTORY TABLE
# ─────────────────────────────────────────────

def render_history(history: list):
    """Compact history log, newest first."""
    if not history:
        st.html("""
        <div style="
            font-family:'IBM Plex Mono',monospace;
            font-size:0.90rem;
            color:#e8e4dc;
            text-align:center;
            padding:40px;
        ">NO HISTORY YET</div>
        """)
        return

    rows = ""
    for item in reversed(history[-30:]):
        blocked  = item.get("blocked", False)
        success  = item.get("execution_success", False)
        lang     = item.get("detected_language", "en")
        complex_ = item.get("complexity", "—")

        if blocked:
            status_color = "#b5872a"
            status_icon  = "⚠"
        elif success:
            status_color = "#22aa44"
            status_icon  = "✓"
        else:
            status_color = "#ff4b6e"
            status_icon  = "✗"

        q_preview = item.get("question", "")[:52]
        if len(item.get("question","")) > 52:
            q_preview += "…"

        rows += f"""
        <tr style="border-bottom:1px solid #f0ede8;">
            <td style="padding:7px 12px;font-family:'IBM Plex Mono',monospace;font-size:0.88rem;color:{status_color};">{status_icon}</td>
            <td style="padding:7px 12px;font-family:'IBM Plex Mono',monospace;font-size:0.88rem;color:#1a1a2e;">{q_preview}</td>
            <td style="padding:7px 12px;font-family:'IBM Plex Mono',monospace;font-size:0.81rem;color:#6b6b7e;">{complex_}</td>
            <td style="padding:7px 12px;font-family:'IBM Plex Mono',monospace;font-size:0.81rem;color:#6b6b7e;text-align:right;">{'AR' if lang == 'ar' else 'EN'}</td>
        </tr>
        """

    st.html(f"""
    <div style="background:#ffffff;border:1px solid #e8e4dc;border-radius:3px;overflow:hidden;">
    <table style="width:100%;border-collapse:collapse;">
        <thead>
            <tr style="border-bottom:1px solid #e8e4dc;">
                <th style="padding:8px 12px;font-family:'IBM Plex Mono',monospace;font-size:0.72rem;letter-spacing:0.18em;color:#6b6b7e;text-align:left;">ST</th>
                <th style="padding:8px 12px;font-family:'IBM Plex Mono',monospace;font-size:0.72rem;letter-spacing:0.18em;color:#6b6b7e;text-align:left;">QUESTION</th>
                <th style="padding:8px 12px;font-family:'IBM Plex Mono',monospace;font-size:0.72rem;letter-spacing:0.18em;color:#6b6b7e;text-align:left;">COMPLEXITY</th>
                <th style="padding:8px 12px;font-family:'IBM Plex Mono',monospace;font-size:0.72rem;letter-spacing:0.18em;color:#6b6b7e;text-align:right;">LANG</th>
            </tr>
        </thead>
        <tbody>{rows}</tbody>
    </table>
    </div>
    """)


# ─────────────────────────────────────────────
# SCHEMA BROWSER
# ─────────────────────────────────────────────

def render_schema(schema_data: dict):
    """Visual database schema browser."""
    if not schema_data:
        return

    tables     = schema_data.get("tables", [])
    total_rows = schema_data.get("total_rows", 0)

    st.html(f"""
    <div style="
        font-family:'IBM Plex Mono',monospace;
        font-size:0.75rem;
        letter-spacing:0.2em;
        color:#6b6b7e;
        margin-bottom:16px;
    ">◈ {len(tables)} TABLES &nbsp;·&nbsp; {total_rows:,} TOTAL ROWS</div>
    """)

    for table in tables:
        name    = table["name"]
        count   = table["row_count"]
        cols    = table["columns"]
        desc    = table.get("description", "")

        # Row bar — proportional to largest table
        max_rows   = max(t["row_count"] for t in tables) or 1
        bar_pct    = int((count / max_rows) * 100)

        col_pills  = " &nbsp;".join(
            f'<span style="color:#1a6bbf;opacity:0.8;">{c}</span>'
            for c in cols
        )

        st.html(f"""
        <div style="
            background:#ffffff;
            border:1px solid #e8e4dc;
            border-radius:3px;
            padding:14px 18px;
            margin-bottom:10px;
        ">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <div style="
                    font-family:'IBM Plex Mono',monospace;
                    font-size:1.02rem;
                    color:#b5872a;
                    font-weight:500;
                ">{name}</div>
                <div style="
                    font-family:'IBM Plex Mono',monospace;
                    font-size:0.81rem;
                    color:#6b6b7e;
                ">{count:,} rows</div>
            </div>

            <!-- Row bar -->
            <div style="background:#f0ede8;height:3px;border-radius:2px;margin-bottom:10px;">
                <div style="width:{bar_pct}%;height:3px;background:#b5872a;border-radius:2px;opacity:0.6;"></div>
            </div>

            <!-- Description -->
            <div style="
                font-family:'IBM Plex Mono',monospace;
                font-size:0.80rem;
                color:#6b6b7e;
                margin-bottom:8px;
                line-height:1.5;
            ">{desc[:120] if desc else ''}</div>

            <!-- Columns -->
            <div style="
                font-family:'IBM Plex Mono',monospace;
                font-size:0.80rem;
                line-height:1.8;
            ">{col_pills}</div>
        </div>
        """)


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────

def render_sidebar(api_status: dict | None, session_stats: dict):
    """Sidebar with system status and session counters."""

    st.html("""
    <div style="
        font-family:'IBM Plex Mono',monospace;
        font-size:0.72rem;
        letter-spacing:0.22em;
        color:#6b6b7e;
        text-transform:uppercase;
        margin-bottom:10px;
    ">◈ SYSTEM STATUS</div>
    """)

    if api_status:
        status     = api_status.get("status", "unknown")
        s_color    = "#22aa44" if status == "ok" else "#b5872a"
        chain_ok   = api_status.get("chain_loaded", False)
        guard_ok   = api_status.get("guard_active", False)
        db_ok      = api_status.get("db_connected", False)
        model      = api_status.get("model", "—")

        st.html(f"""
        <div style="
            background:#ffffff;
            border:1px solid #e8e4dc;
            border-radius:3px;
            padding:12px 14px;
            margin-bottom:16px;
        ">
            <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                <span style="font-family:'IBM Plex Mono',monospace;font-size:0.85rem;color:#1a1a2e;">API</span>
                <span style="font-family:'IBM Plex Mono',monospace;font-size:0.78rem;color:{s_color};">● {status.upper()}</span>
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                <span style="font-family:'IBM Plex Mono',monospace;font-size:0.78rem;color:#6b6b7e;">LLM Chain</span>
                <span style="font-family:'IBM Plex Mono',monospace;font-size:0.78rem;color:{'#22aa44' if chain_ok else '#ff4b6e'};">{'ON' if chain_ok else 'OFF'}</span>
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                <span style="font-family:'IBM Plex Mono',monospace;font-size:0.78rem;color:#6b6b7e;">SQL Guard</span>
                <span style="font-family:'IBM Plex Mono',monospace;font-size:0.78rem;color:{'#22aa44' if guard_ok else '#ff4b6e'};">{'ON' if guard_ok else 'OFF'}</span>
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                <span style="font-family:'IBM Plex Mono',monospace;font-size:0.78rem;color:#6b6b7e;">Database</span>
                <span style="font-family:'IBM Plex Mono',monospace;font-size:0.78rem;color:{'#22aa44' if db_ok else '#ff4b6e'};">{'ON' if db_ok else 'OFF'}</span>
            </div>
            <div style="border-top:1px solid #e8e4dc;padding-top:8px;font-family:'IBM Plex Mono',monospace;font-size:0.75rem;color:#6b6b7e;">
                {model}
            </div>
        </div>
        """)
    else:
        st.html("""
        <div style="
            background:#fffbf0;
            border:1px solid #b5872a40;
            border-radius:3px;
            padding:12px 14px;
            font-family:'IBM Plex Mono',monospace;
            font-size:0.85rem;
            color:#b5872a;
            margin-bottom:16px;
        ">● API OFFLINE<br>
        <span style="color:#6b6b7e;font-size:0.75rem;">
        uvicorn src.text_to_sql.api.main:app --port 8000
        </span>
        </div>
        """)

    # Session stats
    st.html("""
    <div style="
        font-family:'IBM Plex Mono',monospace;
        font-size:0.72rem;
        letter-spacing:0.22em;
        color:#6b6b7e;
        text-transform:uppercase;
        margin-bottom:10px;
    ">◈ SESSION</div>
    """)

    total   = session_stats.get("total", 0)
    success = session_stats.get("success", 0)
    blocked = session_stats.get("blocked", 0)
    block_r = f"{blocked/total*100:.0f}%" if total > 0 else "—"

    st.html(f"""
    <div style="
        background:#ffffff;
        border:1px solid #e8e4dc;
        border-radius:3px;
        padding:12px 14px;
        margin-bottom:16px;
    ">
        <div style="display:flex;justify-content:space-between;margin-bottom:5px;">
            <span style="font-family:'IBM Plex Mono',monospace;font-size:0.78rem;color:#6b6b7e;">Queries</span>
            <span style="font-family:'IBM Plex Mono',monospace;font-size:0.88rem;color:#1a1a2e;">{total}</span>
        </div>
        <div style="display:flex;justify-content:space-between;margin-bottom:5px;">
            <span style="font-family:'IBM Plex Mono',monospace;font-size:0.78rem;color:#6b6b7e;">Success</span>
            <span style="font-family:'IBM Plex Mono',monospace;font-size:0.88rem;color:#22aa44;">{success}</span>
        </div>
        <div style="display:flex;justify-content:space-between;margin-bottom:5px;">
            <span style="font-family:'IBM Plex Mono',monospace;font-size:0.78rem;color:#6b6b7e;">Blocked</span>
            <span style="font-family:'IBM Plex Mono',monospace;font-size:0.88rem;color:#b5872a;">{blocked}</span>
        </div>
        <div style="border-top:1px solid #e8e4dc;padding-top:8px;display:flex;justify-content:space-between;">
            <span style="font-family:'IBM Plex Mono',monospace;font-size:0.78rem;color:#6b6b7e;">Block Rate</span>
            <span style="font-family:'IBM Plex Mono',monospace;font-size:0.88rem;color:#b5872a;">{block_r}</span>
        </div>
    </div>
    """)


# ─────────────────────────────────────────────
# EXAMPLE PROMPTS
# ─────────────────────────────────────────────

EXAMPLE_PROMPTS = {
    "Simple — Customers":    "How many customers are in the database?",
    "Simple — Arabic":       "كم عدد المنتجات في قاعدة البيانات؟",
    "Medium — Top Revenue":  "What are the top 5 customers by total line total?",
    "Medium — By Channel":   "Show total sales broken down by channel",
    "Complex — vs Budget":   "Compare total sales versus 2017 budget for each product",
    "Complex — Arabic":      "قارن المبيعات الفعلية مقابل ميزانية 2017 لكل منتج",
    "Complex — % Revenue":   "What percentage of total revenue came from each channel?",
}