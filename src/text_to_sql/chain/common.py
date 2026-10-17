"""
Pieces shared by every SQL strategy. Kept apart from sql_chain.py so the
strategy modules can import them without a circular import.
"""

import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from src.text_to_sql.constants import COMPLEXITY_SIMPLE, LANG_ENGLISH
from src.text_to_sql.database.executor import format_rows

ROWS_SHOWN_TO_LLM = 50  # rows sent to the answer-writing LLM call

# Matched against lower-cased error text. "error code: 5" covers OpenAI's 500/502/503.
INFRA_SIGNALS = (
    "error code: 429", "rate limit", "ratelimit", "insufficient_quota",
    "error code: 401", "error code: 403", "invalid_api_key",
    "error code: 5", "apiconnectionerror", "connection error",
    "apitimeouterror", "request timed out", "service unavailable",
)


@dataclass
class QueryResult:
    original_question: str
    detected_language: str = LANG_ENGLISH
    english_question: str = ""
    complexity: str = COMPLEXITY_SIMPLE   # router decision
    strategy: str = ""                    # simple / cot / agent, the one that ran first
    generated_sql: str = ""               # SQL that was executed, with the row limit
    agent_queries: list = field(default_factory=list)  # every SQL the agent ran
    sql_valid: bool = False               # passed the guard's checks
    execution_success: bool = False       # SQL ran and an answer was written
    row_count: int = 0
    raw_result: str = ""
    natural_response: str = ""
    fallback_used: bool = False
    retries_used: int = 0                 # LLM attempts made by the fallback
    blocked: bool = False
    block_reason: str = ""
    error: Optional[str] = None


def clean_sql(raw: str) -> str:
    """Remove markdown fences, a leading 'SQL:' and extra whitespace."""
    cleaned = re.sub(r"```(?:sql)?", "", raw or "", flags=re.IGNORECASE).replace("```", "")
    cleaned = re.sub(r"^\s*SQL\s*:", "", cleaned, flags=re.IGNORECASE)
    return " ".join(cleaned.split()).strip().rstrip(";").strip()


def is_infra_error(error: Optional[str]) -> bool:
    """
    True if the failure came from the LLM provider or the network, not from
    the SQL. These are reported separately and never sent to the SQL fallback.
    """
    if not error:
        return False
    return any(signal in error.lower() for signal in INFRA_SIGNALS)


def execute_and_answer(result: QueryResult, sql: str, guard, db_path: str, strategy: str,
                       answer_fn: Callable[[str, str], str]) -> QueryResult:
    """
    Run the SQL through the guard, then ask answer_fn(sql, rows_text) for the
    answer. SQL errors are stored on the result (not raised) so the caller
    can decide whether to fall back.
    """
    run = guard.execute(sql, db_path=db_path, question=result.original_question,
                        language=result.detected_language, strategy=strategy)
    result.generated_sql = run.sql

    if run.blocked:
        result.blocked = True
        result.block_reason = run.block_reason
        result.sql_valid = False
        result.execution_success = False
        result.error = run.block_reason
        return result

    result.sql_valid = True
    if not run.ok:
        result.execution_success = False
        result.error = run.error
        return result

    result.row_count = run.result.row_count
    result.raw_result = format_rows(run.result, ROWS_SHOWN_TO_LLM)
    # Mark success only after the answer exists, so a failing answer call
    # leaves a failed result.
    result.natural_response = answer_fn(run.sql, result.raw_result).strip()
    result.execution_success = True
    result.error = None
    return result
