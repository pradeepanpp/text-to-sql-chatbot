import os

import pytest

pytest.importorskip("streamlit")

from src.text_to_sql.dashboard import components  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EVIL = '<img src=x onerror="alert(1)">'


def test_esc():
    assert components.esc("SELECT * FROM t WHERE a<b") == "SELECT * FROM t WHERE a&lt;b"
    assert components.esc(EVIL) == "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;"
    assert components.esc(None) == ""


def test_api_values_are_escaped(monkeypatch):
    rendered = []
    monkeypatch.setattr(components.st, "html", lambda html: rendered.append(html))

    result = {"question": EVIL, "natural_response": EVIL, "generated_sql": EVIL, "execution_success": True,
              "complexity": EVIL, "detected_language": "en", "block_reason": EVIL}
    components.render_result(result, show_question=True)
    components.render_result({**result, "blocked": True})
    components.render_history([result])
    components.render_schema({"tables": [{"name": EVIL, "row_count": 1, "columns": [EVIL], "description": EVIL}],
                              "total_rows": 1})
    components.render_sidebar({"status": EVIL, "model": EVIL}, {"total": 1, "success": 1, "blocked": 0})

    html = "".join(rendered)
    assert "<img" not in html and "&lt;img" in html


def test_dashboard_starts_without_api():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(os.path.join(ROOT, "src/text_to_sql/dashboard/app.py"), default_timeout=30)
    app.run()
    assert not app.exception
    assert [t.label for t in app.tabs] == ["QUERY", "BATCH", "HISTORY", "SCHEMA", "ABOUT"]
