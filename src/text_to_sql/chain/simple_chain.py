"""
Simple chain, for single-table lookups.

One LLM call writes the SQL, the guard runs it, a second call writes the answer.
"""

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from src.text_to_sql.chain.common import QueryResult, clean_sql, execute_and_answer
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
    def __init__(self, llm, schema: str, db_path: str, guard):
        self.schema = schema
        self.db_path = db_path
        self.guard = guard
        self.sql_chain = SIMPLE_PROMPT | llm | StrOutputParser()
        self.answer_chain = SIMPLE_FORMAT_PROMPT | llm | StrOutputParser()

    def run(self, question: str, result: QueryResult) -> QueryResult:
        result.strategy = STRATEGY
        try:
            sql = clean_sql(self.sql_chain.invoke({"schema": self.schema, "question": question}))
            result = execute_and_answer(
                result, sql, self.guard, self.db_path, STRATEGY,
                answer_fn=lambda _sql, rows: self.answer_chain.invoke({"question": question, "result": rows}),
            )
            if not result.execution_success:
                logger.warning(f"Simple chain failed: {result.error}")
        except Exception as e:  # LLM or network error
            result.error = str(e)
            logger.error(f"Simple chain failed: {e}")
        return result
