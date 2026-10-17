import sqlite3

import pytest

from src.text_to_sql.constants import ALL_TABLES, TABLE_CUSTOMERS, TABLE_SALES
from src.text_to_sql.database.executor import (
    QueryTimeoutError, connect_readonly, execute_readonly, format_rows,
)
from src.text_to_sql.database.loader import verify_database
from src.text_to_sql.database.schema import build_schema_context, get_column_names
from tests.conftest import count_customers


# Read-only execution

def test_readonly_connection_rejects_writes(synthetic_db):
    """Even if every regex check is bypassed, the database refuses writes."""
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        execute_readonly(synthetic_db, "DELETE FROM customers")
    assert count_customers(synthetic_db) == 20


def test_missing_database_is_not_created(tmp_path):
    missing = tmp_path / "nope.db"
    with pytest.raises(FileNotFoundError):
        connect_readonly(str(missing))
    assert not missing.exists()


def test_runaway_query_times_out(synthetic_db):
    infinite = "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n) SELECT COUNT(*) FROM n"
    with pytest.raises(QueryTimeoutError):
        execute_readonly(synthetic_db, infinite, timeout_s=0.3)


def test_max_rows_and_format(synthetic_db):
    result = execute_readonly(synthetic_db, "SELECT * FROM customers", max_rows=7)
    assert result.row_count == 7 and result.columns == ["customer_index", "customer_name"]
    text = format_rows(result, max_rows_shown=3)
    assert text.splitlines()[0] == "customer_index | customer_name"
    assert text.endswith("(showing first 3 of 7 rows)")


# Schema context

def test_schema_context(synthetic_db):
    build_schema_context.cache_clear()
    schema = build_schema_context(synthetic_db)
    for table in ALL_TABLES:
        assert f"Table: {table}" in schema
    for column in ["customer_index", "customer_name", "product_name", "order_number", "line_total", "budget_2017"]:
        assert column in schema
    assert "sales_orders.customer_name_index → customers.customer_index" in schema
    assert "channel: 'Distributor', 'Export', 'Wholesale'" in schema  # allowed values are listed
    build_schema_context.cache_clear()


def test_column_names(synthetic_db):
    assert get_column_names(TABLE_CUSTOMERS, synthetic_db) == ["customer_index", "customer_name"]
    sales = get_column_names(TABLE_SALES, synthetic_db)
    for col in ["order_number", "order_date", "customer_name_index", "channel", "line_total", "order_quantity"]:
        assert col in sales


def test_verify_database(synthetic_db, tmp_path):
    counts = verify_database(synthetic_db)
    assert set(counts) == set(ALL_TABLES) and counts[TABLE_SALES] == 600
    with pytest.raises(FileNotFoundError):
        verify_database(str(tmp_path / "missing.db"))


# Real database (skipped without database/sales.db)

def test_real_database_tables(real_db):
    counts = verify_database(real_db)
    for table in ALL_TABLES:
        assert counts.get(table, 0) > 0, table
    assert counts[TABLE_SALES] > 1000


def test_real_database_join(real_db):
    rows = execute_readonly(real_db, """
        SELECT c.customer_name, COUNT(*) FROM sales_orders s
        JOIN customers c ON s.customer_name_index = c.customer_index
        GROUP BY c.customer_name LIMIT 3
    """).rows
    assert len(rows) == 3
    assert execute_readonly(real_db, "SELECT SUM(line_total) FROM sales_orders").rows[0][0] > 0
