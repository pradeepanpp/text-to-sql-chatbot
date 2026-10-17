"""
Streamlit components. Styles live in style.css.

Every value from the API (question, answer, SQL, table metadata) goes
through esc() before it is put into HTML, so a "<" in SQL or a crafted
question is shown as text, never run as markup.
"""

from html import escape
from pathlib import Path

import streamlit as st

CSS_FILE = Path(__file__).with_name("style.css")

EXAMPLE_PROMPTS = {
    "Simple — Customers": "How many customers are in the database?",
    "Simple — Arabic": "كم عدد المنتجات في قاعدة البيانات؟",
    "Medium — Top Revenue": "What are the top 5 customers by total line total?",
    "Medium — By Channel": "Show total sales broken down by channel",
    "Complex — vs Budget": "Compare total sales versus 2017 budget for each product",
    "Complex — Arabic": "قارن المبيعات الفعلية مقابل ميزانية 2017 لكل منتج",
    "Complex — % Revenue": "What percentage of total revenue came from each channel?",
}


def esc(value) -> str:
    return escape(str(value if value is not None else ""))


def inject_css():
    st.markdown(f"<style>{CSS_FILE.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def section_label(text: str):
    st.html(f'<div class="section-label">{esc(text)}</div>')


def render_header():
    st.html("""
    <div class="header">
        <div class="header-kicker">Bilingual · Arabic / English</div>
        <div class="header-title">Text-to-SQL</div>
        <div class="header-sub">SIMPLE CHAIN · CHAIN-OF-THOUGHT · REACT AGENT · SAFETY LAYER</div>
    </div>
    """)


def render_result(data: dict, show_question: bool = False):
    """One answer card: blocked, failed, or answer with its SQL."""
    question = f'<div class="question">{esc(data.get("question", ""))}</div>' if show_question else ""

    if data.get("blocked"):
        st.html(f"""
        <div class="card blocked">
            {question}
            <div class="card-title warn">BLOCKED BY SAFETY LAYER</div>
            <div class="blocked-text">{esc(data.get("natural_response", ""))}</div>
            <div class="reason">{esc(data.get("block_reason", ""))}</div>
        </div>
        """)
        return

    if not data.get("execution_success"):
        st.html(f'<div class="card failed">{question}<div class="card-title bad">QUERY FAILED</div></div>')
        return

    tier = data.get("complexity", "simple")
    tier_class = tier if tier in ("simple", "medium", "complex") else "simple"
    arabic = data.get("detected_language") == "ar"
    retries = data.get("retries_used", 0)
    retries_text = f"<span class='muted'>| {retries} retries</span>" if retries > 0 else ""

    st.html(f"""
    <div class="card {tier_class}">
        {question}
        <div class="card-meta">
            <div>
                <span class="tier {tier_class}">{esc(tier)}</span>
                <span class="muted">|</span>
                <span class="muted">{"AR عربي" if arabic else "EN"}</span>
                {retries_text}
            </div>
            <span class="ok">✓ SUCCESS</span>
        </div>
        <div class="answer{' rtl' if arabic else ''}">{esc(data.get("natural_response", ""))}</div>
        <div class="sql">{esc(data.get("generated_sql", ""))}</div>
    </div>
    """)


def render_history(history: list):
    """Last 30 questions, newest first."""
    if not history:
        st.html('<div class="empty">NO HISTORY YET</div>')
        return

    rows = ""
    for item in reversed(history[-30:]):
        if item.get("blocked"):
            status = '<span class="warn">⚠</span>'
        elif item.get("execution_success"):
            status = '<span class="ok">✓</span>'
        else:
            status = '<span class="bad">✗</span>'
        question = item.get("question", "")
        if len(question) > 52:
            question = question[:52] + "…"
        lang = "AR" if item.get("detected_language") == "ar" else "EN"
        rows += (f"<tr><td>{status}</td><td>{esc(question)}</td>"
                 f"<td class='muted'>{esc(item.get('complexity', '—'))}</td><td class='muted right'>{lang}</td></tr>")

    st.html(f"""
    <table class="history">
        <thead><tr><th>ST</th><th>QUESTION</th><th>COMPLEXITY</th><th class="right">LANG</th></tr></thead>
        <tbody>{rows}</tbody>
    </table>
    """)


def render_schema(schema_data: dict):
    tables = schema_data.get("tables", []) if schema_data else []
    if not tables:
        return

    section_label(f"{len(tables)} tables · {schema_data.get('total_rows', 0):,} total rows")
    largest = max(t["row_count"] for t in tables) or 1
    for table in tables:
        columns = " ".join(f"<span>{esc(c)}</span>" for c in table["columns"])
        st.html(f"""
        <div class="card table-card">
            <div class="table-head">
                <div class="table-name">{esc(table["name"])}</div>
                <div class="muted">{table["row_count"]:,} rows</div>
            </div>
            <div class="bar"><div style="width:{int(table["row_count"] / largest * 100)}%"></div></div>
            <div class="table-desc">{esc(table.get("description", ""))[:120]}</div>
            <div class="columns">{columns}</div>
        </div>
        """)


def on_off(flag: bool) -> str:
    return '<span class="ok">ON</span>' if flag else '<span class="bad">OFF</span>'


def render_sidebar(api_status: dict | None, session_stats: dict):
    section_label("System status")
    if api_status:
        status = esc(api_status.get("status", "unknown"))
        st.html(f"""
        <div class="card status">
            <div class="row"><span>API</span><span class="{'ok' if status == 'ok' else 'warn'}">● {status.upper()}</span></div>
            <div class="row"><span class="muted">LLM Chain</span>{on_off(api_status.get("chain_loaded"))}</div>
            <div class="row"><span class="muted">SQL Guard</span>{on_off(api_status.get("guard_active"))}</div>
            <div class="row"><span class="muted">Database</span>{on_off(api_status.get("db_connected"))}</div>
            <div class="row total muted">{esc(api_status.get("model", "—"))}</div>
        </div>
        """)
    else:
        st.html("""
        <div class="card status offline">● API OFFLINE<br>
            <span class="muted">uvicorn src.text_to_sql.api.main:app --port 8000</span>
        </div>
        """)

    total = session_stats.get("total", 0)
    blocked = session_stats.get("blocked", 0)
    block_rate = f"{blocked / total * 100:.0f}%" if total > 0 else "—"
    section_label("Session")
    st.html(f"""
    <div class="card status">
        <div class="row"><span class="muted">Queries</span><span>{total}</span></div>
        <div class="row"><span class="muted">Success</span><span class="ok">{session_stats.get("success", 0)}</span></div>
        <div class="row"><span class="muted">Blocked</span><span class="warn">{blocked}</span></div>
        <div class="row total"><span class="muted">Block Rate</span><span class="warn">{block_rate}</span></div>
    </div>
    """)
