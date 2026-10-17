# src/text_to_sql/database/schema.py
"""
Rich schema context builder.

Feeds the LLM a detailed description of every table including:
  - Column names and types (read from the database, so always correct)
  - Table descriptions in plain English (constants.py)
  - Sample rows (2 per table)
  - Allowed values for low-cardinality text columns (e.g. channel)
  - Foreign key relationships
  - Row counts

This is the single biggest factor in SQL generation accuracy.
The more context the LLM has about the schema, the fewer
hallucinated column names, wrong joins and wrong filter values.
"""

import sqlite3
from functools import lru_cache
from src.text_to_sql.utils.logger import logger
from src.text_to_sql.constants import TABLE_DESCRIPTIONS, ALL_TABLES
from src.text_to_sql.database.executor import connect_readonly

# Text columns with at most this many distinct values get their values
# listed in the prompt, so the LLM filters on real values
# (e.g. channel = 'Wholesale') instead of guessing.
MAX_DISTINCT_VALUES_LISTED = 12

DB_PATH = "database/sales.db"

# Foreign key relationships — described explicitly for the LLM
FK_DESCRIPTIONS = """
Foreign Key Relationships:
- sales_orders.customer_name_index → customers.customer_index
- sales_orders.product_description_index → products.product_index
- sales_orders.delivery_region_index → regions.id
- regions.state_code → state_regions.state_code
- budgets.product_name → products.product_name
"""


def get_table_schema(conn: sqlite3.Connection, table: str) -> str:
    """
    Returns CREATE TABLE statement + column info for one table.
    """
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    columns = cursor.fetchall()

    col_lines = []
    for col in columns:
        # col = (cid, name, type, notnull, default, pk)
        pk_marker  = " PRIMARY KEY" if col[5] else ""
        nn_marker  = " NOT NULL"    if col[3] else ""
        col_lines.append(f"  {col[1]} {col[2]}{pk_marker}{nn_marker}")

    return f"CREATE TABLE {table} (\n" + ",\n".join(col_lines) + "\n)"


def get_sample_rows(conn: sqlite3.Connection, table: str, n: int = 2) -> str:
    """
    Returns n sample rows from a table as readable text.
    """
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table} LIMIT {n}")
        rows    = cursor.fetchall()
        cols    = [desc[0] for desc in cursor.description]

        if not rows:
            return "  (empty table)"

        lines = []
        for row in rows:
            pairs = ", ".join(f"{c}={v}" for c, v in zip(cols, row))
            lines.append(f"  Row: {pairs}")
        return "\n".join(lines)
    except Exception:
        return "  (sample rows unavailable)"


def get_categorical_values(conn: sqlite3.Connection, table: str) -> str:
    """
    For TEXT columns with few distinct values, list those values.
    Returns lines like:  channel: 'Distributor', 'Wholesale', ...
    """
    lines  = []
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    for col in cursor.fetchall():
        name, col_type = col[1], (col[2] or "").upper()
        if col_type and "TEXT" not in col_type and "CHAR" not in col_type:
            continue
        try:
            cursor.execute(
                f'SELECT COUNT(DISTINCT "{name}") FROM {table}'
            )
            n_distinct = cursor.fetchone()[0]
            if n_distinct == 0 or n_distinct > MAX_DISTINCT_VALUES_LISTED:
                continue
            cursor.execute(
                f'SELECT DISTINCT "{name}" FROM {table} '
                f'WHERE "{name}" IS NOT NULL ORDER BY 1'
            )
            values = ", ".join(repr(r[0]) for r in cursor.fetchall())
            lines.append(f"  {name}: {values}")
        except Exception:
            continue
    return "\n".join(lines)


def get_row_count(conn: sqlite3.Connection, table: str) -> int:
    """Returns row count for a table."""
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        return cursor.fetchone()[0]
    except Exception:
        return 0


@lru_cache(maxsize=1)
def build_schema_context(db_path: str = DB_PATH) -> str:
    """
    Build the full schema context string for the LLM.
    Cached — only built once per session.

    Returns a rich multi-section string covering all tables.
    """
    conn = connect_readonly(db_path)

    sections = []
    sections.append("DATABASE SCHEMA — Regional Sales System")
    sections.append("=" * 50)
    sections.append(FK_DESCRIPTIONS)
    sections.append("=" * 50)
    sections.append("TABLES:\n")

    for table in ALL_TABLES:
        try:
            count       = get_row_count(conn, table)
            schema_sql  = get_table_schema(conn, table)
            samples     = get_sample_rows(conn, table, n=2)
            description = TABLE_DESCRIPTIONS.get(table, "")
            categorical = get_categorical_values(conn, table)

            section = (
                f"Table: {table} ({count:,} rows)\n"
                f"Description: {description}\n"
                f"{schema_sql}\n"
                f"Sample rows:\n{samples}"
            )
            if categorical:
                section += f"\nAllowed values:\n{categorical}"
            sections.append(section)
            sections.append("-" * 40)

        except Exception as e:
            logger.warning(f"Could not get schema for {table}: {e}")

    conn.close()
    context = "\n".join(sections)
    logger.info(f"Schema context built: {len(context)} chars, {len(ALL_TABLES)} tables")
    return context


def get_table_names(db_path: str = DB_PATH) -> list:
    """Return list of available table names."""
    conn   = connect_readonly(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tables


def get_column_names(table: str, db_path: str = DB_PATH) -> list:
    """Return column names for a specific table."""
    conn   = connect_readonly(db_path)
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    cols   = [row[1] for row in cursor.fetchall()]
    conn.close()
    return cols