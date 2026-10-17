"""Request and response models (used for validation and the /docs page)."""

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class QueryRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language question in English or Arabic",
        examples=["How many customers are in the database?", "كم عدد العملاء في قاعدة البيانات؟"],
    )
    language: Optional[Literal["en", "ar"]] = Field(
        default=None, description="Force language: 'en' or 'ar'. Auto-detected if not set.",
    )

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question must not be blank")
        return v.strip()


class BatchQueryRequest(BaseModel):
    questions: list[str] = Field(..., min_length=1, max_length=20, description="List of questions (max 20)")

    @field_validator("questions")
    @classmethod
    def questions_not_empty(cls, v: list) -> list:
        for i, q in enumerate(v):
            if not isinstance(q, str) or not q.strip():
                raise ValueError(f"questions[{i}] must be a non-empty string")
        return v


class QueryResponse(BaseModel):
    question: str
    detected_language: str = Field(description="'en' or 'ar'")
    complexity: str = Field(description="Router decision: simple / medium / complex")
    strategy: str = Field(default="", description="Strategy that ran first: simple / cot / agent")
    generated_sql: str = Field(description="The SQL that was executed (row limit applied)")
    natural_response: str
    execution_success: bool = Field(description="SQL ran and an answer was produced (not a correctness check)")
    row_count: int = 0
    blocked: bool = Field(description="True if query was blocked by safety layer")
    block_reason: str = ""
    fallback_used: bool = False
    retries_used: int = Field(default=0, description="LLM attempts made by the self-correction fallback")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "question": "How many customers are in the database?",
                "detected_language": "en",
                "complexity": "simple",
                "strategy": "simple",
                "generated_sql": "SELECT COUNT(*) FROM customers LIMIT 500",
                "natural_response": "There are 175 customers in the database.",
                "execution_success": True,
                "row_count": 1,
                "blocked": False,
                "block_reason": "",
                "fallback_used": False,
                "retries_used": 0,
            }]
        }
    }


class BatchQueryResponse(BaseModel):
    results: list[QueryResponse]
    total: int
    success_count: int
    blocked_count: int
    summary: dict = Field(description="Complexity distribution: {simple: n, medium: n, complex: n}")


class SchemaTableInfo(BaseModel):
    name: str
    row_count: int
    columns: list[str]
    description: str


class SchemaResponse(BaseModel):
    tables: list[SchemaTableInfo]
    total_tables: int
    total_rows: int


class HealthResponse(BaseModel):
    status: str = Field(description="ok | degraded")
    chain_loaded: bool
    guard_active: bool
    db_connected: bool
    model: str


class AuditStatsResponse(BaseModel):
    total: int
    blocked: int
    suspicious: int
    block_rate: float
    by_language: dict
