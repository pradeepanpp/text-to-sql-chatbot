"""
Streamlit dashboard. Talks to the API (API_BASE, default http://localhost:8000).

Run (start the API first):
    streamlit run src/text_to_sql/dashboard/app.py
"""

import os
import sys

sys.path.append(".")

import requests
import streamlit as st

from src.text_to_sql.dashboard.components import (
    EXAMPLE_PROMPTS, esc, inject_css, render_header, render_history, render_result,
    render_schema, render_sidebar, section_label,
)

API_BASE = os.getenv("API_BASE", "http://localhost:8000")
MAX_BATCH = 20
NO_EXAMPLE = "— select —"
EMPTY_STATS = {"total": 0, "success": 0, "blocked": 0}

DEFAULT_BATCH = "\n".join([
    "How many customers are in the database?",
    "كم عدد المنتجات في قاعدة البيانات؟",
    "What are the top 5 customers by total sales?",
    "Show total sales broken down by channel",
    "What is the total 2017 budget across all products?",
])

LAYERS = [
    ("simple", "ROUTER", "Keyword rules choose simple / medium / complex. No LLM call."),
    ("simple", "SIMPLE CHAIN", "One call writes the SQL, one writes the answer. Single-table lookups."),
    ("medium", "CHAIN-OF-THOUGHT", "Plans the joins and grouping before writing SQL. Joins, GROUP BY, rankings."),
    ("complex", "REACT AGENT", "LangGraph agent with 4 tools (list_tables, get_schema, run_query, check_query)."),
    ("guard", "SQL GUARD", "Injection check on the question and its translation. SELECT only, read-only "
                           "connection, row limit, timeout. Every execution audited to JSONL."),
]

ENDPOINTS = [
    ("POST", "/query", "Single question"),
    ("POST", "/query/batch", "Batch (max 20)"),
    ("GET", "/schema", "Database schema"),
    ("GET", "/health", "System health"),
    ("GET", "/audit/stats", "Audit log stats"),
    ("GET", "/docs", "Swagger UI"),
]

st.set_page_config(page_title="Text-to-SQL", page_icon="◈", layout="wide", initial_sidebar_state="expanded")


@st.cache_data(ttl=15)
def fetch_health() -> dict | None:
    try:
        r = requests.get(f"{API_BASE}/health", timeout=2)
        return r.json() if r.status_code in (200, 503) else None  # 503 = degraded, body still useful
    except Exception:
        return None


@st.cache_data(ttl=300)
def fetch_json(path: str) -> dict | None:
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=5)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def post(path: str, body: dict, timeout: int) -> dict | None:
    try:
        r = requests.post(f"{API_BASE}{path}", json=body, timeout=timeout)
    except requests.ConnectionError:
        st.error("Cannot connect to the API. Run: `uvicorn src.text_to_sql.api.main:app --port 8000`")
        return None
    except requests.Timeout:
        st.error("Request timed out. Complex questions can take up to a minute.")
        return None
    except Exception as e:
        st.error(f"Request failed: {e}")
        return None
    if r.status_code != 200:
        st.error(f"API error {r.status_code}: {r.text[:200]}")
        return None
    return r.json()


def record(result: dict):
    """Add a result to the history and the session counters."""
    st.session_state.history.append(result)
    stats = st.session_state.stats
    stats["total"] += 1
    if result.get("blocked"):
        stats["blocked"] += 1
    elif result.get("execution_success"):
        stats["success"] += 1


def sidebar():
    with st.sidebar:
        render_sidebar(fetch_health(), st.session_state.stats)
        st.markdown("---")
        if st.button("CLEAR SESSION"):
            st.session_state.history = []
            st.session_state.last_result = None
            st.session_state.stats = dict(EMPTY_STATS)
            fetch_health.clear()
            fetch_json.clear()
            st.rerun()


def query_tab():
    left, right = st.columns([1, 1], gap="large")
    with left:
        section_label("Load example")
        example = st.selectbox("example", [NO_EXAMPLE] + list(EXAMPLE_PROMPTS), label_visibility="collapsed")
        section_label("Question (English or Arabic)")
        question = st.text_area("question", value=EXAMPLE_PROMPTS.get(example, ""), height=120,
                                placeholder="Ask in English or Arabic…", label_visibility="collapsed")
        st.html(f'<div class="note">{len(question)}/2000</div>')
        submit = st.button("EXECUTE →", use_container_width=True, disabled=not question.strip())

    with right:
        if submit and question.strip():
            with st.spinner(""):
                result = post("/query", {"question": question.strip()}, timeout=120)
            if result:
                st.session_state.last_result = result
                record(result)
                fetch_health.clear()

        if st.session_state.last_result:
            render_result(st.session_state.last_result)
        else:
            st.html('<div class="empty">AWAITING QUERY</div>')


def batch_tab():
    section_label(f"Batch input, one question per line (max {MAX_BATCH})")
    text = st.text_area("batch_input", value=DEFAULT_BATCH, height=160, label_visibility="collapsed")
    if not st.button("RUN BATCH →"):
        return

    questions = [line.strip() for line in text.split("\n") if line.strip()]
    if not questions:
        st.warning("Enter at least one question.")
        return
    if len(questions) > MAX_BATCH:
        st.error(f"Maximum {MAX_BATCH} questions per batch.")
        return

    with st.spinner(f"Processing {len(questions)} questions…"):
        batch = post("/query/batch", {"questions": questions}, timeout=300)
    if not batch:
        return

    cols = st.columns(4)
    cols[0].metric("TOTAL", batch["total"])
    cols[1].metric("SUCCESS", batch["success_count"])
    cols[2].metric("BLOCKED", batch["blocked_count"])
    cols[3].metric("COMPLEX", batch.get("summary", {}).get("complex", 0))
    for result in batch["results"]:
        render_result(result, show_question=True)
        record(result)


def history_tab():
    left, right = st.columns([4, 1])
    with left:
        section_label("Session query log (last 30)")
    with right:
        if st.button("CLEAR"):
            st.session_state.history = []
            st.session_state.stats = dict(EMPTY_STATS)
            st.rerun()
    render_history(st.session_state.history)


def schema_tab():
    schema = fetch_json("/schema")
    if schema:
        render_schema(schema)
    else:
        st.html('<div class="card offline">Could not load schema. Is the API running?</div>')


def about_tab():
    left, right = st.columns([1, 1], gap="large")
    with left:
        section_label("Architecture")
        st.html("".join(f'<div class="card layer {tier}"><div class="layer-title">{title}</div>'
                        f'<div class="layer-text">{text}</div></div>' for tier, title, text in LAYERS))

    with right:
        # Numbers come from the latest benchmark run through the API, nothing is hard-coded
        section_label("Benchmark results")
        rows = []
        bench = fetch_json("/benchmark")
        if bench:
            overall = bench.get("overall", {})
            accuracy = f"{overall.get('execution_accuracy', 0):.1%}"
            ci = overall.get("execution_accuracy_ci95")
            if ci:
                accuracy += f" (95% CI {ci[0]:.0%}–{ci[1]:.0%})"
            rows.append(("Execution accuracy", accuracy, "ok"))
            for tier, vals in bench.get("by_complexity", {}).items():
                rows.append((f"{tier.title()} questions", f"{vals['accuracy']:.0%}", ""))
            for lang, vals in bench.get("by_language", {}).items():
                name = "English" if lang == "en" else "Arabic"
                rows.append((f"{name} (n={vals['total']})", f"{vals['accuracy']:.0%}", ""))
            rows.append(("Questions", str(bench.get("meta", {}).get("total_questions", "—")), "muted"))
        else:
            rows.append(("Benchmark", "not run yet (scripts/run_benchmark.py)", "warn"))
        st.html("".join(f'<div class="kv"><span class="muted">{label}</span><span class="{css}">{esc(value)}</span></div>'
                        for label, value, css in rows))

        section_label("API endpoints")
        st.html("".join(f'<div class="kv endpoint"><span class="method">{method}</span><span>{path}</span>'
                        f'<span class="muted">{text}</span></div>' for method, path, text in ENDPOINTS))


def main():
    for key, default in [("history", []), ("last_result", None), ("stats", dict(EMPTY_STATS))]:
        st.session_state.setdefault(key, default)
    inject_css()
    sidebar()
    render_header()

    tabs = st.tabs(["QUERY", "BATCH", "HISTORY", "SCHEMA", "ABOUT"])
    for tab, show in zip(tabs, [query_tab, batch_tab, history_tab, schema_tab, about_tab]):
        with tab:
            show()


if __name__ == "__main__":
    main()
