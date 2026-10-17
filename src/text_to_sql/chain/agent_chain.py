"""
ReAct agent (LangGraph), for complex multi-table questions.

The agent loops: think, call a tool, read the result, until it can answer.
Tools: list_tables, get_schema, run_query (through the guard) and
check_query (checks + EXPLAIN, no execution).

The tools are built per request and record every query they run, so the
final SQL comes from the tool calls, not from scraping the answer text.
A result counts as success only if a query succeeded and the agent wrote
an answer. The loop is capped, and hitting the cap counts as a failure.
"""

import re
import time

from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from src.text_to_sql.chain.common import QueryResult, is_infra_error
from src.text_to_sql.database.executor import connect_readonly, format_rows
from src.text_to_sql.utils.logger import logger

STRATEGY = "agent"
AGENT_RECURSION_LIMIT = 24  # graph steps; one tool round is 2 steps
MAX_ATTEMPTS = 2            # whole-agent attempts when rate limited
MAX_WAIT_S = 30
ROWS_SHOWN_TO_AGENT = 20
STEP_LIMIT_TEXT = "Sorry, need more steps"  # what LangGraph returns at the step limit

AGENT_SYSTEM_PROMPT = """You are an expert SQL analyst with access to a regional sales database (SQLite).

Your job: answer questions by querying the database step by step.

RULES:
1. Check available tables and their schema before writing SQL
2. Validate complex SQL with check_query before running it
3. Only use SELECT queries — never modify data
4. If a query fails, read the error, fix the query and try again
5. Finish with a clear, concise natural-language answer that includes
   the key numbers. Do not mention SQL or tools in the final answer.

Tools:
- list_tables: see all table names
- get_schema: get column details for specific tables
- run_query: execute a SELECT SQL query
- check_query: validate SQL without running it"""


def retry_wait_seconds(error: Exception) -> int:
    """Wait suggested by an OpenAI rate-limit message ('try again in 760ms' / '6s')."""
    text = str(error)
    ms = re.search(r"try again in (\d+)ms", text)
    if ms:
        return max(1, int(ms.group(1)) // 1000 + 1)
    s = re.search(r"try again in (\d+(?:\.\d+)?)s", text)
    if s:
        return int(float(s.group(1))) + 1
    return 10


def list_db_tables(db_path: str) -> list:
    conn = connect_readonly(db_path)
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]


def make_tools(db_path: str, guard, question: str = "", language: str = "en", executed: list = None) -> list:
    """
    Build the agent's tools for one request. Each run_query call appends
    {"sql", "ok", "blocked", "row_count", "error"} to `executed`.
    """
    executed = executed if executed is not None else []

    @tool
    def list_tables() -> str:
        """List all available table names in the database."""
        return f"Available tables: {', '.join(list_db_tables(db_path))}"

    @tool
    def get_schema(table_names: str) -> str:
        """
        Get the column schema for one or more tables.
        Pass comma-separated table names, e.g. 'customers,sales_orders'
        """
        known = set(list_db_tables(db_path))
        parts = []
        conn = connect_readonly(db_path)
        try:
            for table in [t.strip() for t in table_names.split(",") if t.strip()]:
                if table not in known:  # never put unknown names into SQL
                    parts.append(f"Table '{table}': does not exist")
                    continue
                cols = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
                count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                col_info = ", ".join(f"{c[1]} ({c[2]})" for c in cols)
                parts.append(f"Table '{table}' ({count:,} rows):\n  {col_info}")
        finally:
            conn.close()
        return "\n\n".join(parts)

    @tool
    def run_query(sql: str) -> str:
        """
        Execute a SELECT SQL query and return results.
        Only SELECT queries are allowed — no data modification.
        """
        run = guard.execute(sql, db_path=db_path, question=question, language=language, strategy=STRATEGY)
        executed.append({
            "sql": run.sql,
            "ok": run.ok,
            "blocked": run.blocked,
            "row_count": run.result.row_count if run.ok else 0,
            "error": run.block_reason or run.error,
        })
        if run.blocked:
            return f"BLOCKED: {run.block_reason}"
        if not run.ok:
            return f"Query failed: {run.error}"
        if not run.result.rows:
            return "Query executed successfully. No results returned."
        return format_rows(run.result, ROWS_SHOWN_TO_AGENT)

    @tool
    def check_query(sql: str) -> str:
        """
        Validate SQL without executing it.
        Use this to check your query before running it.
        """
        report = guard.inspect_sql(sql)
        if not report.passed:
            return f"UNSAFE: {report.reason}"
        conn = connect_readonly(db_path)
        try:
            plan = conn.execute(f"EXPLAIN QUERY PLAN {report.sanitized_sql}").fetchall()
            return f"SQL is valid. Query plan has {len(plan)} step(s)."
        except Exception as e:
            return f"SQL has an error: {e}"
        finally:
            conn.close()

    return [list_tables, get_schema, run_query, check_query]


def final_answer(messages: list) -> str:
    """Text of the last AI message that does not call a tool."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            if content.strip():
                return content.strip()
    return ""


class AgentChain:
    def __init__(self, llm, schema: str, db_path: str, guard):
        self.llm = llm
        self.schema = schema
        self.db_path = db_path
        self.guard = guard

    def run(self, question: str, result: QueryResult) -> QueryResult:
        """Run the agent. Only rate-limit errors are retried, with a capped wait."""
        result.strategy = STRATEGY
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return self.run_once(question, result)
            except Exception as e:
                result.error = str(e)
                if is_infra_error(result.error) and attempt < MAX_ATTEMPTS:
                    wait = min(retry_wait_seconds(e) * attempt, MAX_WAIT_S)
                    logger.warning(f"Agent rate limited (attempt {attempt}/{MAX_ATTEMPTS}), waiting {wait}s")
                    time.sleep(wait)
                    continue
                logger.error(f"Agent failed: {e}")
                break

        result.execution_success = False
        return result

    def run_once(self, question: str, result: QueryResult) -> QueryResult:
        executed = []
        tools = make_tools(self.db_path, self.guard, question=result.original_question,
                           language=result.detected_language, executed=executed)
        # Same schema context as the other strategies (descriptions, joins,
        # allowed values); without it the agent guesses joins from PRAGMA.
        agent = create_react_agent(self.llm, tools, prompt=f"{AGENT_SYSTEM_PROMPT}\n\n{self.schema}")
        state = agent.invoke({"messages": [("user", question)]},
                             config={"recursion_limit": AGENT_RECURSION_LIMIT})

        answer = final_answer(state["messages"])
        if answer.startswith(STEP_LIMIT_TEXT):
            answer = ""
        successful = [q for q in executed if q["ok"]]

        result.agent_queries = [q["sql"] for q in executed]
        if successful:
            result.generated_sql = successful[-1]["sql"]
            result.row_count = successful[-1]["row_count"]
            result.sql_valid = True
        elif executed:
            result.generated_sql = executed[-1]["sql"]

        if executed and all(q["blocked"] for q in executed):
            result.blocked = True
            result.block_reason = executed[-1]["error"]

        result.execution_success = bool(successful) and bool(answer)
        result.raw_result = answer
        result.natural_response = answer if result.execution_success else ""

        if result.execution_success:
            result.error = None
        else:
            if executed:
                result.error = executed[-1]["error"] or "Agent finished without a final answer"
            else:
                result.error = "Agent finished without running a successful query"
            logger.warning(f"Agent had no successful query: {result.error}")
        return result
