"""
Schema description sent to the LLM with every question.

For each table: row count, plain-English description, columns (read from
the database), two sample rows, and the allowed values of low-cardinality
text columns, so the model filters on real values such as
channel = 'Wholesale' instead of guessing. Foreign keys are listed at the top.
"""

import sqlite3
from functools import lru_cache

from src.text_to_sql.constants import ALL_TABLES, TABLE_DESCRIPTIONS
from src.text_to_sql.database.executor import connect_readonly
from src.text_to_sql.utils.logger import logger

DB_PATH = "database/sales.db"
MAX_DISTINCT_VALUES_LISTED = 12

FK_DESCRIPTIONS = """
Foreign Key Relationships:
- sales_orders.customer_name_index → customers.customer_index
- sales_orders.product_description_index → products.product_index
- sales_orders.delivery_region_index → regions.id
- regions.state_code → state_regions.state_code
- budgets.product_name → products.product_name
"""


def get_table_schema(conn: sqlite3.Connection, table: str) -> str:
    """CREATE TABLE style listing of the columns."""
    lines = []
    for _, name, col_type, notnull, _, pk in conn.execute(f"PRAGMA table_info({table})"):
        lines.append(f"  {name} {col_type}{' PRIMARY KEY' if pk else ''}{' NOT NULL' if notnull else ''}")
    return f"CREATE TABLE {table} (\n" + ",\n".join(lines) + "\n)"


def get_sample_rows(conn: sqlite3.Connection, table: str, n: int = 2) -> str:
    try:
        cursor = conn.execute(f"SELECT * FROM {table} LIMIT {n}")
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]
    except Exception:
        return "  (sample rows unavailable)"
    if not rows:
        return "  (empty table)"
    return "\n".join("  Row: " + ", ".join(f"{c}={v}" for c, v in zip(cols, row)) for row in rows)


def get_categorical_values(conn: sqlite3.Connection, table: str) -> str:
    """Lines like "  channel: 'Distributor', 'Wholesale'" for text columns with few values."""
    lines = []
    for col in conn.execute(f"PRAGMA table_info({table})").fetchall():
        name, col_type = col[1], (col[2] or "").upper()
        if col_type and "TEXT" not in col_type and "CHAR" not in col_type:
            continue
        try:
            n_distinct = conn.execute(f'SELECT COUNT(DISTINCT "{name}") FROM {table}').fetchone()[0]
            if n_distinct == 0 or n_distinct > MAX_DISTINCT_VALUES_LISTED:
                continue
            values = conn.execute(
                f'SELECT DISTINCT "{name}" FROM {table} WHERE "{name}" IS NOT NULL ORDER BY 1'
            ).fetchall()
            lines.append(f"  {name}: " + ", ".join(repr(v[0]) for v in values))
        except Exception:
            continue
    return "\n".join(lines)


def get_row_count(conn: sqlite3.Connection, table: str) -> int:
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except Exception:
        return 0


@lru_cache(maxsize=1)
def build_schema_context(db_path: str = DB_PATH) -> str:
    """Build the schema text once per process (cached)."""
    conn = connect_readonly(db_path)
    sections = ["DATABASE SCHEMA — Regional Sales System", "=" * 50, FK_DESCRIPTIONS, "=" * 50, "TABLES:\n"]

    for table in ALL_TABLES:
        try:
            section = (
                f"Table: {table} ({get_row_count(conn, table):,} rows)\n"
                f"Description: {TABLE_DESCRIPTIONS.get(table, '')}\n"
                f"{get_table_schema(conn, table)}\n"
                f"Sample rows:\n{get_sample_rows(conn, table, n=2)}"
            )
            categorical = get_categorical_values(conn, table)
            if categorical:
                section += f"\nAllowed values:\n{categorical}"
            sections += [section, "-" * 40]
        except Exception as e:
            logger.warning(f"Could not get schema for {table}: {e}")

    conn.close()
    context = "\n".join(sections)
    logger.info(f"Schema context built: {len(context)} chars, {len(ALL_TABLES)} tables")
    return context


def get_column_names(table: str, db_path: str = DB_PATH) -> list:
    conn = connect_readonly(db_path)
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    conn.close()
    return cols
