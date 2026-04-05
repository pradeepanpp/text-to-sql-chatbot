# src/text_to_sql/api/main.py
"""
FastAPI Application — Phase 5.

Startup sequence:
  1. Load TextToSQLChain (LLM + SQLGuard + schema context)
  2. Register routes
  3. Serve on 0.0.0.0:8000

Run:
    uvicorn src.text_to_sql.api.main:app --reload --port 8000

Interactive docs:
    http://localhost:8000/docs    ← Swagger UI
    http://localhost:8000/redoc   ← ReDoc

Arabic example curl:
    curl -X POST http://localhost:8000/query \\
      -H "Content-Type: application/json" \\
      -d '{"question": "ما هو إجمالي المبيعات؟"}'
"""

import sys
import time
import os
sys.path.append(".")

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

from src.text_to_sql.api.routes import router
from src.text_to_sql.chain.sql_chain import TextToSQLChain
from src.text_to_sql.utils.logger import logger


# ─────────────────────────────────────────────
# LIFESPAN — startup / shutdown
# ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models at startup, release at shutdown."""

    # ── STARTUP ───────────────────────────────
    logger.info("=" * 52)
    logger.info("  Text-to-SQL API — Starting Up")
    logger.info("=" * 52)

    t0 = time.time()

    try:
        logger.info("Loading TextToSQLChain...")
        app.state.chain = TextToSQLChain(
            db_path     = "database/sales.db",
            model       = os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature = float(os.getenv("TEMPERATURE", "0.0")),
            max_tokens  = int(os.getenv("MAX_TOKENS", "500")),
            row_limit   = int(os.getenv("ROW_LIMIT", "500")),
        )
        logger.info(f"Chain loaded in {time.time() - t0:.1f}s")
    except Exception as e:
        logger.error(f"Failed to load chain: {e}")
        app.state.chain = None

    # Session stats
    app.state.stats = {
        "total":   0,
        "success": 0,
        "blocked": 0,
        "failed":  0,
    }
    app.state.start_time = time.time()

    logger.info("=" * 52)
    logger.info("  API ready — http://localhost:8000")
    logger.info("  Docs     — http://localhost:8000/docs")
    logger.info("=" * 52)

    yield   # server runs here

    # ── SHUTDOWN ──────────────────────────────
    logger.info("Shutting down...")
    app.state.chain = None


# ─────────────────────────────────────────────
# APP FACTORY
# ─────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title       = "Text-to-SQL API",
        description = (
            "Bilingual Arabic-English Text-to-SQL system with multi-strategy "
            "generation and enterprise safety layer.\n\n"
            "**Supported languages:** English, Arabic (عربي)\n\n"
            "**Detection strategies:**\n"
            "- Simple queries → Direct chain\n"
            "- Medium queries → Chain-of-Thought\n"
            "- Complex queries → ReAct Agent\n\n"
            "**Safety features:**\n"
            "- Prompt injection detection\n"
            "- Read-only SQL enforcement\n"
            "- Row limit protection\n"
            "- Full audit trail"
        ),
        version  = "1.0.0",
        lifespan = lifespan,
        docs_url  = "/docs",
        redoc_url = "/redoc",
    )

    # ── CORS — allows Streamlit dashboard ────
    app.add_middleware(
        CORSMiddleware,
        allow_origins     = ["*"],
        allow_credentials = True,
        allow_methods     = ["*"],
        allow_headers     = ["*"],
    )

    # ── Request logging ───────────────────────
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start    = time.time()
        response = await call_next(request)
        duration = round((time.time() - start) * 1000, 1)
        logger.debug(
            f"{request.method} {request.url.path} "
            f"→ {response.status_code} ({duration}ms)"
        )
        return response

    # ── Global exception handler ──────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception on {request.url.path}: {exc}")
        return JSONResponse(
            status_code = 500,
            content     = {
                "error":  "Internal server error",
                "detail": str(exc),
                "code":   500,
            }
        )

    # ── Routes ────────────────────────────────
    app.include_router(router)

    return app


# ─────────────────────────────────────────────
# APP INSTANCE
# ─────────────────────────────────────────────

app = create_app()


# ─────────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")

    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(
        "src.text_to_sql.api.main:app",
        host      = host,
        port      = port,
        reload    = True,
        workers   = 1,
        log_level = "warning",
    )