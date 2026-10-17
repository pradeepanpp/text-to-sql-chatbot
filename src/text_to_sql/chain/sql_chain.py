# src/text_to_sql/chain/sql_chain.py
"""
Core Text-to-SQL pipeline (orchestrator).

Flow for one question:
    1. Detect language (Arabic / English)
    2. Input guard on the original question         ← blocks before any LLM call
    3. Arabic only: translate to English (LLM)
    4. Arabic only: input guard on the translation  ← catches Arabic injections
    5. Complexity router (rules, no LLM) picks a strategy
    6. Strategy writes SQL; SQLGuard.execute() checks it, applies the row
       limit and runs it on a read-only connection (audited)
    7. On a SQL failure (not a block, not a rate limit): fallback chain
       regenerates and self-corrects up to MAX_SQL_RETRIES times
    8. Arabic only: translate the answer back (LLM)

No SQL is ever executed outside SQLGuard.execute().
"""

import os

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

load_dotenv()

from src.text_to_sql.chain.common import (       # re-exported for older imports
    QueryResult,
    clean_sql,
    validate_sql_safety,  # noqa: F401  (re-exported for older imports)
    is_infra_error,
    execute_and_answer,
)
from src.text_to_sql.language.detector import detect_language
from src.text_to_sql.database.schema import build_schema_context
from src.text_to_sql.chain.complexity_router import ComplexityRouter
from src.text_to_sql.safety.sql_guard import SQLGuard
from src.text_to_sql.utils.logger import logger
from src.text_to_sql.constants import (
    MAX_SQL_RETRIES,
    LANG_ENGLISH,
    LANG_ARABIC,
    COMPLEXITY_SIMPLE,
    COMPLEXITY_MEDIUM,
    COMPLEXITY_COMPLEX,
)

DB_PATH = os.getenv("DB_PATH", "database/sales.db")

# Router decision -> strategy that handles it
STRATEGY_FOR_COMPLEXITY = {
    COMPLEXITY_SIMPLE:  "simple",
    COMPLEXITY_MEDIUM:  "cot",
    COMPLEXITY_COMPLEX: "agent",
}
STRATEGIES = ("simple", "cot", "agent")


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
Keep numbers, product names and customer names exactly as they are.
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
    Complete Text-to-SQL pipeline.

    Usage:
        chain  = TextToSQLChain()
        result = chain.query("Top 5 customers by revenue?")

    For tests, pass any LangChain chat model as `llm`.
    """

    def __init__(
        self,
        db_path:     str   = DB_PATH,
        model:       str   = "gpt-4o-mini",
        temperature: float = 0.0,
        max_tokens:  int   = 500,
        row_limit:   int   = 500,
        llm                = None,
        guard:       SQLGuard = None,
    ):
        self.db_path = db_path

        self.llm = llm or ChatOpenAI(
            model       = model,
            temperature = temperature,
            max_tokens  = max_tokens,
            timeout     = 60,
            max_retries = 2,
            api_key     = os.getenv("OPENAI_API_KEY"),
        )

        self.schema = build_schema_context(db_path)
        self.router = ComplexityRouter()
        self.guard  = guard or SQLGuard(row_limit=row_limit, enable_audit=True)

        self._fallback_chain = FALLBACK_SQL_PROMPT     | self.llm | StrOutputParser()
        self._correct_chain  = FALLBACK_CORRECT_PROMPT | self.llm | StrOutputParser()
        self._format_chain   = FORMAT_PROMPT           | self.llm | StrOutputParser()
        self._to_en_chain    = TRANSLATE_TO_EN         | self.llm | StrOutputParser()
        self._to_ar_chain    = TRANSLATE_TO_AR         | self.llm | StrOutputParser()

        # Lazy-loaded strategy chains
        self._strategies = {}

        logger.info(f"TextToSQLChain ready — db={db_path}")

    # ─────────────────────────────────────────
    # PUBLIC
    # ─────────────────────────────────────────

    def query(
        self,
        question:       str,
        language:       str  = None,
        strategy:       str  = None,
        allow_fallback: bool = True,
    ) -> QueryResult:
        """
        Run the full pipeline for one question.

        Args:
            question:       English or Arabic question
            language:       'en' / 'ar' to skip auto-detection
            strategy:       'simple' / 'cot' / 'agent' to bypass the router
                            (used for ablation runs)
            allow_fallback: set False to measure a strategy on its own

        Check result.blocked before using result.natural_response.
        """
        if not question or not question.strip():
            return QueryResult(original_question=question or "", error="Empty question")

        question = question.strip()
        result   = QueryResult(original_question=question)
        result.detected_language = (
            language if language in (LANG_ENGLISH, LANG_ARABIC)
            else detect_language(question)
        )
        is_arabic = result.detected_language == LANG_ARABIC

        # ── Input guard (original text) ───────
        if self._block_if_injection(result, question):
            return result

        # ── Translate Arabic → English ────────
        if is_arabic:
            try:
                result.english_question = self._to_en_chain.invoke(
                    {"arabic_text": question}
                ).strip()
            except Exception as e:
                result.error = f"Translation to English failed: {e}"
                logger.error(result.error)
                return result
            logger.info(f"Translated: {result.english_question}")

            # ── Input guard (translation) ─────
            if self._block_if_injection(result, result.english_question):
                return result
        else:
            result.english_question = question

        # ── Route ─────────────────────────────
        routed = self.router.classify(result.english_question)
        result.complexity = routed.complexity
        chosen = strategy if strategy in STRATEGIES else STRATEGY_FOR_COMPLEXITY[routed.complexity]
        logger.info(
            f"Complexity: {routed.complexity} (conf={routed.confidence}) "
            f"→ strategy={chosen} | {routed.reasoning}"
        )

        # ── Generate + execute ────────────────
        result = self._get_strategy(chosen).run(result.english_question, result)

        # ── Self-correction fallback ──────────
        if (
            allow_fallback
            and not result.execution_success
            and not result.blocked
            and not is_infra_error(result.error)
        ):
            logger.warning(f"{chosen} failed ({result.error}) — trying fallback chain")
            result = self._fallback_with_correction(result)

        # ── Responses ─────────────────────────
        if result.blocked:
            result.natural_response = BLOCKED_RESPONSE_AR if is_arabic else BLOCKED_RESPONSE_EN
        elif is_arabic and result.natural_response:
            result.natural_response = self._translate_to_arabic(result.natural_response)

        return result

    def analyze_batch(self, questions: list) -> list:
        """Run multiple queries sequentially."""
        return [self.query(q) for q in questions]

    # ─────────────────────────────────────────
    # INTERNALS
    # ─────────────────────────────────────────

    def _block_if_injection(self, result: QueryResult, text: str) -> bool:
        ok, reason = self.guard.check_question(text, language=result.detected_language)
        if ok:
            return False
        result.blocked          = True
        result.block_reason     = reason
        result.natural_response = (
            BLOCKED_RESPONSE_AR if result.detected_language == LANG_ARABIC
            else BLOCKED_RESPONSE_EN
        )
        logger.warning(f"Query BLOCKED at input: {reason}")
        return True

    def _get_strategy(self, name: str):
        if name not in self._strategies:
            if name == "simple":
                from src.text_to_sql.chain.simple_chain import SimpleChain as cls
            elif name == "cot":
                from src.text_to_sql.chain.cot_chain import CoTChain as cls
            else:
                from src.text_to_sql.chain.agent_chain import AgentChain as cls
            self._strategies[name] = cls(self.llm, self.schema, self.db_path, self.guard)
        return self._strategies[name]

    def _fallback_with_correction(self, result: QueryResult) -> QueryResult:
        """
        Regenerate SQL with a plain prompt; if that fails, feed the error
        back to the LLM and ask for a fix. Up to MAX_SQL_RETRIES attempts.
        """
        question   = result.english_question
        last_error = result.error or "Unknown error"
        last_sql   = result.generated_sql or ""
        result.fallback_used = True

        for attempt in range(MAX_SQL_RETRIES):
            result.retries_used += 1
            try:
                if attempt == 0:
                    raw = self._fallback_chain.invoke({
                        "schema": self.schema, "question": question,
                    })
                else:
                    raw = self._correct_chain.invoke({
                        "schema": self.schema, "question": question,
                        "failed_sql": last_sql, "error": last_error,
                    })
                result = execute_and_answer(
                    result, clean_sql(raw), self.guard, self.db_path, "fallback",
                    answer_fn=lambda s, rows: self._format_chain.invoke({
                        "question": question, "sql": s, "result": rows,
                    }),
                )
            except Exception as e:          # LLM / network errors
                result.error = str(e)
                logger.warning(f"Fallback attempt {attempt + 1}: LLM error {e}")
                if is_infra_error(result.error):
                    break
                continue

            if result.blocked:
                break
            if result.execution_success:
                logger.info(f"Fallback succeeded on attempt {attempt + 1}")
                break

            last_sql, last_error = result.generated_sql, result.error
            logger.warning(f"Fallback attempt {attempt + 1} failed: {last_error}")

        return result

    def _translate_to_arabic(self, english_text: str) -> str:
        try:
            return self._to_ar_chain.invoke({"english_text": english_text}).strip()
        except Exception as e:
            logger.error(f"Translation to Arabic failed: {e}")
            return english_text
