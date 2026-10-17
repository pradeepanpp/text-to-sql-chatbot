# src/text_to_sql/chain/agent_chain.py
"""
ReAct Agent Chain — LangGraph agent for complex multi-table queries.

The agent loops: reason -> call a tool -> read the result -> repeat,
until it can answer.

Tools:
    list_tables  → table names
    get_schema   → columns + row count for named tables
    run_query    → run a SELECT through SQLGuard (read-only, audited)
    check_query  → policy check + EXPLAIN QUERY PLAN, no execution

Bookkeeping (what makes the result trustworthy):
  - Tools are built per request, so each request records its own list
    of executed SQL. The final `generated_sql` is the last query that
    ran successfully — read from tool calls, not regex-scraped from text.
  - execution_success is True only if at least one query succeeded and
    the agent produced a final answer.
  - The loop is capped (AGENT_RECURSION_LIMIT) so a confused agent
    cannot spin forever. Hitting the cap counts as a failure, not an answer.

LLM calls: one per reasoning step (typically 3–8).
"""

import re
import time

from langchain_core.messages import AIMessage
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool

from src.text_to_sql.chain.common import QueryResult, is_infra_error
from src.text_to_sql.database.executor import connect_readonly, format_rows
from src.text_to_sql.utils.logger import logger

STRATEGY = "agent"

# ── Loop and retry limits ─────────────────────
AGENT_RECURSION_LIMIT = 24   # graph steps; one tool round = 2 steps → ~11 tool calls
MAX_ATTEMPTS          = 2    # whole-agent attempts on rate limit (429)
MAX_WAIT_S            = 30   # cap on backoff so an API request never hangs for minutes
ROWS_SHOWN_TO_AGENT   = 20

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


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _extract_retry_wait(error: Exception) -> int:
    """
    Read the suggested wait from an OpenAI rate-limit message, e.g.
    'Please try again in 760ms' or 'Please try again in 6s'.
    """
    text = str(error)
    ms = re.search(r"try again in (\d+)ms", text)
    if ms:
        return max(1, int(ms.group(1)) // 1000 + 1)
    s = re.search(r"try again in (\d+(?:\.\d+)?)s", text)
    if s:
        return int(float(s.group(1))) + 1
    return 10


def _list_table_names(db_path: str) -> list:
    conn = connect_readonly(db_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]


def make_tools(db_path: str, guard, question: str = "", language: str = "en",
               executed: list = None) -> list:
    """
    Build the agent's tools for ONE request.

    `executed` collects one dict per run_query call:
        {"sql", "ok", "blocked", "row_count", "error"}
    """
    executed = executed if executed is not None else []

    @tool
    def list_tables() -> str:
        """List all available table names in the database."""
        return f"Available tables: {', '.join(_list_table_names(db_path))}"

    @tool
    def get_schema(table_names: str) -> str:
        """
        Get the column schema for one or more tables.
        Pass comma-separated table names, e.g. 'customers,sales_orders'
        """
        known   = set(_list_table_names(db_path))
        tables  = [t.strip() for t in table_names.split(",") if t.strip()]
        results = []
        conn    = connect_readonly(db_path)
        try:
            for table in tables:
                if table not in known:      # never interpolate unknown names into SQL
                    results.append(f"Table '{table}': does not exist")
                    continue
                cols     = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
                col_info = ", ".join(f"{c[1]} ({c[2]})" for c in cols)
                count    = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                results.append(f"Table '{table}' ({count:,} rows):\n  {col_info}")
        finally:
            conn.close()
        return "\n\n".join(results)

    @tool
    def run_query(sql: str) -> str:
        """
        Execute a SELECT SQL query and return results.
        Only SELECT queries are allowed — no data modification.
        """
        run = guard.execute(
            sql, db_path=db_path, question=question,
            language=language, strategy=STRATEGY,
        )
        executed.append({
            "sql":       run.sql,
            "ok":        run.ok,
            "blocked":   run.blocked,
            "row_count": run.result.row_count if run.ok else 0,
            "error":     run.block_reason or run.error,
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


def _final_answer(messages: list) -> str:
    """Last AI message that has text and does not request a tool call."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            if content.strip():
                return content.strip()
    return ""


# ─────────────────────────────────────────────
# AGENT CHAIN
# ─────────────────────────────────────────────

class AgentChain:
    """LangGraph ReAct agent for complex multi-table queries."""

    def __init__(self, llm, schema: str, db_path: str, guard):
        self.llm     = llm
        self.schema  = schema
        self.db_path = db_path
        self.guard   = guard

    def run(self, question: str, result: QueryResult) -> QueryResult:
        """Run the agent, retrying only on rate-limit errors (capped backoff)."""
        logger.info("[AgentChain] Running ReAct agent...")
        result.strategy = STRATEGY

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return self._run_once(question, result)
            except Exception as e:
                result.error = str(e)
                if is_infra_error(result.error) and attempt < MAX_ATTEMPTS:
                    wait_s = min(_extract_retry_wait(e) * attempt, MAX_WAIT_S)
                    logger.warning(
                        f"[AgentChain] Rate limit (attempt {attempt}/{MAX_ATTEMPTS}) "
                        f"— waiting {wait_s}s"
                    )
                    time.sleep(wait_s)
                    continue
                logger.error(f"[AgentChain] Failed: {e}")
                break

        result.execution_success = False
        return result

    def _run_once(self, question: str, result: QueryResult) -> QueryResult:
        executed = []
        tools = make_tools(
            self.db_path, self.guard,
            question = result.original_question,
            language = result.detected_language,
            executed = executed,
        )
                # Give the agent the same schema context the other strategies get
        # (descriptions, foreign keys, allowed values). Without it the agent
        # only sees raw column names from PRAGMA and guesses joins.
        prompt = f"{AGENT_SYSTEM_PROMPT}\n\n{self.schema}"
        agent  = create_react_agent(self.llm, tools, prompt=prompt)
       

        state = agent.invoke(
            {"messages": [("user", question)]},
            config={"recursion_limit": AGENT_RECURSION_LIMIT},
        )
        answer     = _final_answer(state["messages"])
        # LangGraph returns this text when the step limit is hit — not a real answer
        if answer.startswith("Sorry, need more steps"):
            answer = ""
        successful = [q for q in executed if q["ok"]]

        result.agent_queries = [q["sql"] for q in executed]
        if successful:
            last = successful[-1]
            result.generated_sql = last["sql"]
            result.row_count     = last["row_count"]
            result.sql_valid     = True
        elif executed:
            result.generated_sql = executed[-1]["sql"]

        if executed and all(q["blocked"] for q in executed):
            result.blocked      = True
            result.block_reason = executed[-1]["error"]

        result.execution_success = bool(successful) and bool(answer)
        result.raw_result        = answer
        result.natural_response  = answer if result.execution_success else ""

        if result.execution_success:
            result.error = None
            logger.info(
                f"[AgentChain] Success — {len(executed)} queries, "
                f"{len(successful)} succeeded"
            )
        else:
            result.error = (
                executed[-1]["error"] if executed
                else "Agent finished without running a successful query"
            ) or "Agent finished without a final answer"
            logger.warning(f"[AgentChain] No successful query: {result.error}")

        return result