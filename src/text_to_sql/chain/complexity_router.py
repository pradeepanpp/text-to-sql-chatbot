"""
Complexity router: picks a strategy for each question with keyword rules,
without an LLM call.

  simple  - one table, basic filters ("How many customers?")
  medium  - joins, GROUP BY, rankings ("Top 5 products by revenue")
  complex - comparisons, percentages, 3+ tables ("Sales vs budget by region")
"""

import re
from dataclasses import dataclass

from src.text_to_sql.constants import COMPLEXITY_COMPLEX, COMPLEXITY_MEDIUM, COMPLEXITY_SIMPLE

COMPLEX_SIGNALS = [
    r"\bcompare\b", r"\bvs\b", r"\bversus\b", r"\brank\b", r"\branking\b",
    r"\bpercentage\b", r"\bpercent\b", r"\bratio\b", r"\bgrowth\b", r"\btrend\b",
    r"\byear.over.year\b", r"\bmonth.over.month\b", r"\bcorrelat\b",
    r"\bbest.performing\b", r"\bworst.performing\b", r"\bbenchmark\b",
    r"\bbudget vs\b", r"\bvs budget\b", r"\bacross.+and\b",
]

MEDIUM_SIGNALS = [
    r"\bgroup by\b", r"\bper customer\b", r"\bper product\b", r"\bper region\b",
    r"\bby customer\b", r"\bby product\b", r"\bby region\b", r"\bby channel\b",
    r"\btop \d+\b", r"\bbottom \d+\b", r"\bhighest\b", r"\blowest\b",
    r"\baverage\b", r"\bmean\b", r"\bjoin\b", r"\bfor each\b",
    r"\bbreak.?down\b", r"\bbreakdown\b", r"\bsummary\b", r"\bsummarise\b", r"\bsummarize\b",
]

# Words that point to a table; more tables means a harder question
TABLE_KEYWORDS = {
    "customer": ["customer", "client", "buyer"],
    "product": ["product"],
    "region": ["region", "city", "state", "area", "location"],
    "budget": ["budget", "target", "forecast"],
    "sales": ["sale", "order", "revenue", "purchase", "transaction"],
    "channel": ["wholesale", "distributor", "retail", "channel"],
}


@dataclass
class ComplexityResult:
    complexity: str
    confidence: float
    signals_found: list
    tables_detected: list
    reasoning: str


def matches(patterns: list, text: str) -> list:
    """Patterns found in text, shown without the regex escapes."""
    return [p.replace(r"\b", "").replace("\\", "") for p in patterns if re.search(p, text)]


class ComplexityRouter:
    def classify(self, question: str) -> ComplexityResult:
        q = question.lower().strip()
        tables = [name for name, words in TABLE_KEYWORDS.items() if any(w in q for w in words)]
        complex_hits = matches(COMPLEX_SIGNALS, q)
        medium_hits = matches(MEDIUM_SIGNALS, q)

        if complex_hits or len(tables) >= 3:
            complexity = COMPLEXITY_COMPLEX
            confidence = min(0.95, 0.70 + len(complex_hits) * 0.10)
            signals = complex_hits or [f"{len(tables)} tables detected"]
            if complex_hits:
                reasoning = f"Complex signals: {complex_hits} | Tables: {tables}"
            else:
                reasoning = f"3+ tables detected: {tables}"
        elif medium_hits or len(tables) == 2:
            complexity = COMPLEXITY_MEDIUM
            confidence = min(0.90, 0.65 + len(medium_hits) * 0.08)
            signals = medium_hits or [f"{len(tables)} tables detected"]
            reasoning = f"Medium signals: {medium_hits} | Tables: {tables}"
        else:
            complexity = COMPLEXITY_SIMPLE
            confidence = 0.80
            signals = ["no complex/medium signals found"]
            reasoning = f"Single table or simple lookup. Tables: {tables}"

        return ComplexityResult(complexity, round(confidence, 2), signals, tables, reasoning)
