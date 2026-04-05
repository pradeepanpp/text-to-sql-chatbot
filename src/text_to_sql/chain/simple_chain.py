# src/text_to_sql/chain/simple_chain.py
"""
Simple Chain — Phase 2.

Direct single-step SQL generation for simple queries.
Single table, basic filters, COUNT/SUM on one table.

Strategy: one LLM call → SQL → execute
Speed: fastest (~1-2 seconds)
Cost: lowest (~50-100 tokens)

Examples:
    "How many customers are in the database?"
    "What are all the product names?"
    "Show me orders from the Wholesale channel."
"""

import os
import sqlite3
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from src.text_to_sql.chain.sql_chain import (
    clean_sql,
    validate_sql_safety,
    QueryResult,
)
from src.text_to_sql.utils.logger import logger

DB_PATH = "database/sales.db"

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

    def __init__(self, llm: ChatOpenAI, schema: str, db_path: str = DB_PATH):
        self.llm     = llm
        self.schema  = schema
        self.db_path = db_path
        self._chain  = SIMPLE_PROMPT | llm | StrOutputParser()
        self._format = SIMPLE_FORMAT_PROMPT | llm | StrOutputParser()

    def run(self, question: str, result: QueryResult) -> QueryResult:
        """
        Run simple direct chain.
        Updates and returns the QueryResult.
        """
        logger.info("[SimpleChain] Running direct SQL generation...")

        try:
            # Generate SQL
            raw_sql = self._chain.invoke({
                "schema":   self.schema,
                "question": question,
            })
            sql = clean_sql(raw_sql)

            # Safety check
            is_safe, reason = validate_sql_safety(sql)
            if not is_safe:
                result.sql_valid = False
                result.error     = reason
                return result

            result.generated_sql = sql
            result.sql_valid     = True

            # Execute
            db_result = self._execute(sql)
            result.raw_result        = db_result
            result.execution_success = True

            # Format response
            result.natural_response = self._format.invoke({
                "question": question,
                "result":   db_result,
            }).strip()

            logger.info("[SimpleChain] Success")

        except Exception as e:
            result.error = str(e)
            logger.error(f"[SimpleChain] Failed: {e}")

        return result

    def _execute(self, sql: str) -> str:
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