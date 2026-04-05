# src/text_to_sql/api/routes.py
"""
FastAPI route handlers — Phase 5.

Endpoints:
    POST /query           → single natural language query
    POST /query/batch     → batch queries (up to 20)
    GET  /schema          → database schema browser
    GET  /health          → system health check
    GET  /audit/stats     → audit log statistics
    GET  /                → welcome + docs link
"""

import sqlite3
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

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
from src.text_to_sql.chain.sql_chain import QueryResult
from src.text_to_sql.safety.sql_guard import get_audit_stats
from src.text_to_sql.constants import TABLE_DESCRIPTIONS
from src.text_to_sql.utils.logger import logger

router = APIRouter()

DB_PATH = "database/sales.db"


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


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def result_to_response(result: QueryResult) -> QueryResponse:
    """Convert QueryResult dataclass → QueryResponse Pydantic model."""
    return QueryResponse(
        question          = result.original_question,
        detected_language = result.detected_language,
        complexity        = result.complexity,
        generated_sql     = result.generated_sql or "",
        natural_response  = result.natural_response or "",
        execution_success = result.execution_success,
        blocked           = result.blocked,
        block_reason      = result.block_reason or "",
        retries_used      = result.retries_used,
    )


def update_stats(stats: dict, result: QueryResult):
    """Increment session counters."""
    stats["total"]  += 1
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
async def root():
    """Welcome message with API information."""
    return {
        "name":        "Text-to-SQL API",
        "version":     "1.0.0",
        "description": "Bilingual Arabic-English Text-to-SQL with safety layer",
        "docs":        "/docs",
        "health":      "/health",
        "endpoints": {
            "query":       "POST /query",
            "batch":       "POST /query/batch",
            "schema":      "GET  /schema",
            "health":      "GET  /health",
            "audit_stats": "GET  /audit/stats",
        }
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
    }
)
async def query(
    body:  QueryRequest,
    chain  = Depends(get_chain),
    stats  = Depends(get_stats_counter),
):
    """
    Submit a natural language question and receive a SQL-backed answer.

    - Supports **English and Arabic** questions
    - Automatically detects language
    - Routes to Simple / Chain-of-Thought / ReAct agent based on complexity
    - Blocked if prompt injection or write SQL detected
    - Full audit trail logged automatically
    """
    try:
        result   = chain.query(body.question)
        response = result_to_response(result)
        update_stats(stats, result)

        logger.info(
            f"[/query] lang={result.detected_language} "
            f"complexity={result.complexity} "
            f"blocked={result.blocked} "
            f"success={result.execution_success}"
        )
        return response

    except Exception as e:
        logger.error(f"[/query] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/query/batch",
    response_model = BatchQueryResponse,
    tags           = ["query"],
    summary        = "Submit multiple questions at once (max 20)",
    responses      = {
        200: {"description": "Batch processed"},
        422: {"description": "Validation error"},
        503: {"description": "Chain not initialized"},
    }
)
async def query_batch(
    body:  BatchQueryRequest,
    chain  = Depends(get_chain),
    stats  = Depends(get_stats_counter),
):
    """
    Submit up to 20 questions in a single request.
    Returns individual results for each question plus a summary.
    """
    try:
        results   = chain.analyze_batch(body.questions)
        responses = [result_to_response(r) for r in results]

        # Build summary
        complexity_dist = {"simple": 0, "medium": 0, "complex": 0}
        for r in results:
            if r.complexity in complexity_dist:
                complexity_dist[r.complexity] += 1
            update_stats(stats, r)

        success_count = sum(1 for r in results if r.execution_success and not r.blocked)
        blocked_count = sum(1 for r in results if r.blocked)

        logger.info(
            f"[/query/batch] {len(body.questions)} questions — "
            f"success={success_count} blocked={blocked_count}"
        )

        return BatchQueryResponse(
            results       = responses,
            total         = len(responses),
            success_count = success_count,
            blocked_count = blocked_count,
            summary       = complexity_dist,
        )

    except Exception as e:
        logger.error(f"[/query/batch] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/schema",
    response_model = SchemaResponse,
    tags           = ["database"],
    summary        = "Browse the database schema",
)
async def schema():
    """
    Returns the full database schema including all tables,
    column names, row counts, and plain-English descriptions.
    Useful for building a schema browser in the dashboard.
    """
    try:
        conn   = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        table_names = [row[0] for row in cursor.fetchall()]

        tables     = []
        total_rows = 0

        for name in table_names:
            # Get columns
            cursor.execute(f"PRAGMA table_info({name})")
            columns = [row[1] for row in cursor.fetchall()]

            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {name}")
            row_count = cursor.fetchone()[0]
            total_rows += row_count

            tables.append(SchemaTableInfo(
                name        = name,
                row_count   = row_count,
                columns     = columns,
                description = TABLE_DESCRIPTIONS.get(name, ""),
            ))

        conn.close()

        return SchemaResponse(
            tables       = tables,
            total_tables = len(tables),
            total_rows   = total_rows,
        )

    except Exception as e:
        logger.error(f"[/schema] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/health",
    response_model = HealthResponse,
    tags           = ["system"],
    summary        = "System health check",
)
async def health(request: Request):
    """
    Returns the current health status of all system components.
    - **ok**: all components healthy
    - **degraded**: one or more components unavailable
    """
    chain       = request.app.state.chain
    chain_ok    = chain is not None
    guard_ok    = chain_ok and chain.guard is not None

    # Check DB connection
    db_ok = False
    try:
        conn   = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        db_ok  = True
        conn.close()
    except Exception:
        pass

    all_ok = chain_ok and guard_ok and db_ok
    status = "ok" if all_ok else "degraded"

    model = "gpt-4o-mini"
    if chain_ok and hasattr(chain, "llm") and chain.llm:
        try:
            model = chain.llm.model_name
        except Exception:
            pass

    return HealthResponse(
        status       = status,
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
async def audit_stats():
    """
    Returns statistics from the audit log:
    total queries, blocked count, block rate, and language breakdown.
    For compliance monitoring in UAE banking/government deployments.
    """
    stats = get_audit_stats()
    return AuditStatsResponse(
        total       = stats.get("total", 0),
        blocked     = stats.get("blocked", 0),
        suspicious  = stats.get("suspicious", 0),
        block_rate  = stats.get("block_rate", 0.0),
        by_language = stats.get("by_language", {}),
    )
