# Dockerfile — Text-to-SQL API
# Multi-stage build: builder installs deps, runtime runs the app

# ─────────────────────────────────────────────
# Stage 1 — Builder
# ─────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt


# ─────────────────────────────────────────────
# Stage 2 — Runtime
# ─────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY src/      src/
COPY configs/  configs/

# Copy pre-built database and models
COPY database/ database/
COPY models/   models/

# Create writable directories
RUN mkdir -p logs data/eval && \
    chown -R appuser:appuser /app

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" \
    || exit 1

CMD ["uvicorn", "src.text_to_sql.api.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--log-level", "warning"]