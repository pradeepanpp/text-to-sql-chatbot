# src/text_to_sql/chain/agent_chain.py
"""
ReAct Agent Chain — Phase 2 (updated with rate limit retry).

LangGraph-powered ReAct agent for complex multi-table queries.
The agent reasons iteratively, choosing tools at each step.

Tools available:
    list_tables    → shows all available table names
    get_schema     → returns schema for specific tables
    run_query      → executes a SQL SELECT query
    check_query    → validates SQL before execution

Strategy: reason → act → observe → repeat → final answer
Speed: slowest (~8-15 seconds)
Cost: highest (~500-1000 tokens)

Rate limit handling:
    - Detects 429 errors automatically
    - Retries up to 3 times with exponential backoff
    - Waits 60s → 120s → 180s between retries
    - Logs wait time clearly so user knows what's happening

Examples:
    "Compare sales vs budget for each product in the South region"
    "Which customers ranked in top 10 for both quantity and revenue?"
    "What percentage of total sales came from each region?"
"""

import os
import re
import time
import sqlite3
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.prebuilt import create_react_agent

from src.text_to_sql.chain.sql_chain import (
    validate_sql_safety,
    QueryResult,
)
from src.text_to_sql.utils.logger import logger

DB_PATH = "database/sales.db"

# ── Rate limit retry settings ─────────────────
MAX_RETRIES       = 3
RETRY_WAIT_BASE   = 120    # seconds — first retry waits 60s
RATE_LIMIT_SIGNAL = "429" # string to detect in error messages

AGENT_SYSTEM_PROMPT = """You are an expert SQL analyst with access to a regional sales database.

Your job: answer questions by querying the database step by step.

RULES:
1. Always check available tables first if unsure
2. Always validate your SQL logic before running
3. Only use SELECT queries — never modify data
4. If a query fails, fix it and try again
5. Give a clear, concise natural language answer at the end

Available tools:
- list_tables: see all table names
- get_schema: get column details for specific tables
- run_query: execute a SELECT SQL query
- check_query: validate your SQL before running it

Work methodically. Think before each tool call."""

FORMAT_PROMPT = ChatPromptTemplate.from_template("""
Given the agent's findings, write a clear final answer to the question.
Be specific with numbers. Do not mention SQL or tools.

Question: {question}
Agent findings: {findings}

Final Answer:""")


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _is_rate_limit_error(error: Exception) -> bool:
    """Check if an exception is an OpenAI rate limit (429) error."""
    return RATE_LIMIT_SIGNAL in str(error)


def _extract_retry_wait(error: Exception) -> int:
    """
    Try to extract the suggested wait time from the rate limit
    error message. Falls back to RETRY_WAIT_BASE if not found.

    OpenAI errors contain text like:
    'Please try again in 760ms' or 'Please try again in 63s'
    """
    error_str = str(error)

    # Look for milliseconds
    ms_match = re.search(r"try again in (\d+)ms", error_str)
    if ms_match:
        ms = int(ms_match.group(1))
        # Round up to nearest second + 5s buffer
        return max(5, (ms // 1000) + 5)

    # Look for seconds
    s_match = re.search(r"try again in (\d+)s", error_str)
    if s_match:
        return int(s_match.group(1)) + 5  # add 5s buffer

    return RETRY_WAIT_BASE


# ─────────────────────────────────────────────
# TOOLS — built with db_path closure
# ─────────────────────────────────────────────

def make_tools(db_path: str):
    """Create tool functions bound to a specific database path."""

    @tool
    def list_tables() -> str:
        """List all available table names in the database."""
        conn   = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return f"Available tables: {', '.join(tables)}"

    @tool
    def get_schema(table_names: str) -> str:
        """
        Get the column schema for one or more tables.
        Pass comma-separated table names, e.g. 'customers,sales_orders'
        """
        conn    = sqlite3.connect(db_path)
        cursor  = conn.cursor()
        tables  = [t.strip() for t in table_names.split(",")]
        results = []

        for table in tables:
            try:
                cursor.execute(f"PRAGMA table_info({table})")
                cols     = cursor.fetchall()
                col_info = ", ".join(f"{c[1]} ({c[2]})" for c in cols)
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                results.append(
                    f"Table '{table}' ({count:,} rows):\n  {col_info}"
                )
            except Exception as e:
                results.append(f"Table '{table}': Error — {e}")

        conn.close()
        return "\n\n".join(results)

    @tool
    def run_query(sql: str) -> str:
        """
        Execute a SELECT SQL query and return results.
        Only SELECT queries are allowed — no data modification.
        """
        is_safe, reason = validate_sql_safety(sql)
        if not is_safe:
            return f"BLOCKED: {reason}"

        try:
            conn   = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(sql)
            rows   = cursor.fetchmany(20)

            if not rows:
                conn.close()
                return "Query executed successfully. No results returned."

            cols  = [d[0] for d in cursor.description]
            lines = [" | ".join(cols), "-" * 40]
            for row in rows:
                lines.append(" | ".join(str(v) for v in row))

            if len(rows) == 20:
                cursor.execute(
                    f"SELECT COUNT(*) FROM ({sql}) AS subq"
                )
                total = cursor.fetchone()[0]
                lines.append(f"(showing 20 of {total:,} total rows)")

            conn.close()
            return "\n".join(lines)

        except Exception as e:
            return f"Query failed: {str(e)}"

    @tool
    def check_query(sql: str) -> str:
        """
        Validate SQL syntax without executing it.
        Use this to check your query before running it.
        """
        is_safe, reason = validate_sql_safety(sql)
        if not is_safe:
            return f"UNSAFE: {reason}"

        try:
            conn   = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(f"EXPLAIN QUERY PLAN {sql}")
            plan = cursor.fetchall()
            conn.close()
            return f"SQL is valid. Query plan has {len(plan)} step(s)."
        except Exception as e:
            return f"SQL has an error: {str(e)}"

    return [list_tables, get_schema, run_query, check_query]


# ─────────────────────────────────────────────
# AGENT CHAIN
# ─────────────────────────────────────────────

class AgentChain:
    """
    LangGraph ReAct agent for complex multi-table queries.

    Improvements over Phase 2 original:
      - Exponential backoff retry on rate limit (429) errors
      - Cleaner SQL extraction from agent messages
      - Better final answer extraction logic
      - Explicit retry logging so user knows what is happening
    """

    def __init__(self, llm: ChatOpenAI, schema: str, db_path: str = DB_PATH):
        self.llm     = llm
        self.schema  = schema
        self.db_path = db_path

        tools        = make_tools(db_path)
        self._agent  = create_react_agent(
            llm,
            tools,
            prompt = AGENT_SYSTEM_PROMPT,
        )
        self._format = FORMAT_PROMPT | llm | StrOutputParser()

    # ─────────────────────────────────────────
    # PUBLIC
    # ─────────────────────────────────────────

    def run(self, question: str, result: QueryResult) -> QueryResult:
        """
        Run ReAct agent with automatic rate limit retry.
        Retries up to MAX_RETRIES times with exponential backoff.
        Updates and returns the QueryResult.
        """
        logger.info("[AgentChain] Running ReAct agent...")

        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):

            try:
                result = self._run_once(question, result)
                if attempt > 1:
                    logger.info(
                        f"[AgentChain] Succeeded on retry {attempt}"
                    )
                return result

            except Exception as e:
                last_error = e

                if _is_rate_limit_error(e):
                    if attempt < MAX_RETRIES:
                        # Exponential backoff
                        wait_s = _extract_retry_wait(e) * attempt
                        logger.warning(
                            f"[AgentChain] Rate limit hit "
                            f"(attempt {attempt}/{MAX_RETRIES}) — "
                            f"waiting {wait_s}s before retry..."
                        )
                        time.sleep(wait_s)
                        continue
                    else:
                        logger.error(
                            f"[AgentChain] Rate limit — "
                            f"all {MAX_RETRIES} retries exhausted"
                        )
                        break
                else:
                    # Non-rate-limit error — no point retrying
                    logger.error(f"[AgentChain] Failed: {e}")
                    break

        result.error = str(last_error)
        return result

    # ─────────────────────────────────────────
    # PRIVATE — SINGLE ATTEMPT
    # ─────────────────────────────────────────

    def _run_once(self, question: str, result: QueryResult) -> QueryResult:
        """
        Run a single agent attempt.
        Raises exception on any failure (caller handles retry).
        """
        events = self._agent.stream(
            {"messages": [("user", question)]},
            stream_mode = "values",
        )

        all_messages = []
        final_sql    = ""

        for event in events:
            msg = event["messages"][-1]
            all_messages.append(msg)

            # Capture any SQL generated by the agent
            content = str(getattr(msg, "content", ""))
            if "SELECT" in content.upper():
                sql_match = re.search(
                    r"SELECT\s+.+?(?:;|$)",
                    content,
                    re.IGNORECASE | re.DOTALL
                )
                if sql_match:
                    candidate = sql_match.group(0).strip().rstrip(";")
                    # Keep the longest SQL found (most complete query)
                    if len(candidate) > len(final_sql):
                        final_sql = candidate

        # Extract final answer — last substantive AI message
        final_answer = self._extract_final_answer(all_messages)

        result.generated_sql     = final_sql or "Multi-step agent query"
        result.sql_valid         = True
        result.execution_success = True
        result.raw_result        = final_answer

        # Format into clean natural language response
        result.natural_response = self._format.invoke({
            "question": question,
            "findings": final_answer,
        }).strip()

        logger.info("[AgentChain] Success")
        return result

    def _extract_final_answer(self, messages: list) -> str:
        """
        Extract the final answer from the agent's message list.

        Looks for the last AI message that:
          - Has non-empty content
          - Is not a tool call request
          - Is longer than 20 characters (not a one-word ack)
        """
        for msg in reversed(messages):
            content = str(getattr(msg, "content", ""))

            # Skip empty messages
            if not content or len(content) < 20:
                continue

            # Skip tool call messages
            msg_type = type(msg).__name__.lower()
            if "tool" in msg_type:
                continue

            # Skip messages that are pure tool invocations
            if "tool_call" in content.lower():
                continue

            return content

        return "Agent completed analysis — see query results above."