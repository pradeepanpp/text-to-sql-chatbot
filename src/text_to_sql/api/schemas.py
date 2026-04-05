# src/text_to_sql/api/schemas.py
"""
Pydantic schemas — Phase 5.

All API request/response models are defined here.
FastAPI uses these for automatic validation and OpenAPI docs.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional


# ─────────────────────────────────────────────
# REQUEST MODELS
# ─────────────────────────────────────────────

class QueryRequest(BaseModel):
    """Single natural language query."""
    question: str = Field(
        ...,
        min_length = 1,
        max_length = 2000,
        description = "Natural language question in English or Arabic",
        examples    = [
            "How many customers are in the database?",
            "كم عدد العملاء في قاعدة البيانات؟",
        ],
    )
    language: Optional[str] = Field(
        default = None,
        description = "Force language: 'en' or 'ar'. Auto-detected if not set.",
    )

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question must not be blank")
        return v.strip()


class BatchQueryRequest(BaseModel):
    """Batch of up to 20 questions."""
    questions: list[str] = Field(
        ...,
        min_length = 1,
        max_length = 20,
        description = "List of questions (max 20)",
    )

    @field_validator("questions")
    @classmethod
    def questions_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("questions list must not be empty")
        for i, q in enumerate(v):
            if not isinstance(q, str) or not q.strip():
                raise ValueError(f"questions[{i}] must be a non-empty string")
        return v


# ─────────────────────────────────────────────
# RESPONSE MODELS
# ─────────────────────────────────────────────

class QueryResponse(BaseModel):
    """Response from /query endpoint."""
    question:         str
    detected_language: str           = Field(description="'en' or 'ar'")
    complexity:       str            = Field(description="simple / medium / complex")
    generated_sql:    str
    natural_response: str
    execution_success: bool
    blocked:          bool           = Field(description="True if query was blocked by safety layer")
    block_reason:     str            = ""
    retries_used:     int            = 0

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "question":          "How many customers are in the database?",
                "detected_language": "en",
                "complexity":        "simple",
                "generated_sql":     "SELECT COUNT(*) FROM customers LIMIT 500",
                "natural_response":  "There are 175 customers in the database.",
                "execution_success": True,
                "blocked":           False,
                "block_reason":      "",
                "retries_used":      0,
            }]
        }
    }


class BatchQueryResponse(BaseModel):
    """Response from /query/batch endpoint."""
    results:        list[QueryResponse]
    total:          int
    success_count:  int
    blocked_count:  int
    summary: dict = Field(
        description="Complexity distribution: {simple: n, medium: n, complex: n}"
    )


class SchemaTableInfo(BaseModel):
    """Info about one database table."""
    name:        str
    row_count:   int
    columns:     list[str]
    description: str


class SchemaResponse(BaseModel):
    """Response from /schema endpoint."""
    tables:       list[SchemaTableInfo]
    total_tables: int
    total_rows:   int


class HealthResponse(BaseModel):
    """Response from /health endpoint."""
    status:        str   = Field(description="ok | degraded")
    chain_loaded:  bool
    guard_active:  bool
    db_connected:  bool
    model:         str


class AuditStatsResponse(BaseModel):
    """Response from /audit/stats endpoint."""
    total:       int
    blocked:     int
    suspicious:  int
    block_rate:  float
    by_language: dict


class ErrorResponse(BaseModel):
    """Standard error envelope."""
    error:  str
    detail: Optional[str] = None
    code:   int