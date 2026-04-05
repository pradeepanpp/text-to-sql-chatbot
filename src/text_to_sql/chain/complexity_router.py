# src/text_to_sql/chain/complexity_router.py
"""
Query Complexity Router — Phase 2.

Classifies incoming natural language questions into three tiers
and routes each to the appropriate SQL generation strategy.

Tiers:
    SIMPLE  → single table, no joins, basic filters
              e.g. "How many customers?" / "List all products"

    MEDIUM  → 2 tables, simple joins, GROUP BY, aggregations
              e.g. "Total sales by customer?" / "Top 5 products by revenue"

    COMPLEX → 3+ tables, subqueries, multi-step reasoning
              e.g. "Which region had highest sales vs budget for Product 5?"

Why this matters:
    Simple queries waste tokens on a ReAct agent.
    Complex queries fail with a direct single-step chain.
    Routing gives the best accuracy at the lowest cost.
"""

import re
from dataclasses import dataclass
from src.text_to_sql.utils.logger import logger
from src.text_to_sql.constants import (
    COMPLEXITY_SIMPLE,
    COMPLEXITY_MEDIUM,
    COMPLEXITY_COMPLEX,
    ALL_TABLES,
)


# ─────────────────────────────────────────────
# KEYWORD SIGNALS
# ─────────────────────────────────────────────

# Strong signals for COMPLEX queries
COMPLEX_SIGNALS = [
    r"\bcompare\b",
    r"\bvs\b",
    r"\bversus\b",
    r"\brank\b",
    r"\branking\b",
    r"\bpercentage\b",
    r"\bpercent\b",
    r"\bratio\b",
    r"\bgrowth\b",
    r"\btrend\b",
    r"\byear.over.year\b",
    r"\bmonth.over.month\b",
    r"\bcorrelat\b",
    r"\bbest.performing\b",
    r"\bworst.performing\b",
    r"\bbenchmark\b",
    r"\bbudget vs\b",
    r"\bvs budget\b",
    r"\bacross.+and\b",
]

# Strong signals for MEDIUM queries
MEDIUM_SIGNALS = [
    r"\bgroup by\b",
    r"\bper customer\b",
    r"\bper product\b",
    r"\bper region\b",
    r"\bby customer\b",
    r"\bby product\b",
    r"\bby region\b",
    r"\bby channel\b",
    r"\btop \d+\b",
    r"\bbottom \d+\b",
    r"\bhighest\b",
    r"\blowest\b",
    r"\baverage\b",
    r"\bmean\b",
    r"\bjoin\b",
    r"\bfor each\b",
    r"\bbreak.?down\b",
    r"\bbreakdown\b",
    r"\bsummary\b",
    r"\bsummarise\b",
    r"\bsummarize\b",
]

# Table name mentions — multi-table = more complex
TABLE_KEYWORDS = {
    "customer":  ["customer", "client", "buyer"],
    "product":   ["product"],
    "region":    ["region", "city", "state", "area", "location"],
    "budget":    ["budget", "target", "forecast"],
    "sales":     ["sale", "order", "revenue", "purchase", "transaction"],
    "channel":   ["wholesale", "distributor", "retail", "channel"],
}


# ─────────────────────────────────────────────
# RESULT DATACLASS
# ─────────────────────────────────────────────

@dataclass
class ComplexityResult:
    """Output of the complexity router."""
    complexity:      str    # SIMPLE / MEDIUM / COMPLEX
    confidence:      float  # 0.0 – 1.0
    signals_found:   list   # which patterns triggered
    tables_detected: list   # which tables are likely needed
    reasoning:       str    # human-readable explanation


# ─────────────────────────────────────────────
# ROUTER
# ─────────────────────────────────────────────

class ComplexityRouter:
    """
    Rule-based query complexity classifier.

    Uses regex pattern matching on the natural language question
    to determine which SQL generation strategy to use.

    No LLM calls — fast, deterministic, zero cost.

    Usage:
        router = ComplexityRouter()
        result = router.classify("Top 5 customers by total sales?")

    """

    def classify(self, question: str) -> ComplexityResult:
        """
        Classify a question into SIMPLE / MEDIUM / COMPLEX.

        Args:
            question: natural language question (English)

        Returns:
            ComplexityResult with tier, confidence, and reasoning
        """
        q_lower  = question.lower().strip()
        signals  = []
        tables   = self._detect_tables(q_lower)

        # ── Check COMPLEX signals first ───────
        complex_hits = []
        for pattern in COMPLEX_SIGNALS:
            if re.search(pattern, q_lower):
                complex_hits.append(pattern.replace(r"\b", "").replace("\\", ""))

        # ── Check MEDIUM signals ──────────────
        medium_hits = []
        for pattern in MEDIUM_SIGNALS:
            if re.search(pattern, q_lower):
                medium_hits.append(pattern.replace(r"\b", "").replace("\\", ""))

        # ── Table count heuristic ─────────────
        table_count = len(tables)

        # ── Decision logic ────────────────────
        if complex_hits or table_count >= 3:
            complexity  = COMPLEXITY_COMPLEX
            confidence  = min(0.95, 0.70 + len(complex_hits) * 0.10)
            signals     = complex_hits or [f"{table_count} tables detected"]
            reasoning   = (
                f"Complex signals: {complex_hits} | "
                f"Tables: {tables}"
                if complex_hits
                else f"3+ tables detected: {tables}"
            )

        elif medium_hits or table_count == 2:
            complexity  = COMPLEXITY_MEDIUM
            confidence  = min(0.90, 0.65 + len(medium_hits) * 0.08)
            signals     = medium_hits or [f"{table_count} tables detected"]
            reasoning   = (
                f"Medium signals: {medium_hits} | Tables: {tables}"
            )

        else:
            complexity  = COMPLEXITY_SIMPLE
            confidence  = 0.80
            signals     = ["no complex/medium signals found"]
            reasoning   = f"Single table or simple lookup. Tables: {tables}"

        result = ComplexityResult(
            complexity      = complexity,
            confidence      = round(confidence, 2),
            signals_found   = signals,
            tables_detected = tables,
            reasoning       = reasoning,
        )

        logger.debug(
            f"Complexity: {complexity} "
            f"(conf={confidence:.2f}) | {reasoning}"
        )
        return result

    def _detect_tables(self, q_lower: str) -> list:
        """
        Detect which database tables are likely referenced
        in the question based on keyword matching.
        """
        detected = []
        for table_key, keywords in TABLE_KEYWORDS.items():
            if any(kw in q_lower for kw in keywords):
                detected.append(table_key)
        return detected