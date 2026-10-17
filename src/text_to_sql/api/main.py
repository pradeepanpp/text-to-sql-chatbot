"""
FastAPI app.

Run:  uvicorn src.text_to_sql.api.main:app --port 8000
Docs: http://localhost:8000/docs
"""

import os
import sys
import time
from contextlib import asynccontextmanager

sys.path.append(".")

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

load_dotenv()

from src.text_to_sql.api.routes import router
from src.text_to_sql.chain.sql_chain import TextToSQLChain
from src.text_to_sql.utils.logger import logger

DESCRIPTION = """Ask questions about the sales database in English or Arabic.

Each question is routed to one of three SQL strategies: a simple chain,
chain-of-thought, or a ReAct agent. Every query passes the SQL guard,
runs on a read-only connection and is written to the audit log."""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the pipeline once at startup. If it fails, /health reports 503."""
    start = time.time()
    try:
        app.state.chain = TextToSQLChain(
            db_path=os.getenv("DB_PATH", "database/sales.db"),
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=float(os.getenv("TEMPERATURE", "0.0")),
            max_tokens=int(os.getenv("MAX_TOKENS", "500")),
            row_limit=int(os.getenv("ROW_LIMIT", "500")),
        )
        logger.info(f"Pipeline loaded in {time.time() - start:.1f}s")
    except Exception as e:
        logger.error(f"Failed to load the pipeline: {e}")
        app.state.chain = None

    app.state.stats = {"total": 0, "success": 0, "blocked": 0, "failed": 0}
    app.state.start_time = time.time()
    yield
    app.state.chain = None


def create_app() -> FastAPI:
    app = FastAPI(title="Text-to-SQL API", description=DESCRIPTION, version="1.1.0", lifespan=lifespan)

    # The dashboard calls the API from its server, so CORS only matters for
    # browser clients. Credentials are never allowed together with "*".
    origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=origins != ["*"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        logger.debug(f"{request.method} {request.url.path} {response.status_code} "
                     f"({(time.time() - start) * 1000:.1f}ms)")
        return response

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception):
        # Details go to the server log only, so SQL errors and stack traces are not leaked
        logger.exception(f"Unhandled exception on {request.url.path}: {exc}")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "code": 500})

    app.include_router(router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.text_to_sql.api.main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", 8000)),
        reload=os.environ.get("RELOAD", "0") == "1",
        log_level="warning",
    )
