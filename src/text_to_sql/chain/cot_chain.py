"""
Chain-of-thought chain, for joins, grouping and rankings.

One LLM call writes its reasoning followed by the SQL, the guard runs the
extracted SQL, and a second call writes the answer.
"""

import re

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from src.text_to_sql.chain.common import QueryResult, clean_sql, execute_and_answer
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

SQL_MARKER = re.compile(r"(?im)^[ \t*#]*(?:final\s+)?sql[ \t*]*:[ \t*]*")  # "SQL:", "**SQL:**", "Final SQL:"
FENCED_SQL = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def extract_sql(output: str) -> str:
    """
    Get the final SQL out of the reasoning text. The SQL often spans several
    lines, so everything after the last marker is taken, not just that line.
    (Taking one line dropped the FROM clause and caused
    "no such column: c.customer_name" in the benchmark.)

    Tried in order: last fenced block, text after the last "SQL:" line,
    text from the last line starting with SELECT/WITH, the whole output.
    """
    text = (output or "").strip()

    blocks = FENCED_SQL.findall(text)
    if blocks:
        return clean_sql(blocks[-1])

    markers = list(SQL_MARKER.finditer(text))
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
    def __init__(self, llm, schema: str, db_path: str, guard):
        self.schema = schema
        self.db_path = db_path
        self.guard = guard
        self.sql_chain = COT_PROMPT | llm | StrOutputParser()
        self.answer_chain = COT_FORMAT_PROMPT | llm | StrOutputParser()

    def run(self, question: str, result: QueryResult) -> QueryResult:
        result.strategy = STRATEGY
        try:
            output = self.sql_chain.invoke({"schema": self.schema, "question": question})
            result = execute_and_answer(
                result, extract_sql(output), self.guard, self.db_path, STRATEGY,
                answer_fn=lambda _sql, rows: self.answer_chain.invoke({"question": question, "result": rows}),
            )
            if not result.execution_success:
                logger.warning(f"CoT chain failed: {result.error}")
        except Exception as e:  # LLM or network error
            result.error = str(e)
            logger.error(f"CoT chain failed: {e}")
        return result
