# src/text_to_sql/chain/common.py
"""
Shared pieces used by every SQL generation strategy.

  QueryResult            — the result object that flows through the pipeline
  clean_sql()            — strip markdown fences from LLM output
  validate_sql_safety()  — quick yes/no SQL policy check
  is_infra_error()       — separate API/rate-limit failures from SQL failures
  execute_and_answer()   — guarded execution + natural-language answer

Kept in its own module so the strategy chains do not import from
sql_chain.py (which imports them), avoiding a circular import.
"""

import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from src.text_to_sql.database.executor import format_rows
from src.text_to_sql.constants import LANG_ENGLISH, COMPLEXITY_SIMPLE

# Rows shown to the answer-formatting LLM call (keeps prompts small)
ROWS_SHOWN_TO_LLM = 50


# ─────────────────────────────────────────────
# RESULT DATACLASS
# ─────────────────────────────────────────────

@dataclass
class QueryResult:
    """Full result from one Text-to-SQL query."""
    original_question:  str
    detected_language:  str           = LANG_ENGLISH
    english_question:   str           = ""
    complexity:         str           = COMPLEXITY_SIMPLE   # router's decision
    strategy:           str           = ""      # simple / cot / agent (what actually ran first)
    generated_sql:      str           = ""      # the SQL that was executed (after row limit)
    agent_queries:      list          = field(default_factory=list)  # every SQL the agent tried
    sql_valid:          bool          = False   # passed the guard's policy checks
    execution_success:  bool          = False   # a query returned rows/answer without error
    row_count:          int           = 0
    raw_result:         str           = ""
    natural_response:   str           = ""
    fallback_used:      bool          = False   # self-correction fallback ran
    retries_used:       int           = 0       # LLM generation attempts made by the fallback
    blocked:            bool          = False
    block_reason:       str           = ""
    error:              Optional[str] = None


# ─────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────

def clean_sql(raw: str) -> str:
    """Strip markdown fences, 'SQL:' prefixes and extra whitespace."""
    cleaned = re.sub(r"```(?:sql)?", "", raw or "", flags=re.IGNORECASE)
    cleaned = cleaned.replace("```", "")
    cleaned = re.sub(r"^\s*SQL\s*:", "", cleaned, flags=re.IGNORECASE)
    cleaned = " ".join(cleaned.split())
    return cleaned.strip().rstrip(";").strip()


def validate_sql_safety(sql: str) -> tuple:
    """
    Policy check only, no execution. Returns (is_safe, reason).
    Uses the same checks as SQLGuard so there is one source of truth.
    """
    from src.text_to_sql.safety.sql_guard import SQLGuard
    report = SQLGuard(enable_audit=False).inspect_sql(sql)
    return report.passed, report.reason


# Matched against lower-cased error text. "error code: 5" covers the
# OpenAI SDK's "Error code: 500/502/503 - ..." messages.

_INFRA_SIGNALS = (
       "error code: 429", "rate limit", "ratelimit", "insufficient_quota",
       "error code: 401", "error code: 403", "invalid_api_key",
       "error code: 5", "apiconnectionerror", "connection error",
       "apitimeouterror", "request timed out", "service unavailable",
)


def is_infra_error(error: Optional[str]) -> bool:
    """
    True if a failure came from the LLM provider / network rather than
    from the generated SQL. These are retried or reported separately,
    never counted as a model mistake, and never sent to the SQL fallback.
    """
    if not error:
        return False
    lower = error.lower()
    return any(signal in lower for signal in _INFRA_SIGNALS)


def execute_and_answer(
    result:    QueryResult,
    sql:       str,
    guard,
    db_path:   str,
    strategy:  str,
    answer_fn: Callable[[str, str], str],
) -> QueryResult:
    """
    Run SQL through the guard, then turn the rows into an answer.

    answer_fn(sql, rows_text) -> natural language answer (one LLM call).
    Updates and returns `result`. Never raises for SQL errors; the error
    is stored on the result so the caller can decide to fall back.
    """
    run = guard.execute(
        sql,
        db_path  = db_path,
        question = result.original_question,
        language = result.detected_language,
        strategy = strategy,
    )
    result.generated_sql = run.sql

    if run.blocked:
        result.blocked           = True
        result.block_reason      = run.block_reason
        result.sql_valid         = False
        result.execution_success = False
        result.error             = run.block_reason
        return result

    result.sql_valid = True
    if not run.ok:
        result.execution_success = False
        result.error             = run.error
        return result

    result.row_count  = run.result.row_count
    result.raw_result = format_rows(run.result, ROWS_SHOWN_TO_LLM)
    # Success is set only after the answer exists; if the formatting LLM
    # call raises, the caller sees a failed result with the error.
    result.natural_response  = answer_fn(run.sql, result.raw_result).strip()
    result.execution_success = True
    result.error             = None
    return result
