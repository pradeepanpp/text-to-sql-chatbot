# src/text_to_sql/api/routes.py
"""
FastAPI route handlers.

Endpoints:
    POST /query           → single natural language query
    POST /query/batch     → batch queries (up to 20)
    GET  /schema          → database schema browser
    GET  /health          → system health check
    GET  /audit/stats     → audit log statistics
    GET  /benchmark       → latest benchmark summary (if one has been run)
    GET  /                → welcome + docs link

Why the handlers are plain `def`, not `async def`:
the pipeline makes blocking calls (OpenAI over HTTP, SQLite). Inside an
`async def` those would block the event loop, so one slow agent query
would freeze every other request. FastAPI runs plain `def` handlers in a
thread pool, so requests are served concurrently.
"""

import json
import os
import threading

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from src.text_to_sql.api.schemas import (
    QueryRequest,
    QueryResponse,
    BatchQueryRequest,
    BatchQueryResponse,
    SchemaResponse,
    SchemaTableInfo,
    HealthResponse,
    AuditStatsResponse,
)
from src.text_to_sql.chain.common import QueryResult
from src.text_to_sql.database.executor import connect_readonly
from src.text_to_sql.safety.sql_guard import get_audit_stats
from src.text_to_sql.constants import TABLE_DESCRIPTIONS
from src.text_to_sql.utils.logger import logger

router = APIRouter()

DEFAULT_DB_PATH   = os.getenv("DB_PATH", "database/sales.db")
BENCHMARK_RESULTS = "data/eval/benchmark_results.json"

_stats_lock = threading.Lock()


# ─────────────────────────────────────────────
# DEPENDENCIES
# ─────────────────────────────────────────────

def get_chain(request: Request):
    """Pull shared TextToSQLChain from app state."""
    chain = request.app.state.chain
    if chain is None:
        raise HTTPException(status_code=503, detail="Chain not initialized")
    return chain


def get_stats_counter(request: Request) -> dict:
    """Pull session stats counter from app state."""
    return request.app.state.stats


def _db_path(request: Request) -> str:
    chain = getattr(request.app.state, "chain", None)
    return getattr(chain, "db_path", None) or DEFAULT_DB_PATH


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def result_to_response(result: QueryResult) -> QueryResponse:
    """Convert QueryResult dataclass → QueryResponse Pydantic model."""
    return QueryResponse(
        question          = result.original_question,
        detected_language = result.detected_language,
        complexity        = result.complexity,
        strategy          = result.strategy,
        generated_sql     = result.generated_sql or "",
        natural_response  = result.natural_response or "",
        execution_success = result.execution_success,
        row_count         = result.row_count,
        blocked           = result.blocked,
        block_reason      = result.block_reason or "",
        fallback_used     = result.fallback_used,
        retries_used      = result.retries_used,
    )


def update_stats(stats: dict, result: QueryResult):
    """Increment session counters (thread-safe)."""
    with _stats_lock:
        stats["total"] += 1
        if result.blocked:
            stats["blocked"] += 1
        elif result.execution_success:
            stats["success"] += 1
        else:
            stats["failed"] += 1


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@router.get("/", tags=["info"])
def root():
    """Welcome message with API information."""
    return {
        "name":        "Text-to-SQL API",
        "version":     "1.1.0",
        "description": "Bilingual Arabic-English Text-to-SQL with safety layer",
        "docs":        "/docs",
        "health":      "/health",
        "endpoints": {
            "query":       "POST /query",
            "batch":       "POST /query/batch",
            "schema":      "GET  /schema",
            "health":      "GET  /health",
            "audit_stats": "GET  /audit/stats",
            "benchmark":   "GET  /benchmark",
        },
    }


@router.post(
    "/query",
    response_model = QueryResponse,
    tags           = ["query"],
    summary        = "Ask a question in English or Arabic",
    responses      = {
        200: {"description": "Query processed"},
        422: {"description": "Validation error — blank or too long"},
        503: {"description": "Chain not initialized"},
    },
)
def query(
    body:  QueryRequest,
    chain  = Depends(get_chain),
    stats  = Depends(get_stats_counter),
):
    """
    Submit a natural language question and receive a SQL-backed answer.

    - Supports **English and Arabic** questions (`language` overrides detection)
    - Routes to Simple / Chain-of-Thought / ReAct agent based on complexity
    - Blocked if prompt injection or unsafe SQL is detected
    - Every SQL execution is written to the audit log
    """
    try:
        result = chain.query(body.question, language=body.language)
    except Exception as e:
        logger.error(f"[/query] Error: {e}")
        raise HTTPException(status_code=500, detail="Query processing failed")

    update_stats(stats, result)
    logger.info(
        f"[/query] lang={result.detected_language} strategy={result.strategy} "
        f"blocked={result.blocked} success={result.execution_success}"
    )
    return result_to_response(result)


@router.post(
    "/query/batch",
    response_model = BatchQueryResponse,
    tags           = ["query"],
    summary        = "Submit multiple questions at once (max 20)",
)
def query_batch(
    body:  BatchQueryRequest,
    chain  = Depends(get_chain),
    stats  = Depends(get_stats_counter),
):
    """
    Submit up to 20 questions in a single request (processed sequentially).
    Returns individual results for each question plus a summary.
    """
    try:
        results = chain.analyze_batch(body.questions)
    except Exception as e:
        logger.error(f"[/query/batch] Error: {e}")
        raise HTTPException(status_code=500, detail="Batch processing failed")

    complexity_dist = {"simple": 0, "medium": 0, "complex": 0}
    for r in results:
        if r.complexity in complexity_dist:
            complexity_dist[r.complexity] += 1
        update_stats(stats, r)

    return BatchQueryResponse(
        results       = [result_to_response(r) for r in results],
        total         = len(results),
        success_count = sum(1 for r in results if r.execution_success and not r.blocked),
        blocked_count = sum(1 for r in results if r.blocked),
        summary       = complexity_dist,
    )


@router.get(
    "/schema",
    response_model = SchemaResponse,
    tags           = ["database"],
    summary        = "Browse the database schema",
)
def schema(request: Request):
    """
    Returns all tables with column names, row counts and descriptions.
    """
    try:
        conn = connect_readonly(_db_path(request))
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    try:
        names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()]

        tables, total_rows = [], 0
        for name in names:
            columns   = [r[1] for r in conn.execute(f'PRAGMA table_info("{name}")').fetchall()]
            row_count = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            total_rows += row_count
            tables.append(SchemaTableInfo(
                name        = name,
                row_count   = row_count,
                columns     = columns,
                description = TABLE_DESCRIPTIONS.get(name, ""),
            ))
    finally:
        conn.close()

    return SchemaResponse(tables=tables, total_tables=len(tables), total_rows=total_rows)


@router.get(
    "/health",
    response_model = HealthResponse,
    tags           = ["system"],
    summary        = "System health check",
    responses      = {503: {"description": "Degraded: a component is unavailable"}},
)
def health(request: Request, response: Response):
    """
    - **200 ok**: chain loaded, guard active, database readable
    - **503 degraded**: one or more components unavailable

    Returning 503 (not 200) when degraded lets Docker's healthcheck and
    load balancers take an unhealthy instance out of service.
    """
    chain    = request.app.state.chain
    chain_ok = chain is not None
    guard_ok = chain_ok and getattr(chain, "guard", None) is not None

    db_ok = False
    try:                                  # read-only: never creates an empty DB
        conn = connect_readonly(_db_path(request))
        conn.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchall()
        conn.close()
        db_ok = True
    except Exception:
        pass

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if chain_ok:
        model = getattr(chain.llm, "model_name", model)

    healthy = chain_ok and guard_ok and db_ok
    if not healthy:
        response.status_code = 503

    return HealthResponse(
        status       = "ok" if healthy else "degraded",
        chain_loaded = chain_ok,
        guard_active = guard_ok,
        db_connected = db_ok,
        model        = model,
    )


@router.get(
    "/audit/stats",
    response_model = AuditStatsResponse,
    tags           = ["system"],
    summary        = "Audit log statistics",
)
def audit_stats():
    """Counts from the audit log: events, blocked, suspicious, by language."""
    stats = get_audit_stats()
    return AuditStatsResponse(
        total       = stats.get("total", 0),
        blocked     = stats.get("blocked", 0),
        suspicious  = stats.get("suspicious", 0),
        block_rate  = stats.get("block_rate", 0.0),
        by_language = stats.get("by_language", {}),
    )


@router.get("/benchmark", tags=["system"], summary="Latest benchmark summary")
def benchmark_summary():
    """
    Headline numbers from the most recent `scripts/run_benchmark.py` run.
    Returns 404 until a benchmark has been run, so no number is ever
    shown that the code did not produce.
    """
    if not os.path.exists(BENCHMARK_RESULTS):
        raise HTTPException(status_code=404, detail="No benchmark has been run yet")
    with open(BENCHMARK_RESULTS, encoding="utf-8") as f:
        report = json.load(f)
    return {k: report.get(k) for k in
            ("meta", "overall", "by_complexity", "by_language", "router", "latency")}
