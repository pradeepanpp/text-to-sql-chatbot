"""
Read-only SQL execution, the last line of defence.

- The connection uses SQLite's read-only mode (mode=ro), so a write fails
  inside the database even if a regex check missed it.
- A progress handler stops any query that runs past the time limit
  (cartesian joins, runaway recursive CTEs).
- At most max_rows rows are fetched.

SQLGuard.execute() calls this after its checks pass.
"""

import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_TIMEOUT_S = 10.0
DEFAULT_MAX_ROWS = 500


class QueryTimeoutError(Exception):
    """Raised when a query exceeds the execution time budget."""


@dataclass
class ExecutionResult:
    """Rows returned by one read-only query."""
    columns: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    row_count: int = 0
    execution_ms: float = 0.0


def connect_readonly(db_path: str) -> sqlite3.Connection:
    """Open the database read-only. A wrong path raises instead of creating an empty file."""
    path = Path(db_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}. Run: python scripts/setup_database.py")
    return sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)


def execute_readonly(db_path: str, sql: str, max_rows: int = DEFAULT_MAX_ROWS,
                     timeout_s: float = DEFAULT_TIMEOUT_S) -> ExecutionResult:
    """
    Run one statement read-only. Raises sqlite3.Error for SQL errors
    (including write attempts) and QueryTimeoutError after timeout_s.
    """
    conn = connect_readonly(db_path)
    deadline = time.perf_counter() + timeout_s
    # Called every 10k SQLite instructions; a non-zero return aborts the query.
    conn.set_progress_handler(lambda: 1 if time.perf_counter() > deadline else 0, 10_000)

    start = time.perf_counter()
    try:
        cursor = conn.execute(sql)
        rows = cursor.fetchmany(max_rows)
        columns = [d[0] for d in cursor.description] if cursor.description else []
    except sqlite3.OperationalError as e:
        if "interrupted" in str(e).lower():
            raise QueryTimeoutError(f"Query exceeded the {timeout_s:g}s time limit") from e
        raise
    finally:
        conn.close()

    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    return ExecutionResult(columns=columns, rows=rows, row_count=len(rows), execution_ms=elapsed_ms)


def format_rows(result: ExecutionResult, max_rows_shown: int = 50) -> str:
    """Pipe-separated table for the LLM. Only the first max_rows_shown rows, with a note if cut."""
    if not result.rows:
        return "No results found."

    lines = [" | ".join(result.columns), "-" * 40]
    for row in result.rows[:max_rows_shown]:
        lines.append(" | ".join(str(v) for v in row))

    if result.row_count > max_rows_shown:
        lines.append(f"(showing first {max_rows_shown} of {result.row_count} rows)")
    return "\n".join(lines)
