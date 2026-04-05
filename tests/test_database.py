# tests/test_database.py
"""
Tests for Phase 1 — Database Layer.

Run with: python tests/test_database.py
Requires: python scripts/setup_database.py to have run first.
"""

import sys
import os
sys.path.append(".")

import sqlite3
from src.text_to_sql.database.loader import verify_database
from src.text_to_sql.database.schema import (
    build_schema_context,
    get_table_names,
    get_column_names,
)
from src.text_to_sql.constants import ALL_TABLES, TABLE_SALES, TABLE_CUSTOMERS

DB_PATH = "database/sales.db"


def test_database_exists():
    print("\n--- Testing Database Existence ---")

    # Test 1
    assert os.path.exists(DB_PATH), (
        f"Database not found: {DB_PATH}\n"
        "Run: python scripts/setup_database.py"
    )
    print(f"✅ Test 1 passed: {DB_PATH} exists")

    # Test 2 — all 6 tables present
    counts = verify_database(DB_PATH)
    for table in ALL_TABLES:
        assert table in counts, f"Missing table: {table}"
    print(f"✅ Test 2 passed: All {len(ALL_TABLES)} tables present")

    # Test 3 — row counts are non-zero
    for table, count in counts.items():
        assert count > 0, f"Table {table} is empty"
    print("✅ Test 3 passed: All tables have rows")

    # Test 4 — sales_orders is the largest table
    assert counts[TABLE_SALES] > 1000, (
        f"Expected 1000+ sales rows, got {counts[TABLE_SALES]}"
    )
    print(f"✅ Test 4 passed: sales_orders has {counts[TABLE_SALES]:,} rows")

    # Print counts
    print("\n  Table row counts:")
    for table, count in sorted(counts.items()):
        print(f"  {table:<25} {count:>8,}")


def test_schema_context():
    print("\n--- Testing Schema Context ---")

    # Test 5 — schema builds without error
    schema = build_schema_context(DB_PATH)
    assert isinstance(schema, str)
    assert len(schema) > 100
    print(f"✅ Test 5 passed: Schema context built ({len(schema)} chars)")

    # Test 6 — all table names present in schema
    for table in ALL_TABLES:
        assert table in schema, f"Table {table} missing from schema context"
    print("✅ Test 6 passed: All table names in schema context")

    # Test 7 — key column names present
    key_columns = [
        "customer_index", "customer_name",
        "product_name",
        "order_number", "line_total",
        "budget_2017",
    ]
    for col in key_columns:
        assert col in schema, f"Column {col} missing from schema context"
    print("✅ Test 7 passed: Key column names in schema context")

    # Test 8 — FK descriptions present
    assert "customer_name_index" in schema
    assert "product_description_index" in schema
    print("✅ Test 8 passed: Foreign key descriptions present")


def test_column_names():
    print("\n--- Testing Column Names ---")

    # Test 9 — customers table columns
    cols = get_column_names(TABLE_CUSTOMERS, DB_PATH)
    assert "customer_index" in cols
    assert "customer_name"  in cols
    print(f"✅ Test 9 passed: customers columns = {cols}")

    # Test 10 — sales_orders has all expected columns
    sales_cols = get_column_names(TABLE_SALES, DB_PATH)
    expected   = [
        "order_number", "order_date", "customer_name_index",
        "channel", "line_total", "order_quantity",
    ]
    for col in expected:
        assert col in sales_cols, f"Missing sales column: {col}"
    print(f"✅ Test 10 passed: sales_orders has {len(sales_cols)} columns")


def test_direct_sql():
    print("\n--- Testing Direct SQL Queries ---")
    conn = sqlite3.connect(DB_PATH)

    # Test 11 — simple SELECT
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM customers")
    count = cursor.fetchone()[0]
    assert count > 0
    print(f"✅ Test 11 passed: SELECT COUNT(*) FROM customers = {count}")

    # Test 12 — join works
    cursor.execute("""
        SELECT c.customer_name, COUNT(*) as order_count
        FROM sales_orders s
        JOIN customers c ON s.customer_name_index = c.customer_index
        GROUP BY c.customer_name
        LIMIT 3
    """)
    rows = cursor.fetchall()
    assert len(rows) > 0
    print(f"✅ Test 12 passed: JOIN query works — {rows[0]}")

    # Test 13 — aggregation works
    cursor.execute("SELECT SUM(line_total) FROM sales_orders")
    total = cursor.fetchone()[0]
    assert total and total > 0
    print(f"✅ Test 13 passed: SUM(line_total) = {total:,.2f}")

    conn.close()


def run_all_tests():
    print("=" * 50)
    print("  Phase 1 — Database Layer Tests")
    print("=" * 50)

    test_database_exists()
    test_schema_context()
    test_column_names()
    test_direct_sql()

    print()
    print("=" * 50)
    print("✅ All database tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    run_all_tests()