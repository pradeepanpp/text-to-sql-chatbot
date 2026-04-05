# src/text_to_sql/chain/cot_chain.py
"""
Chain-of-Thought (CoT) Chain — Phase 2.

Step-by-step reasoning before SQL generation for medium queries.
Used for 2-table joins, GROUP BY, rankings, aggregations.

Strategy: reason step-by-step → generate SQL → execute
Speed: medium (~3-5 seconds)
Cost: medium (~200-400 tokens)

Examples:
    "What are the top 5 customers by total sales?"
    "Which product has the highest average order quantity?"
    "Show total sales broken down by channel."
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

COT_PROMPT = ChatPromptTemplate.from_template("""
You are a SQL expert. Think through this step by step, then write the SQL.

Schema:
{schema}

Question: {question}

Think through:
1. Which tables do I need?
2. How do I join them?
3. What aggregation or grouping is needed?
4. What is the final SQL?

After reasoning, output ONLY the final SQL query on the last line,
starting with "SQL:" prefix. No markdown, no backticks.

Reasoning and SQL:""")

COT_FORMAT_PROMPT = ChatPromptTemplate.from_template("""
Answer this question clearly based on the data. Be specific with numbers.
Format nicely if there are multiple rows. Do not mention SQL.

Question: {question}
Data: {result}

Answer:""")


def _extract_sql_from_cot(raw_output: str) -> str:
    """
    Extract the SQL query from CoT output.
    Looks for 'SQL:' prefix on the last meaningful line.
    Falls back to clean_sql on the whole output.
    """
    lines = [l.strip() for l in raw_output.strip().splitlines() if l.strip()]

    # Look for SQL: prefix
    for line in reversed(lines):
        if line.upper().startswith("SQL:"):
            return clean_sql(line[4:].strip())

    # Fallback — take last line that looks like SQL
    for line in reversed(lines):
        if line.upper().startswith("SELECT"):
            return clean_sql(line)

    # Last resort
    return clean_sql(raw_output)


class CoTChain:
    """Chain-of-thought SQL generation for medium complexity queries."""

    def __init__(self, llm: ChatOpenAI, schema: str, db_path: str = DB_PATH):
        self.llm     = llm
        self.schema  = schema
        self.db_path = db_path
        self._chain  = COT_PROMPT  | llm | StrOutputParser()
        self._format = COT_FORMAT_PROMPT | llm | StrOutputParser()

    def run(self, question: str, result: QueryResult) -> QueryResult:
        """
        Run chain-of-thought SQL generation.
        Updates and returns the QueryResult.
        """
        logger.info("[CoTChain] Running chain-of-thought SQL generation...")

        try:
            # Generate with reasoning
            raw_output = self._chain.invoke({
                "schema":   self.schema,
                "question": question,
            })

            # Log the reasoning for debugging
            logger.debug(f"[CoTChain] Reasoning:\n{raw_output[:500]}")

            # Extract just the SQL
            sql = _extract_sql_from_cot(raw_output)

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

            logger.info("[CoTChain] Success")

        except Exception as e:
            result.error = str(e)
            logger.error(f"[CoTChain] Failed: {e}")

        return result

    def _execute(self, sql: str) -> str:
        conn   = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchmany(50)

        if not rows:
            conn.close()
            return "No results found."

        cols  = [d[0] for d in cursor.description]
        lines = [" | ".join(cols), "-" * 40]
        for row in rows:
            lines.append(" | ".join(str(v) for v in row))

        if len(rows) == 50:
            lines.append("(showing first 50 rows)")

        conn.close()
        return "\n".join(lines)