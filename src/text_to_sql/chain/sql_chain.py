"""
Text-to-SQL pipeline.

For one question:
  1. Detect the language (Arabic or English).
  2. Input guard on the question, before any LLM call.
  3. Arabic only: translate to English, then run the input guard on the
     translation (catches injections the Arabic patterns miss).
  4. The router picks a strategy: simple, chain-of-thought or agent.
  5. The strategy writes SQL; SQLGuard.execute() checks it, adds the row
     limit and runs it read-only. Every execution is audited.
  6. On a SQL error (not a block, not a rate limit) the fallback writes new
     SQL and fixes it with the error message, up to MAX_SQL_RETRIES times.
  7. Arabic only: translate the answer back.

SQL is never executed outside SQLGuard.execute().
"""

import os

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

load_dotenv()

from src.text_to_sql.chain.common import QueryResult, clean_sql, execute_and_answer, is_infra_error
from src.text_to_sql.chain.complexity_router import ComplexityRouter
from src.text_to_sql.constants import (
    COMPLEXITY_COMPLEX, COMPLEXITY_MEDIUM, COMPLEXITY_SIMPLE, LANG_ARABIC, LANG_ENGLISH, MAX_SQL_RETRIES,
)
from src.text_to_sql.database.schema import build_schema_context
from src.text_to_sql.language.detector import detect_language
from src.text_to_sql.safety.sql_guard import SQLGuard
from src.text_to_sql.utils.logger import logger

DB_PATH = os.getenv("DB_PATH", "database/sales.db")

STRATEGY_FOR_COMPLEXITY = {
    COMPLEXITY_SIMPLE: "simple",
    COMPLEXITY_MEDIUM: "cot",
    COMPLEXITY_COMPLEX: "agent",
}
STRATEGIES = ("simple", "cot", "agent")

BLOCKED_RESPONSE_AR = "عذراً، لا يمكن معالجة هذا الطلب لأسباب أمنية."
BLOCKED_RESPONSE_EN = "This request has been blocked for security reasons."

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


class TextToSQLChain:
    """
    chain = TextToSQLChain()
    result = chain.query("Top 5 customers by revenue?")

    Tests pass any LangChain chat model as `llm`.
    """

    def __init__(self, db_path: str = DB_PATH, model: str = "gpt-4o-mini", temperature: float = 0.0,
                 max_tokens: int = 500, row_limit: int = 500, llm=None, guard: SQLGuard = None):
        self.db_path = db_path
        self.llm = llm or ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=60,
            max_retries=2,
            api_key=os.getenv("OPENAI_API_KEY"),
        )
        self.schema = build_schema_context(db_path)
        self.router = ComplexityRouter()
        self.guard = guard or SQLGuard(row_limit=row_limit, enable_audit=True)

        self.fallback_chain = FALLBACK_SQL_PROMPT | self.llm | StrOutputParser()
        self.correct_chain = FALLBACK_CORRECT_PROMPT | self.llm | StrOutputParser()
        self.format_chain = FORMAT_PROMPT | self.llm | StrOutputParser()
        self.to_english = TRANSLATE_TO_EN | self.llm | StrOutputParser()
        self.to_arabic = TRANSLATE_TO_AR | self.llm | StrOutputParser()
        self.strategies = {}  # created on first use

    def query(self, question: str, language: str = None, strategy: str = None,
              allow_fallback: bool = True) -> QueryResult:
        """
        Answer one question.

        language: 'en' or 'ar' to skip detection.
        strategy: 'simple', 'cot' or 'agent' to bypass the router (ablation runs).
        allow_fallback: False measures a strategy on its own.
        Check result.blocked before using result.natural_response.
        """
        if not question or not question.strip():
            return QueryResult(original_question=question or "", error="Empty question")

        question = question.strip()
        result = QueryResult(original_question=question)
        if language in (LANG_ENGLISH, LANG_ARABIC):
            result.detected_language = language
        else:
            result.detected_language = detect_language(question)
        is_arabic = result.detected_language == LANG_ARABIC

        if self.block_if_injection(result, question):
            return result

        if is_arabic:
            try:
                result.english_question = self.to_english.invoke({"arabic_text": question}).strip()
            except Exception as e:
                result.error = f"Translation to English failed: {e}"
                logger.error(result.error)
                return result
            logger.info(f"Translated: {result.english_question}")
            if self.block_if_injection(result, result.english_question):
                return result
        else:
            result.english_question = question

        routed = self.router.classify(result.english_question)
        result.complexity = routed.complexity
        chosen = strategy if strategy in STRATEGIES else STRATEGY_FOR_COMPLEXITY[routed.complexity]
        logger.info(f"Complexity {routed.complexity} -> strategy {chosen} ({routed.reasoning})")

        result = self.get_strategy(chosen).run(result.english_question, result)

        sql_failed = not result.execution_success and not result.blocked and not is_infra_error(result.error)
        if allow_fallback and sql_failed:
            logger.warning(f"{chosen} failed ({result.error}), trying the fallback")
            result = self.fallback_with_correction(result)

        if result.blocked:
            result.natural_response = BLOCKED_RESPONSE_AR if is_arabic else BLOCKED_RESPONSE_EN
        elif is_arabic and result.natural_response:
            result.natural_response = self.translate_to_arabic(result.natural_response)
        return result

    def analyze_batch(self, questions: list) -> list:
        return [self.query(q) for q in questions]

    def block_if_injection(self, result: QueryResult, text: str) -> bool:
        ok, reason = self.guard.check_question(text, language=result.detected_language)
        if ok:
            return False
        result.blocked = True
        result.block_reason = reason
        if result.detected_language == LANG_ARABIC:
            result.natural_response = BLOCKED_RESPONSE_AR
        else:
            result.natural_response = BLOCKED_RESPONSE_EN
        return True

    def get_strategy(self, name: str):
        if name not in self.strategies:
            if name == "simple":
                from src.text_to_sql.chain.simple_chain import SimpleChain as cls
            elif name == "cot":
                from src.text_to_sql.chain.cot_chain import CoTChain as cls
            else:
                from src.text_to_sql.chain.agent_chain import AgentChain as cls
            self.strategies[name] = cls(self.llm, self.schema, self.db_path, self.guard)
        return self.strategies[name]

    def fallback_with_correction(self, result: QueryResult) -> QueryResult:
        """
        Write new SQL with a plain prompt; if that fails, send the error back
        to the LLM and ask for a fix. Up to MAX_SQL_RETRIES attempts.
        """
        question = result.english_question
        last_error = result.error or "Unknown error"
        last_sql = result.generated_sql or ""
        result.fallback_used = True

        for attempt in range(MAX_SQL_RETRIES):
            result.retries_used += 1
            try:
                if attempt == 0:
                    raw = self.fallback_chain.invoke({"schema": self.schema, "question": question})
                else:
                    raw = self.correct_chain.invoke({"schema": self.schema, "question": question,
                                                     "failed_sql": last_sql, "error": last_error})
                result = execute_and_answer(
                    result, clean_sql(raw), self.guard, self.db_path, "fallback",
                    answer_fn=lambda sql, rows: self.format_chain.invoke(
                        {"question": question, "sql": sql, "result": rows}),
                )
            except Exception as e:  # LLM or network error
                result.error = str(e)
                logger.warning(f"Fallback attempt {attempt + 1}: LLM error {e}")
                if is_infra_error(result.error):
                    break
                continue

            if result.blocked or result.execution_success:
                break
            last_sql, last_error = result.generated_sql, result.error
            logger.warning(f"Fallback attempt {attempt + 1} failed: {last_error}")

        return result

    def translate_to_arabic(self, english_text: str) -> str:
        try:
            return self.to_arabic.invoke({"english_text": english_text}).strip()
        except Exception as e:
            logger.error(f"Translation to Arabic failed: {e}")
            return english_text
