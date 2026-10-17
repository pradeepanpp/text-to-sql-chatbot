# src/text_to_sql/chain/cot_chain.py
"""
Chain-of-Thought (CoT) Chain — reason step by step, then write SQL.

Used for 2-table joins, GROUP BY, rankings, aggregations.

Strategy: one LLM call that writes its reasoning and then the final SQL
          -> extract the SQL -> SQLGuard checks + executes (read-only)
          -> LLM writes the answer from the rows
LLM calls: 2 (reasoning + SQL in one call, answer formatting)

Examples:
    "What are the top 5 customers by total sales?"
    "Which product has the highest average order quantity?"
    "Show total sales broken down by channel."
"""

import re

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from src.text_to_sql.chain.common import (
    QueryResult,
    clean_sql,
    execute_and_answer,
)
from src.text_to_sql.utils.logger import logger

STRATEGY = "cot"

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

After your reasoning, write a line that says exactly "SQL:" and put the
final SQLite query after it. The query may span several lines. Write
nothing after the query. No markdown, no backticks.

Reasoning and SQL:""")

COT_FORMAT_PROMPT = ChatPromptTemplate.from_template("""
Answer this question clearly based on the data. Be specific with numbers.
Format nicely if there are multiple rows. Do not mention SQL.

Question: {question}
Data: {result}

Answer:""")

# A line that starts the final SQL, e.g. "SQL:", "**SQL:**", "Final SQL:"
_SQL_MARKER = re.compile(r"(?im)^[ \t*#]*(?:final\s+)?sql[ \t*]*:[ \t*]*")
_FENCED     = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def _extract_sql_from_cot(raw_output: str) -> str:
    """
    Extract the final SQL query from CoT output.

    The SQL usually spans several lines, so we take everything AFTER the
    last marker, not just the marker line. (Taking only the marker line
    turned "SQL: SELECT c.customer_name ...\\nFROM ..." into a query with
    no FROM clause, which SQLite rejects with
    "no such column: c.customer_name".)

    Order of attempts:
      1. last ```sql fenced block
      2. text after the last "SQL:" marker line
      3. text from the last line that starts with SELECT / WITH
      4. the whole output
    """
    text = (raw_output or "").strip()

    blocks = _FENCED.findall(text)
    if blocks:
        return clean_sql(blocks[-1])

    markers = list(_SQL_MARKER.finditer(text))
    if markers:
        tail = text[markers[-1].end():].strip()
        if tail:
            return clean_sql(tail)

    lines = text.splitlines()
    for i in range(len(lines) - 1, -1, -1):
        if re.match(r"^\s*(SELECT|WITH)\b", lines[i], re.IGNORECASE):
            return clean_sql("\n".join(lines[i:]))

    return clean_sql(text)


class CoTChain:
    """Chain-of-thought SQL generation for medium complexity queries."""

    def __init__(self, llm, schema: str, db_path: str, guard):
        self.schema  = schema
        self.db_path = db_path
        self.guard   = guard
        self._chain  = COT_PROMPT | llm | StrOutputParser()
        self._format = COT_FORMAT_PROMPT | llm | StrOutputParser()

    def run(self, question: str, result: QueryResult) -> QueryResult:
        """Reason, extract SQL, execute through the guard, format the answer."""
        logger.info("[CoTChain] Running chain-of-thought SQL generation...")
        result.strategy = STRATEGY

        try:
            raw_output = self._chain.invoke({
                "schema":   self.schema,
                "question": question,
            })
            logger.debug(f"[CoTChain] Reasoning:\n{raw_output[:500]}")

            sql = _extract_sql_from_cot(raw_output)

            result = execute_and_answer(
                result, sql, self.guard, self.db_path, STRATEGY,
                answer_fn=lambda _sql, rows: self._format.invoke({
                    "question": question,
                    "result":   rows,
                }),
            )
            if result.execution_success:
                logger.info("[CoTChain] Success")
            else:
                logger.warning(f"[CoTChain] Failed: {result.error}")

        except Exception as e:       # LLM / network errors
            result.error = str(e)
            logger.error(f"[CoTChain] Failed: {e}")

        return result
