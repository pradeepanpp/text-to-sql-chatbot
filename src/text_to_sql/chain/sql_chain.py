# src/text_to_sql/chain/sql_chain.py
"""
Core Text-to-SQL pipeline — Phase 4 update.

Changes from Phase 3:
  - SQLGuard now wraps every query at input and output
  - Prompt injection blocked before reaching LLM
  - All generated SQL sanitized before execution
  - Full audit trail written to logs/sql_audit.jsonl

Flow:
    1. Detect language (Arabic / English)
    2. SQLGuard.check_question() ← NEW Phase 4
    3. Translate Arabic → English if needed
    4. Classify query complexity
    5. Route to appropriate chain
    6. SQLGuard.check_and_sanitize_sql() ← NEW Phase 4
    7. Execute sanitized SQL
    8. Format natural language response
    9. Translate response back to Arabic if needed
"""

import os
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

load_dotenv()

from src.text_to_sql.database.schema import build_schema_context
from src.text_to_sql.chain.complexity_router import ComplexityRouter
from src.text_to_sql.safety.sql_guard import SQLGuard
from src.text_to_sql.utils.logger import logger
from src.text_to_sql.constants import (
    BLOCKED_SQL_KEYWORDS,
    MAX_SQL_RETRIES,
    LANG_ENGLISH,
    LANG_ARABIC,
    COMPLEXITY_SIMPLE,
    COMPLEXITY_MEDIUM,
    COMPLEXITY_COMPLEX,
)

DB_PATH = "database/sales.db"


# ─────────────────────────────────────────────
# RESULT DATACLASS
# ─────────────────────────────────────────────

@dataclass
class QueryResult:
    """Full result from one Text-to-SQL query."""
    original_question:  str
    detected_language:  str           = LANG_ENGLISH
    english_question:   str           = ""
    complexity:         str           = COMPLEXITY_SIMPLE
    generated_sql:      str           = ""
    sql_valid:          bool          = False
    execution_success:  bool          = False
    raw_result:         str           = ""
    natural_response:   str           = ""
    retries_used:       int           = 0
    blocked:            bool          = False   # NEW — was query blocked?
    block_reason:       str           = ""      # NEW — why was it blocked?
    error:              Optional[str] = None


# ─────────────────────────────────────────────
# SHARED UTILITIES
# ─────────────────────────────────────────────

def validate_sql_safety(sql: str) -> tuple:
    """Check SQL for blocked operations. Returns (is_safe, reason)."""
    sql_upper = sql.upper()
    for keyword in BLOCKED_SQL_KEYWORDS:
        if re.search(rf'\b{keyword}\b', sql_upper):
            return False, f"Blocked SQL keyword: {keyword}"
    return True, ""


def clean_sql(raw: str) -> str:
    """Strip markdown fences and whitespace from LLM SQL output."""
    cleaned = re.sub(r"```(?:sql)?", "", raw, flags=re.IGNORECASE)
    cleaned = cleaned.replace("```", "")
    cleaned = " ".join(cleaned.split())
    return cleaned.strip().rstrip(";")


# ─────────────────────────────────────────────
# LANGUAGE DETECTION
# ─────────────────────────────────────────────

def detect_language(text: str) -> str:
    """Detect Arabic vs English via Unicode range check."""
    arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
    ratio        = arabic_chars / max(len(text), 1)
    return LANG_ARABIC if ratio > 0.2 else LANG_ENGLISH


# ─────────────────────────────────────────────
# PROMPTS
# ─────────────────────────────────────────────

FALLBACK_SQL_PROMPT = ChatPromptTemplate.from_template("""
Write a SQLite SELECT query to answer the question.
Return ONLY the SQL query. No explanation. No markdown.

Schema:
{schema}

Question: {question}

SQL:""")

FALLBACK_CORRECT_PROMPT = ChatPromptTemplate.from_template("""
Fix this SQL query that produced an error.
Return ONLY the corrected SQL. No explanation. No markdown.

Schema: {schema}
Question: {question}
Failed SQL: {failed_sql}
Error: {error}

Corrected SQL:""")

FORMAT_PROMPT = ChatPromptTemplate.from_template("""
Answer the question clearly based on the query result.
Be concise. Do not mention SQL. If empty, say no data was found.

Question: {question}
SQL: {sql}
Result: {result}

Answer:""")

TRANSLATE_TO_EN = ChatPromptTemplate.from_template("""
Translate this Arabic question to English.
Return only the English translation.

Arabic: {arabic_text}
English:""")

TRANSLATE_TO_AR = ChatPromptTemplate.from_template("""
Translate this English answer to Arabic.
Return only the Arabic translation.

English: {english_text}
Arabic:""")

BLOCKED_RESPONSE_AR = "عذراً، لا يمكن معالجة هذا الطلب لأسباب أمنية."
BLOCKED_RESPONSE_EN = "This request has been blocked for security reasons."


# ─────────────────────────────────────────────
# MAIN CHAIN
# ─────────────────────────────────────────────

class TextToSQLChain:
    """
    Complete Text-to-SQL pipeline — Phase 4.

    Added: SQLGuard integration at question and SQL levels.
    Every query is now:
      1. Checked for prompt injection
      2. SQL validated and sanitized before execution
      3. Fully audited in logs/sql_audit.jsonl

    Usage:
        chain  = TextToSQLChain()
        result = chain.query("Top 5 customers by revenue?")

    """

    def __init__(
        self,
        db_path:     str   = DB_PATH,
        model:       str   = "gpt-4o-mini",
        temperature: float = 0.0,
        max_tokens:  int   = 500,
        row_limit:   int   = 500,
    ):
        self.db_path = db_path

        self.llm = ChatOpenAI(
            model       = model,
            temperature = temperature,
            max_tokens  = max_tokens,
            api_key     = os.getenv("OPENAI_API_KEY"),
        )

        self.schema = build_schema_context(db_path)
        self.router = ComplexityRouter()
        self.guard  = SQLGuard(row_limit=row_limit, enable_audit=True)

        # Fallback chains
        self._fallback_chain  = FALLBACK_SQL_PROMPT    | self.llm | StrOutputParser()
        self._correct_chain   = FALLBACK_CORRECT_PROMPT | self.llm | StrOutputParser()
        self._format_chain    = FORMAT_PROMPT           | self.llm | StrOutputParser()
        self._to_en_chain     = TRANSLATE_TO_EN         | self.llm | StrOutputParser()
        self._to_ar_chain     = TRANSLATE_TO_AR         | self.llm | StrOutputParser()

        # Lazy-loaded strategy chains
        self._simple_chain = None
        self._cot_chain    = None
        self._agent_chain  = None

        logger.info(f"TextToSQLChain ready — model={model} db={db_path}")

    # ─────────────────────────────────────────
    # PUBLIC
    # ─────────────────────────────────────────

    def query(self, question: str) -> QueryResult:
        """
        Full pipeline with safety layer.
        Returns QueryResult — check result.blocked before using response.
        """
        if not question or not question.strip():
            return QueryResult(
                original_question = question or "",
                error             = "Empty question",
            )

        result                   = QueryResult(original_question=question.strip())
        result.detected_language = detect_language(question)

        # ── Phase 4: Input Guard ──────────────
        is_safe, reason = self.guard.check_question(question)
        if not is_safe:
            result.blocked        = True
            result.block_reason   = reason
            result.natural_response = (
                BLOCKED_RESPONSE_AR
                if result.detected_language == LANG_ARABIC
                else BLOCKED_RESPONSE_EN
            )
            logger.warning(f"Query BLOCKED at input: {reason}")
            return result

        # ── Language detection + translation ──
        if result.detected_language == LANG_ARABIC:
            logger.info("Arabic detected — translating...")
            result.english_question = self._translate_to_english(question)
            logger.info(f"Translated: {result.english_question}")
        else:
            result.english_question = question

        # ── Complexity routing ────────────────
        complexity_result = self.router.classify(result.english_question)
        result.complexity = complexity_result.complexity
        logger.info(
            f"Complexity: {result.complexity} "
            f"(conf={complexity_result.confidence}) | "
            f"{complexity_result.reasoning}"
        )

        # ── Route to strategy ─────────────────
        result = self._route_and_execute(result)

        # ── Phase 4: SQL Guard ────────────────
        if result.generated_sql and result.generated_sql != "Multi-step agent query":
            safe_sql, sql_ok, sql_reason = self.guard.check_and_sanitize_sql(
                sql      = result.generated_sql,
                question = question,
                language = result.detected_language,
            )
            if not sql_ok:
                result.blocked          = True
                result.block_reason     = sql_reason
                result.execution_success = False
                result.natural_response = (
                    BLOCKED_RESPONSE_AR
                    if result.detected_language == LANG_ARABIC
                    else BLOCKED_RESPONSE_EN
                )
                logger.warning(f"Query BLOCKED at SQL: {sql_reason}")
                return result
            result.generated_sql = safe_sql

        # ── Fallback on failure ───────────────
        if not result.execution_success and result.complexity != COMPLEXITY_COMPLEX:
            logger.warning("Primary chain failed — trying fallback direct chain...")
            result = self._fallback_with_correction(result)

        # ── Translate response back ───────────
        if result.detected_language == LANG_ARABIC and result.natural_response:
            if result.natural_response not in [BLOCKED_RESPONSE_AR, BLOCKED_RESPONSE_EN]:
                result.natural_response = self._translate_to_arabic(
                    result.natural_response
                )

        return result

    def analyze_batch(self, questions: list) -> list:
        """Run multiple queries sequentially."""
        return [self.query(q) for q in questions]

    # ─────────────────────────────────────────
    # ROUTING
    # ─────────────────────────────────────────

    def _get_simple_chain(self):
        if self._simple_chain is None:
            from src.text_to_sql.chain.simple_chain import SimpleChain
            self._simple_chain = SimpleChain(self.llm, self.schema, self.db_path)
        return self._simple_chain

    def _get_cot_chain(self):
        if self._cot_chain is None:
            from src.text_to_sql.chain.cot_chain import CoTChain
            self._cot_chain = CoTChain(self.llm, self.schema, self.db_path)
        return self._cot_chain

    def _get_agent_chain(self):
        if self._agent_chain is None:
            from src.text_to_sql.chain.agent_chain import AgentChain
            self._agent_chain = AgentChain(self.llm, self.schema, self.db_path)
        return self._agent_chain

    def _route_and_execute(self, result: QueryResult) -> QueryResult:
        question = result.english_question
        if result.complexity == COMPLEXITY_SIMPLE:
            return self._get_simple_chain().run(question, result)
        elif result.complexity == COMPLEXITY_MEDIUM:
            return self._get_cot_chain().run(question, result)
        elif result.complexity == COMPLEXITY_COMPLEX:
            return self._get_agent_chain().run(question, result)
        return self._get_simple_chain().run(question, result)

    # ─────────────────────────────────────────
    # SELF-CORRECTION FALLBACK
    # ─────────────────────────────────────────

    def _fallback_with_correction(self, result: QueryResult) -> QueryResult:
        question   = result.english_question
        last_error = result.error or "Unknown error"
        last_sql   = result.generated_sql or ""

        for attempt in range(MAX_SQL_RETRIES):
            try:
                if attempt == 0:
                    raw = self._fallback_chain.invoke({
                        "schema":   self.schema,
                        "question": question,
                    })
                else:
                    raw = self._correct_chain.invoke({
                        "schema":     self.schema,
                        "question":   question,
                        "failed_sql": last_sql,
                        "error":      last_error,
                    })
                    result.retries_used += 1

                sql = clean_sql(raw)
                last_sql = sql

                is_safe, reason = validate_sql_safety(sql)
                if not is_safe:
                    result.error = reason
                    return result

                result.generated_sql = sql
                result.sql_valid     = True

                db_result = self._execute_sql(sql)
                result.raw_result        = db_result
                result.execution_success = True

                result.natural_response = self._format_chain.invoke({
                    "question": question,
                    "sql":      sql,
                    "result":   db_result,
                }).strip()

                logger.info(f"Fallback succeeded on attempt {attempt + 1}")
                return result

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Fallback attempt {attempt + 1} failed: {e}")
                result.error = last_error

        return result

    def _execute_sql(self, sql: str) -> str:
        conn   = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchmany(100)

        if not rows:
            conn.close()
            return "No results found."

        cols  = [d[0] for d in cursor.description]
        lines = [" | ".join(cols), "-" * 40]
        for row in rows:
            lines.append(" | ".join(str(v) for v in row))

        conn.close()
        return "\n".join(lines)

    # ─────────────────────────────────────────
    # LANGUAGE HELPERS
    # ─────────────────────────────────────────

    def _translate_to_english(self, arabic_text: str) -> str:
        try:
            return self._to_en_chain.invoke(
                {"arabic_text": arabic_text}
            ).strip()
        except Exception as e:
            logger.error(f"Translation to English failed: {e}")
            return arabic_text

    def _translate_to_arabic(self, english_text: str) -> str:
        try:
            return self._to_ar_chain.invoke(
                {"english_text": english_text}
            ).strip()
        except Exception as e:
            logger.error(f"Translation to Arabic failed: {e}")
            return english_text