# src/text_to_sql/dashboard/app.py
"""
Streamlit Dashboard — Phase 6.

Bilingual Arabic-English Text-to-SQL Dashboard.
Connects to the FastAPI backend at localhost:8000.

Run (API must be running first):
    streamlit run src/text_to_sql/dashboard/app.py

Tabs:
    QUERY    — interactive query interface
    BATCH    — multi-question analysis
    HISTORY  — session query log
    SCHEMA   — database schema browser
    ABOUT    — system info
"""

import sys
sys.path.append(".")

import requests
import streamlit as st

from src.text_to_sql.dashboard.components import (
    inject_css,
    render_header,
    render_result,
    render_history,
    render_schema,
    render_sidebar,
    EXAMPLE_PROMPTS,
)

API_BASE = "http://localhost:8000"

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────

st.set_page_config(
    page_title  = "Text-to-SQL",
    page_icon   = "◈",
    layout      = "wide",
    initial_sidebar_state = "expanded",
)


# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────

def init_state():
    defaults = {
        "history":     [],
        "last_result": None,
        "api_status":  None,
        "schema_data": None,
        "stats":       {"total": 0, "success": 0, "blocked": 0},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ─────────────────────────────────────────────
# API HELPERS
# ─────────────────────────────────────────────

@st.cache_data(ttl=15)
def fetch_health() -> dict | None:
    try:
        r = requests.get(f"{API_BASE}/health", timeout=2)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


@st.cache_data(ttl=300)
def fetch_schema() -> dict | None:
    try:
        r = requests.get(f"{API_BASE}/schema", timeout=5)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def call_query(question: str) -> dict | None:
    try:
        r = requests.post(
            f"{API_BASE}/query",
            json    = {"question": question},
            timeout = 120,
        )
        if r.status_code == 200:
            return r.json()
        st.error(f"API error {r.status_code}: {r.text[:200]}")
        return None
    except requests.ConnectionError:
        st.error("❌ Cannot connect to API. Run: `uvicorn src.text_to_sql.api.main:app --port 8000`")
        return None
    except requests.Timeout:
        st.error("⏱ Request timed out — complex queries can take up to 60 seconds.")
        return None
    except Exception as e:
        st.error(f"Request failed: {e}")
        return None


def call_batch(questions: list) -> dict | None:
    try:
        r = requests.post(
            f"{API_BASE}/query/batch",
            json    = {"questions": questions},
            timeout = 300,
        )
        if r.status_code == 200:
            return r.json()
        st.error(f"API error {r.status_code}: {r.text[:200]}")
        return None
    except requests.ConnectionError:
        st.error("❌ Cannot connect to API.")
        return None
    except Exception as e:
        st.error(f"Request failed: {e}")
        return None


def update_stats(result: dict):
    st.session_state.stats["total"] += 1
    if result.get("blocked"):
        st.session_state.stats["blocked"] += 1
    elif result.get("execution_success"):
        st.session_state.stats["success"] += 1


def add_to_history(result: dict):
    st.session_state.history.append(result)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    init_state()
    inject_css()

    # ── Sidebar ───────────────────────────────
    with st.sidebar:
        st.markdown("<br>", unsafe_allow_html=True)
        api_status = fetch_health()
        st.session_state.api_status = api_status
        render_sidebar(api_status, st.session_state.stats)

        st.markdown("---")
        if st.button("CLEAR SESSION"):
            st.session_state.history     = []
            st.session_state.last_result = None
            st.session_state.stats       = {"total": 0, "success": 0, "blocked": 0}
            fetch_health.clear()
            fetch_schema.clear()
            st.rerun()

        st.markdown("""
        <div style="
            font-family:'IBM Plex Mono',monospace;
            font-size:0.55rem;
            letter-spacing:0.12em;
            color:#1a2235;
            text-align:center;
            padding-top:8px;
        ">TEXT-TO-SQL · v1.0</div>
        """, unsafe_allow_html=True)

    # ── Header ────────────────────────────────
    render_header()

    # ── Tabs ──────────────────────────────────
    tab_query, tab_batch, tab_history, tab_schema, tab_about = st.tabs([
        "QUERY", "BATCH", "HISTORY", "SCHEMA", "ABOUT"
    ])

    # ══════════════════════════════════════════
    # TAB 1 — QUERY
    # ══════════════════════════════════════════
    with tab_query:
        col_left, col_right = st.columns([1, 1], gap="large")

        with col_left:
            # Example selector
            st.markdown("""
            <div style="font-family:'IBM Plex Mono',monospace;font-size:0.6rem;
                letter-spacing:0.18em;color:#3d5a80;margin-bottom:8px;">
            ◈ LOAD EXAMPLE</div>
            """, unsafe_allow_html=True)

            example = st.selectbox(
                label            = "example",
                options          = ["— select —"] + list(EXAMPLE_PROMPTS.keys()),
                label_visibility = "collapsed",
            )

            default_text = (
                EXAMPLE_PROMPTS[example]
                if example != "— select —"
                else ""
            )

            st.markdown("""
            <div style="font-family:'IBM Plex Mono',monospace;font-size:0.6rem;
                letter-spacing:0.18em;color:#3d5a80;margin-top:16px;margin-bottom:8px;">
            ◈ QUESTION  (English or Arabic)</div>
            """, unsafe_allow_html=True)

            question = st.text_area(
                label            = "question",
                value            = default_text,
                height           = 120,
                placeholder      = "Ask in English or Arabic…",
                label_visibility = "collapsed",
            )

            char_count = len(question)
            st.markdown(f"""
            <div style="font-family:'IBM Plex Mono',monospace;font-size:0.58rem;
                color:#1a2235;text-align:right;margin-top:-6px;margin-bottom:10px;">
            {char_count}/2000</div>
            """, unsafe_allow_html=True)

            submit = st.button(
                "EXECUTE →",
                use_container_width = True,
                disabled            = not question.strip(),
            )

        with col_right:
            if submit and question.strip():
                with st.spinner(""):
                    result = call_query(question.strip())
                if result:
                    st.session_state.last_result = result
                    update_stats(result)
                    add_to_history(result)
                    fetch_health.clear()

            if st.session_state.last_result:
                render_result(st.session_state.last_result)
            else:
                st.markdown("""
                <div style="
                    height:260px;
                    display:flex;
                    align-items:center;
                    justify-content:center;
                    border:1px dashed #1a2235;
                    border-radius:3px;
                ">
                    <div style="text-align:center;">
                        <div style="font-size:2rem;opacity:0.08;margin-bottom:10px;">◈</div>
                        <div style="font-family:'IBM Plex Mono',monospace;
                            font-size:0.65rem;color:#1a2235;letter-spacing:0.1em;">
                        AWAITING QUERY</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # ══════════════════════════════════════════
    # TAB 2 — BATCH
    # ══════════════════════════════════════════
    with tab_batch:
        st.markdown("""
        <div style="font-family:'IBM Plex Mono',monospace;font-size:0.6rem;
            letter-spacing:0.18em;color:#3d5a80;margin-bottom:8px;">
        ◈ BATCH INPUT — one question per line (max 20)</div>
        """, unsafe_allow_html=True)

        default_batch = "\n".join([
            "How many customers are in the database?",
            "كم عدد المنتجات في قاعدة البيانات؟",
            "What are the top 5 customers by total sales?",
            "Show total sales broken down by channel",
            "What is the total 2017 budget across all products?",
        ])

        batch_input = st.text_area(
            label            = "batch_input",
            value            = default_batch,
            height           = 160,
            label_visibility = "collapsed",
        )

        run_batch = st.button("RUN BATCH →")

        if run_batch:
            lines = [l.strip() for l in batch_input.split("\n") if l.strip()]
            if not lines:
                st.warning("Enter at least one question.")
            elif len(lines) > 20:
                st.error("Maximum 20 questions per batch.")
            else:
                with st.spinner(f"Processing {len(lines)} questions…"):
                    batch_result = call_batch(lines)

                if batch_result:
                    # Summary row
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("TOTAL",   batch_result["total"])
                    with col2:
                        st.metric("SUCCESS", batch_result["success_count"])
                    with col3:
                        st.metric("BLOCKED", batch_result["blocked_count"])
                    with col4:
                        summary = batch_result.get("summary", {})
                        complex_count = summary.get("complex", 0)
                        st.metric("COMPLEX", complex_count)

                    st.markdown("<br>", unsafe_allow_html=True)

                    # Individual results
                    for r in batch_result["results"]:
                        render_result(r)
                        # Add question label above each result
                        add_to_history(r)
                        update_stats(r)

    # ══════════════════════════════════════════
    # TAB 3 — HISTORY
    # ══════════════════════════════════════════
    with tab_history:
        col_h1, col_h2 = st.columns([4, 1])
        with col_h1:
            st.markdown("""
            <div style="font-family:'IBM Plex Mono',monospace;font-size:0.6rem;
                letter-spacing:0.18em;color:#3d5a80;margin-bottom:12px;">
            ◈ SESSION QUERY LOG (last 30)</div>
            """, unsafe_allow_html=True)
        with col_h2:
            if st.button("CLEAR"):
                st.session_state.history = []
                st.session_state.stats   = {"total": 0, "success": 0, "blocked": 0}
                st.rerun()

        render_history(st.session_state.history)

    # ══════════════════════════════════════════
    # TAB 4 — SCHEMA
    # ══════════════════════════════════════════
    with tab_schema:
        schema = fetch_schema()
        if schema:
            render_schema(schema)
        else:
            st.markdown("""
            <div style="font-family:'IBM Plex Mono',monospace;font-size:0.72rem;
                color:#c9a84c;padding:20px;">
            Could not load schema — is the API running?</div>
            """, unsafe_allow_html=True)

    # ══════════════════════════════════════════
    # TAB 5 — ABOUT
    # ══════════════════════════════════════════
    with tab_about:
        col_a, col_b = st.columns([1, 1], gap="large")

        with col_a:
            st.markdown("""
            <div style="font-family:'IBM Plex Mono',monospace;font-size:0.6rem;
                letter-spacing:0.18em;color:#3d5a80;margin-bottom:12px;">
            ◈ ARCHITECTURE</div>
            """, unsafe_allow_html=True)

            layers = [
                ("LAYER 1 · RULE ROUTER",
                 "Complexity classifier — routes simple/medium/complex queries to the right strategy. Zero LLM cost.",
                 "#4a9eff"),
                ("LAYER 2 · SIMPLE CHAIN",
                 "Direct single-step SQL generation. 1 LLM call. Used for single-table lookups and basic aggregations.",
                 "#4a9eff"),
                ("LAYER 3 · COT CHAIN",
                 "Chain-of-thought reasoning before SQL generation. Used for joins, GROUP BY, rankings. Fewer errors.",
                 "#c9a84c"),
                ("LAYER 4 · REACT AGENT",
                 "LangGraph ReAct agent with 4 tools (list_tables, get_schema, run_query, check_query). Multi-step reasoning for complex cross-table analysis.",
                 "#b06aff"),
                ("LAYER 5 · SQL GUARD",
                 "Prompt injection detection. Write-operation blocking. Row limit enforcement. Full JSONL audit trail.",
                 "#22aa44"),
            ]

            for title, desc, color in layers:
                st.markdown(f"""
                <div style="
                    background:#080c14;
                    border:1px solid #1a2235;
                    border-left:3px solid {color};
                    border-radius:3px;
                    padding:12px 16px;
                    margin-bottom:10px;
                ">
                    <div style="font-family:'IBM Plex Mono',monospace;font-size:0.68rem;
                        color:{color};margin-bottom:5px;">{title}</div>
                    <div style="font-family:'IBM Plex Mono',monospace;font-size:0.62rem;
                        color:#3d5a80;line-height:1.5;">{desc}</div>
                </div>
                """, unsafe_allow_html=True)

        with col_b:
            st.markdown("""
            <div style="font-family:'IBM Plex Mono',monospace;font-size:0.6rem;
                letter-spacing:0.18em;color:#3d5a80;margin-bottom:12px;">
            ◈ BENCHMARK RESULTS</div>
            """, unsafe_allow_html=True)

            metrics = [
                ("Overall Accuracy",       "97%",    "#22aa44"),
                ("Simple Queries",         "100%",   "#22aa44"),
                ("Medium Queries",         "100%",   "#22aa44"),
                ("Complex Queries",        "88%",    "#c9a84c"),
                ("English Accuracy",       "96.5%",  "#22aa44"),
                ("Arabic Accuracy",        "100%",   "#22aa44"),
                ("ML Classifier F1",       "0.884",  "#4a9eff"),
                ("Injection Patterns",     "16",     "#4a9eff"),
                ("Write Ops Blocked",      "8 types","#4a9eff"),
            ]

            for label, value, color in metrics:
                st.markdown(f"""
                <div style="
                    display:flex;
                    justify-content:space-between;
                    padding:8px 0;
                    border-bottom:1px solid #0d1220;
                ">
                    <span style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;color:#3d5a80;">{label}</span>
                    <span style="font-family:'IBM Plex Mono',monospace;font-size:0.68rem;color:{color};font-weight:500;">{value}</span>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("""
            <div style="font-family:'IBM Plex Mono',monospace;font-size:0.6rem;
                letter-spacing:0.18em;color:#3d5a80;margin-top:20px;margin-bottom:12px;">
            ◈ API ENDPOINTS</div>
            """, unsafe_allow_html=True)

            endpoints = [
                ("POST", "/query",       "Single question"),
                ("POST", "/query/batch", "Batch (max 20)"),
                ("GET",  "/schema",      "Database schema"),
                ("GET",  "/health",      "System health"),
                ("GET",  "/audit/stats", "Compliance stats"),
                ("GET",  "/docs",        "Swagger UI"),
            ]

            for method, path, desc in endpoints:
                color = "#4a9eff" if method == "GET" else "#c9a84c"
                st.markdown(f"""
                <div style="display:flex;gap:12px;padding:6px 0;border-bottom:1px solid #0d1220;">
                    <span style="font-family:'IBM Plex Mono',monospace;font-size:0.6rem;color:{color};min-width:36px;">{method}</span>
                    <span style="font-family:'IBM Plex Mono',monospace;font-size:0.62rem;color:#c8cfd8;min-width:130px;">{path}</span>
                    <span style="font-family:'IBM Plex Mono',monospace;font-size:0.6rem;color:#3d5a80;">{desc}</span>
                </div>
                """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()