"""
API routes.

Handlers are plain `def`, not `async def`: the pipeline makes blocking
calls (OpenAI, SQLite), and FastAPI runs plain handlers in a thread pool,
so one slow agent query does not freeze the other requests.
"""

import json
import os
import threading

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from src.text_to_sql.api.schemas import (
    AuditStatsResponse, BatchQueryRequest, BatchQueryResponse, HealthResponse,
    QueryRequest, QueryResponse, SchemaResponse, SchemaTableInfo,
)
from src.text_to_sql.chain.common import QueryResult
from src.text_to_sql.constants import TABLE_DESCRIPTIONS
from src.text_to_sql.database.executor import connect_readonly
from src.text_to_sql.safety.sql_guard import get_audit_stats
from src.text_to_sql.utils.logger import logger

router = APIRouter()

DEFAULT_DB_PATH = os.getenv("DB_PATH", "database/sales.db")
BENCHMARK_RESULTS = "data/eval/benchmark_results.json"

stats_lock = threading.Lock()


def get_chain(request: Request):
    chain = request.app.state.chain
    if chain is None:
        raise HTTPException(status_code=503, detail="Chain not initialized")
    return chain


def get_counters(request: Request) -> dict:
    return request.app.state.stats


def db_path(request: Request) -> str:
    chain = getattr(request.app.state, "chain", None)
    return getattr(chain, "db_path", None) or DEFAULT_DB_PATH


def to_response(result: QueryResult) -> QueryResponse:
    return QueryResponse(
        question=result.original_question,
        detected_language=result.detected_language,
        complexity=result.complexity,
        strategy=result.strategy,
        generated_sql=result.generated_sql or "",
        natural_response=result.natural_response or "",
        execution_success=result.execution_success,
        row_count=result.row_count,
        blocked=result.blocked,
        block_reason=result.block_reason or "",
        fallback_used=result.fallback_used,
        retries_used=result.retries_used,
    )


def count(counters: dict, result: QueryResult):
    with stats_lock:
        counters["total"] += 1
        if result.blocked:
            counters["blocked"] += 1
        elif result.execution_success:
            counters["success"] += 1
        else:
            counters["failed"] += 1


@router.get("/", tags=["info"])
def root():
    return {
        "name": "Text-to-SQL API",
        "version": "1.1.0",
        "description": "Bilingual Arabic-English Text-to-SQL with safety layer",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "query": "POST /query",
            "batch": "POST /query/batch",
            "schema": "GET  /schema",
            "health": "GET  /health",
            "audit_stats": "GET  /audit/stats",
            "benchmark": "GET  /benchmark",
        },
    }


@router.post(
    "/query",
    response_model=QueryResponse,
    tags=["query"],
    summary="Ask a question in English or Arabic",
    responses={
        200: {"description": "Query processed"},
        422: {"description": "Validation error — blank or too long"},
        503: {"description": "Chain not initialized"},
    },
)
def query(body: QueryRequest, chain=Depends(get_chain), counters=Depends(get_counters)):
    """
    Answer one question. `language` overrides detection. The answer comes
    with the SQL that produced it; unsafe questions or SQL are blocked.
    """
    try:
        result = chain.query(body.question, language=body.language)
    except Exception as e:
        logger.error(f"/query failed: {e}")
        raise HTTPException(status_code=500, detail="Query processing failed")

    count(counters, result)
    logger.info(f"/query lang={result.detected_language} strategy={result.strategy} "
                f"blocked={result.blocked} success={result.execution_success}")
    return to_response(result)


@router.post("/query/batch", response_model=BatchQueryResponse, tags=["query"],
             summary="Submit multiple questions at once (max 20)")
def query_batch(body: BatchQueryRequest, chain=Depends(get_chain), counters=Depends(get_counters)):
    """Up to 20 questions, answered one after another."""
    try:
        results = chain.analyze_batch(body.questions)
    except Exception as e:
        logger.error(f"/query/batch failed: {e}")
        raise HTTPException(status_code=500, detail="Batch processing failed")

    by_complexity = {"simple": 0, "medium": 0, "complex": 0}
    for r in results:
        if r.complexity in by_complexity:
            by_complexity[r.complexity] += 1
        count(counters, r)

    return BatchQueryResponse(
        results=[to_response(r) for r in results],
        total=len(results),
        success_count=sum(1 for r in results if r.execution_success and not r.blocked),
        blocked_count=sum(1 for r in results if r.blocked),
        summary=by_complexity,
    )


@router.get("/schema", response_model=SchemaResponse, tags=["database"], summary="Browse the database schema")
def schema(request: Request):
    """Tables with columns, row counts and descriptions."""
    try:
        conn = connect_readonly(db_path(request))
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    try:
        names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        tables = []
        for name in names:
            tables.append(SchemaTableInfo(
                name=name,
                row_count=conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0],
                columns=[r[1] for r in conn.execute(f'PRAGMA table_info("{name}")')],
                description=TABLE_DESCRIPTIONS.get(name, ""),
            ))
    finally:
        conn.close()

    total_rows = sum(t.row_count for t in tables)
    return SchemaResponse(tables=tables, total_tables=len(tables), total_rows=total_rows)


@router.get("/health", response_model=HealthResponse, tags=["system"], summary="System health check",
            responses={503: {"description": "Degraded: a component is unavailable"}})
def health(request: Request, response: Response):
    """
    200 when the pipeline, guard and database are all available, otherwise
    503, so Docker's healthcheck and load balancers can react.
    """
    chain = request.app.state.chain
    chain_ok = chain is not None
    guard_ok = chain_ok and getattr(chain, "guard", None) is not None

    db_ok = False
    try:
        conn = connect_readonly(db_path(request))  # read-only: never creates an empty file
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
    return HealthResponse(status="ok" if healthy else "degraded", chain_loaded=chain_ok,
                          guard_active=guard_ok, db_connected=db_ok, model=model)


@router.get("/audit/stats", response_model=AuditStatsResponse, tags=["system"], summary="Audit log statistics")
def audit_stats():
    stats = get_audit_stats()
    return AuditStatsResponse(
        total=stats.get("total", 0),
        blocked=stats.get("blocked", 0),
        suspicious=stats.get("suspicious", 0),
        block_rate=stats.get("block_rate", 0.0),
        by_language=stats.get("by_language", {}),
    )


@router.get("/benchmark", tags=["system"], summary="Latest benchmark summary")
def benchmark_summary():
    """Numbers from the last scripts/run_benchmark.py run; 404 until one exists."""
    if not os.path.exists(BENCHMARK_RESULTS):
        raise HTTPException(status_code=404, detail="No benchmark has been run yet")
    with open(BENCHMARK_RESULTS, encoding="utf-8") as f:
        report = json.load(f)
    return {k: report.get(k) for k in ("meta", "overall", "by_complexity", "by_language", "router", "latency")}
