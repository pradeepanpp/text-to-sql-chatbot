# src/text_to_sql/database/executor.py
"""
Read-only SQL execution.

Every SQL statement the system runs against the sales database goes
through execute_readonly(). It is the last line of defence:

  - The connection is opened with SQLite's read-only flag (mode=ro),
    so a write statement fails inside the database engine even if a
    regex check upstream misses it.
  - A progress handler aborts any query that runs longer than the
    time budget (protects against cartesian joins / runaway CTEs).
  - At most `max_rows` rows are fetched into memory.

SQLGuard.execute() calls this after its policy checks pass, so the
pipeline is: policy checks (guard) -> read-only execution (here).
"""

import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_TIMEOUT_S = 10.0
DEFAULT_MAX_ROWS  = 500


class QueryTimeoutError(Exception):
    """Raised when a query exceeds the execution time budget."""


@dataclass
class ExecutionResult:
    """Rows returned by one read-only query."""
    columns:      list = field(default_factory=list)
    rows:         list = field(default_factory=list)
    row_count:    int   = 0
    execution_ms: float = 0.0


def connect_readonly(db_path: str) -> sqlite3.Connection:
    """
    Open the SQLite database in read-only mode.

    Unlike sqlite3.connect(path), this never creates an empty database
    file when the path is wrong; it raises FileNotFoundError instead.
    """
    path = Path(db_path).resolve()
    if not path.exists():
        raise FileNotFoundError(
            f"Database not found: {db_path}. "
            "Run: python scripts/setup_database.py"
        )
    return sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)


def execute_readonly(
    db_path:   str,
    sql:       str,
    max_rows:  int   = DEFAULT_MAX_ROWS,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> ExecutionResult:
    """
    Run one SQL statement on a read-only connection.

    Raises:
        sqlite3.Error      for SQL errors (bad column, syntax, write attempt)
        QueryTimeoutError  if the query runs longer than timeout_s
    """
    conn     = connect_readonly(db_path)
    deadline = time.perf_counter() + timeout_s
    # Called every 10k SQLite VM instructions; non-zero return aborts.
    conn.set_progress_handler(
        lambda: 1 if time.perf_counter() > deadline else 0, 10_000
    )

    t0 = time.perf_counter()
    try:
        cursor  = conn.execute(sql)
        rows    = cursor.fetchmany(max_rows)
        columns = [d[0] for d in cursor.description] if cursor.description else []
    except sqlite3.OperationalError as e:
        if "interrupted" in str(e).lower():
            raise QueryTimeoutError(
                f"Query exceeded the {timeout_s:g}s time limit"
            ) from e
        raise
    finally:
        conn.close()

    return ExecutionResult(
        columns      = columns,
        rows         = rows,
        row_count    = len(rows),
        execution_ms = round((time.perf_counter() - t0) * 1000, 2),
    )


def format_rows(result: ExecutionResult, max_rows_shown: int = 50) -> str:
    """
    Render rows as a pipe-separated table for the LLM answer formatter.

    Only the first `max_rows_shown` rows are sent to the LLM, to keep
    prompts small; the note at the end tells it the result was cut.
    """
    if not result.rows:
        return "No results found."

    lines = [" | ".join(result.columns), "-" * 40]
    for row in result.rows[:max_rows_shown]:
        lines.append(" | ".join(str(v) for v in row))

    if result.row_count > max_rows_shown:
        lines.append(
            f"(showing first {max_rows_shown} of {result.row_count} rows)"
        )
    return "\n".join(lines)
