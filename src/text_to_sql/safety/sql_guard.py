"""
SQL safety guard.

No SQL reaches the database except through SQLGuard.execute(), which runs
the checks below and then executes on a read-only connection.

Checks, in the order a request meets them:
  1. Prompt injection in the question (English and a small Arabic set).
     Arabic questions are checked twice: original text and translation.
  2. Only one SELECT / WITH statement.
  3. No write keywords (DROP, DELETE, UPDATE, INSERT, ...).
  4. No CROSS JOIN or recursive CTEs.
  5. Optional table allow-list.
  6. Suspicious patterns such as UNION SELECT are logged, not blocked.
  7. LIMIT <= row_limit on every query.
  8. Read-only execution with a time limit (database/executor.py).
  9. One audit record (JSONL) per blocked question and per execution.

Checks 2-7 are regular expressions, not a SQL parser. The read-only
connection is what actually guarantees that nothing is written.
"""

import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from src.text_to_sql.database.executor import DEFAULT_TIMEOUT_S, ExecutionResult, execute_readonly
from src.text_to_sql.utils.logger import logger

AUDIT_LOG_DIR = "logs"
AUDIT_LOG_FILE = "logs/sql_audit.jsonl"
DEFAULT_ROW_LIMIT = 500

BLOCKED_WRITE_KEYWORDS = [
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER",
    "CREATE", "TRUNCATE", "REPLACE", "MERGE",
    "GRANT", "REVOKE", "ATTACH", "DETACH",
    "PRAGMA", "VACUUM", "REINDEX",
]

# REPLACE is only a write as "REPLACE INTO"; REPLACE(x, y, z) is a string function.
WRITE_PATTERNS = {
    kw: (r"\bREPLACE\s+INTO\b" if kw == "REPLACE" else rf"\b{kw}\b")
    for kw in BLOCKED_WRITE_KEYWORDS
}

COMPLEXITY_RISK_PATTERNS = [
    r"CROSS\s+JOIN",
    r"SELECT\s+\*\s+FROM\s+\w+\s+JOIN\s+\w+\s+JOIN\s+\w+\s+JOIN",  # 3+ joins with *
    r"WHILE\s*\(",
    r"RECURSIVE",
]

INJECTION_SIGNALS = [
    r"ignore\s+(all\s+)?((previous|prior|above|earlier)\s+)?(instructions?|rules?|prompts?)",
    r"\bsystem\s*prompt\b",
    r"reveal\s+(your|the)\s+(instructions?|prompt|system)",
    r"forget\s+(everything|all)",
    r"new\s+instruction",
    r"override\s+(your|all)\s+",
    r"you\s+are\s+now\s+(a|an|the)\s+",
    r"act\s+as\s+(if\s+)?(you\s+are|a|an)\s+",
    r"pretend\s+(you\s+are|to\s+be)",
    r"disregard\s+(all\s+)?(previous|prior|your)",
    r"were\s+told\s+(before|to\s+ignore|to\s+forget)",
    r"--\s*inject",
    r"<\s*script\s*>",
    r";\s*(drop|delete|update|insert)\s+",
    r"\byou\s+are\s+now\b",
    r"\bnew\s+primary\s+directive\b",
    r"\bwithout\s+restrictions\b",
    r"\bno\s+restrictions\b",
]

# Matched after normalise_arabic(). Kept small on purpose: the main Arabic
# defence is checking the English translation with the patterns above.
INJECTION_SIGNALS_AR = [
    r"تجاهل\s+(جميع\s+|كل\s+)?(التعليمات|الاوامر|القواعد)",   # ignore (all) instructions/commands/rules
    r"انس\s+(كل\s+شيء|جميع|التعليمات)",                       # forget everything / the instructions
    r"انت\s+الان\b",                                            # you are now
    r"(موجه|تعليمات|رسالة)\s+النظام",                           # system prompt / instructions
    r"(بدون|بلا)\s+(اي\s+)?قيود",                               # without (any) restrictions
    r"تصرف\s+(كانك|ك)",                                         # act as (if you are)
]

# Logged as warnings, not blocked
SUSPICIOUS_PATTERNS = [
    r"UNION\s+SELECT",
    r"0x[0-9a-fA-F]+",
    r"SLEEP\s*\(",
    r"BENCHMARK\s*\(",
    r"LOAD_FILE\s*\(",
    r"INTO\s+OUTFILE",
    r"INFORMATION_SCHEMA",
    r"sqlite_master",
]

# A LIMIT at the very end: LIMIT n | LIMIT n OFFSET m | LIMIT m, n
TRAILING_LIMIT = re.compile(r"\bLIMIT\s+(\d+)\s*(?:OFFSET\s+\d+|,\s*(\d+))?\s*;?\s*$", re.IGNORECASE)
ARABIC_DIACRITICS = re.compile(r"[ً-ْٰـ]")  # harakat, dagger alef, tatweel


@dataclass
class GuardResult:
    passed: bool
    check_name: str
    reason: str = ""
    risk_level: str = "none"  # none / medium / high / critical


@dataclass
class SQLCheckReport:
    """All SQL checks combined. No execution, no audit record."""
    passed: bool
    sanitized_sql: str
    reason: str = ""
    checks_passed: list = field(default_factory=list)
    checks_failed: list = field(default_factory=list)
    suspicious: bool = False


@dataclass
class GuardedExecution:
    """Result of SQLGuard.execute(): blocked, failed, or rows returned."""
    ok: bool
    sql: str
    blocked: bool = False
    block_reason: str = ""
    error: str = ""
    result: Optional[ExecutionResult] = None


def normalise_arabic(text: str) -> str:
    """Remove diacritics and tatweel, unify alef and yaa variants."""
    text = ARABIC_DIACRITICS.sub("", text)
    text = re.sub("[إأآٱ]", "ا", text)
    return text.replace("ى", "ي")


def strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", " ", sql)


def check_prompt_injection(question: str) -> GuardResult:
    if not question:
        return GuardResult(True, "prompt_injection")

    for pattern in INJECTION_SIGNALS:
        if re.search(pattern, question.lower(), re.IGNORECASE):
            return GuardResult(False, "prompt_injection",
                               "Prompt injection pattern detected in question", "critical")

    normalised = normalise_arabic(question)
    for pattern in INJECTION_SIGNALS_AR:
        if re.search(pattern, normalised):
            return GuardResult(False, "prompt_injection",
                               "Prompt injection pattern detected in question (Arabic)", "critical")

    return GuardResult(True, "prompt_injection")


def check_read_only_statement(sql: str) -> GuardResult:
    """Allow-list: a single SELECT or WITH statement, nothing else."""
    body = strip_sql_comments(sql or "").strip().rstrip(";").strip()
    if not body:
        return GuardResult(False, "read_only_statement", "Empty SQL", "high")
    if not re.match(r"^(SELECT|WITH)\b", body, re.IGNORECASE):
        return GuardResult(False, "read_only_statement", "Only SELECT queries are allowed", "critical")
    if ";" in body:
        return GuardResult(False, "read_only_statement", "Multiple SQL statements are not allowed", "critical")
    return GuardResult(True, "read_only_statement")


def check_sql_write_operations(sql: str) -> GuardResult:
    if not sql:
        return GuardResult(True, "write_operations")

    upper = strip_sql_comments(sql).upper()
    for keyword, pattern in WRITE_PATTERNS.items():
        if re.search(pattern, upper):
            return GuardResult(False, "write_operations", f"Blocked SQL operation: {keyword}", "critical")
    return GuardResult(True, "write_operations")


def check_sql_complexity(sql: str) -> GuardResult:
    """Block patterns that can exhaust the database. The executor timeout catches the rest."""
    if not sql:
        return GuardResult(True, "complexity")

    for pattern in COMPLEXITY_RISK_PATTERNS:
        if re.search(pattern, sql.upper(), re.IGNORECASE):
            return GuardResult(False, "complexity", f"High-complexity SQL pattern detected: {pattern}", "high")
    return GuardResult(True, "complexity")


def check_suspicious_patterns(sql: str) -> GuardResult:
    """Always passes; risk_level is 'medium' when something looks suspicious."""
    if sql and any(re.search(p, sql, re.IGNORECASE) for p in SUSPICIOUS_PATTERNS):
        return GuardResult(True, "suspicious_patterns",
                           "Suspicious SQL patterns detected (flagged for review)", "medium")
    return GuardResult(True, "suspicious_patterns")


def validate_table_access(sql: str, allowed_tables: Optional[list] = None) -> GuardResult:
    """
    Check that the SQL only uses allowed tables (None = all tables allowed).
    Regex based, so CTE names count as table names.
    """
    if allowed_tables is None:
        return GuardResult(True, "table_access")

    referenced = re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b", sql, re.IGNORECASE)
    allowed = [t.lower() for t in allowed_tables]
    unauthorized = [t.lower() for t in referenced if t.lower() not in allowed]
    if unauthorized:
        return GuardResult(False, "table_access", f"Unauthorized table access: {unauthorized}", "high")
    return GuardResult(True, "table_access")


def enforce_row_limit(sql: str, limit: int = DEFAULT_ROW_LIMIT) -> str:
    """
    Make sure the outer query returns at most `limit` rows.

    Only a LIMIT at the end counts. A LIMIT inside a subquery does not
    limit the outer result, so the outer query still gets one.
    """
    if not sql:
        return sql

    sql = sql.rstrip().rstrip(";").rstrip()
    match = TRAILING_LIMIT.search(sql)
    if not match:
        return f"{sql} LIMIT {limit}"

    group = 2 if match.group(2) is not None else 1  # "LIMIT offset, count" uses group 2
    if int(match.group(group)) <= limit:
        return sql
    start, end = match.span(group)
    return f"{sql[:start]}{limit}{sql[end:]}"


def read_audit_log(last_n: int = 100) -> list:
    if not os.path.exists(AUDIT_LOG_FILE):
        return []
    try:
        with open(AUDIT_LOG_FILE, encoding="utf-8") as f:
            lines = f.readlines()
        return [json.loads(line) for line in lines[-last_n:] if line.strip()]
    except Exception as e:
        logger.error(f"Audit log read failed: {e}")
        return []


def get_audit_stats() -> dict:
    records = read_audit_log(last_n=10_000)
    if not records:
        return {"total": 0}

    total = len(records)
    blocked = sum(1 for r in records if r.get("blocked"))
    by_language = {}
    for r in records:
        lang = r.get("language", "unknown")
        by_language[lang] = by_language.get(lang, 0) + 1

    return {
        "total": total,
        "blocked": blocked,
        "suspicious": sum(1 for r in records if r.get("suspicious")),
        "errors": sum(1 for r in records if r.get("error")),
        "block_rate": round(blocked / total, 4),
        "by_language": by_language,
    }


class SQLGuard:
    """
    guard = SQLGuard()
    ok, reason = guard.check_question("How many customers?")   # before any LLM call
    run = guard.execute(sql, db_path="database/sales.db")       # the only way SQL is run

    The guard keeps no per-request state, so API requests can share one instance.
    """

    def __init__(self, row_limit: int = DEFAULT_ROW_LIMIT, allowed_tables: Optional[list] = None,
                 enable_audit: bool = True, timeout_s: float = DEFAULT_TIMEOUT_S):
        self.row_limit = row_limit
        self.allowed_tables = allowed_tables
        self.enable_audit = enable_audit
        self.timeout_s = timeout_s
        if enable_audit:
            os.makedirs(AUDIT_LOG_DIR, exist_ok=True)

    def check_question(self, question: str, language: str = "en") -> tuple:
        """Return (True, "") if safe, else (False, reason). Blocks are audited."""
        result = check_prompt_injection(question)
        if result.passed:
            return True, ""

        logger.warning(f"Question blocked: {result.reason} | '{question[:60]}'")
        self._audit(question=question, language=language, sql="", blocked=True,
                    block_reason=result.reason, checks_failed=["prompt_injection"], event="question")
        return False, result.reason

    def inspect_sql(self, sql: str) -> SQLCheckReport:
        """Run every SQL check and apply the row limit. No execution, no audit."""
        passed = []
        for result in (check_read_only_statement(sql), check_sql_write_operations(sql),
                       check_sql_complexity(sql), validate_table_access(sql, self.allowed_tables)):
            if not result.passed:
                return SQLCheckReport(False, sql, result.reason, passed, [result.check_name])
            passed.append(result.check_name)

        suspicious = check_suspicious_patterns(sql).risk_level != "none"
        passed.append("suspicious_patterns_flagged" if suspicious else "suspicious_patterns")
        passed.append("row_limit_enforced")
        return SQLCheckReport(True, enforce_row_limit(sql, self.row_limit),
                              checks_passed=passed, suspicious=suspicious)

    def execute(self, sql: str, db_path: str, question: str = "", language: str = "en",
                strategy: str = "") -> GuardedExecution:
        """Check the SQL, then run it read-only. Always writes one audit record."""
        audit = dict(question=question, language=language, strategy=strategy)
        report = self.inspect_sql(sql)
        if not report.passed:
            logger.warning(f"SQL blocked: {report.reason}")
            self._audit(**audit, sql=sql, blocked=True, block_reason=report.reason,
                        checks_passed=report.checks_passed, checks_failed=report.checks_failed)
            return GuardedExecution(ok=False, sql=sql, blocked=True, block_reason=report.reason)

        if report.suspicious:
            logger.warning(f"Suspicious SQL: {sql[:80]}")

        safe_sql = report.sanitized_sql
        audit.update(sql=safe_sql, checks_passed=report.checks_passed, suspicious=report.suspicious)
        start = time.perf_counter()
        try:
            result = execute_readonly(db_path, safe_sql, max_rows=self.row_limit, timeout_s=self.timeout_s)
        except Exception as e:
            self._audit(**audit, execution_ms=round((time.perf_counter() - start) * 1000, 2), error=str(e))
            return GuardedExecution(ok=False, sql=safe_sql, error=str(e))

        self._audit(**audit, row_count=result.row_count, execution_ms=result.execution_ms)
        return GuardedExecution(ok=True, sql=safe_sql, result=result)

    def _audit(self, question, language, sql, blocked=False, block_reason="", row_count=0,
               execution_ms=0.0, checks_passed=None, checks_failed=None, suspicious=False,
               event="sql", strategy="", error=""):
        """Append one JSON line to the audit log."""
        if not self.enable_audit:
            return
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "event": event,
            "strategy": strategy,
            "question": (question or "")[:200],
            "language": language,
            "sql": (sql or "")[:500],
            "blocked": blocked,
            "block_reason": block_reason,
            "row_count": row_count,
            "execution_ms": execution_ms,
            "checks_passed": checks_passed or [],
            "checks_failed": checks_failed or [],
            "suspicious": suspicious,
            "error": error[:300],
        }
        try:
            os.makedirs(AUDIT_LOG_DIR, exist_ok=True)
            with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Audit log write failed: {e}")
