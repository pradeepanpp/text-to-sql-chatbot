# src/text_to_sql/chain/simple_chain.py
"""
Simple Chain — direct single-step SQL generation.

Used for single-table lookups, basic filters, COUNT/SUM on one table.

Strategy: LLM writes SQL -> SQLGuard checks + executes (read-only)
          -> LLM writes the answer from the rows
LLM calls: 2 (SQL generation + answer formatting)

Examples:
    "How many customers are in the database?"
    "What are all the product names?"
    "Show me orders from the Wholesale channel."
"""

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from src.text_to_sql.chain.common import (
    QueryResult,
    clean_sql,
    execute_and_answer,
)
from src.text_to_sql.utils.logger import logger

STRATEGY = "simple"

SIMPLE_PROMPT = ChatPromptTemplate.from_template("""
You are a SQL expert. Write a SQLite SELECT query to answer the question.

Rules:
- Return ONLY the SQL query, no explanation, no markdown
- Use exact column and table names from the schema
- Keep it simple — one table preferred

Schema:
{schema}

Question: {question}

SQL:""")

SIMPLE_FORMAT_PROMPT = ChatPromptTemplate.from_template("""
Answer this question based on the query result. Be concise and clear.
Do not mention SQL. If empty, say no data was found.

Question: {question}
Result: {result}

Answer:""")


class SimpleChain:
    """Direct single-step SQL chain for simple queries."""

    def __init__(self, llm, schema: str, db_path: str, guard):
        self.schema  = schema
        self.db_path = db_path
        self.guard   = guard
        self._chain  = SIMPLE_PROMPT | llm | StrOutputParser()
        self._format = SIMPLE_FORMAT_PROMPT | llm | StrOutputParser()

    def run(self, question: str, result: QueryResult) -> QueryResult:
        """Generate SQL, execute it through the guard, format the answer."""
        logger.info("[SimpleChain] Running direct SQL generation...")
        result.strategy = STRATEGY

        try:
            raw_sql = self._chain.invoke({
                "schema":   self.schema,
                "question": question,
            })
            sql = clean_sql(raw_sql)

            result = execute_and_answer(
                result, sql, self.guard, self.db_path, STRATEGY,
                answer_fn=lambda _sql, rows: self._format.invoke({
                    "question": question,
                    "result":   rows,
                }),
            )
            if result.execution_success:
                logger.info("[SimpleChain] Success")
            else:
                logger.warning(f"[SimpleChain] Failed: {result.error}")

        except Exception as e:       # LLM / network errors
            result.error = str(e)
            logger.error(f"[SimpleChain] Failed: {e}")

        return result
