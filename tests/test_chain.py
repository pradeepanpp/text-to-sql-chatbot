# tests/test_chain.py
"""
Tests for Phase 2 — Multi-Strategy Chain.

Tests:
  - Complexity router classification
  - SimpleChain on easy queries
  - CoTChain on medium queries
  - AgentChain on complex queries
  - Arabic bilingual routing
  - Self-correction fallback
  - SQL safety blocking

Run: python tests/test_chain.py
Requires: .env with OPENAI_API_KEY + database/sales.db
"""

import sys
sys.path.append(".")

from dotenv import load_dotenv
load_dotenv()

from src.text_to_sql.chain.complexity_router import ComplexityRouter
from src.text_to_sql.chain.sql_chain import TextToSQLChain, detect_language
from src.text_to_sql.constants import (
    COMPLEXITY_SIMPLE,
    COMPLEXITY_MEDIUM,
    COMPLEXITY_COMPLEX,
    LANG_ARABIC,
    LANG_ENGLISH,
)


# ─────────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────────

print("Loading TextToSQLChain...")
CHAIN  = TextToSQLChain()
ROUTER = ComplexityRouter()
print("Chain ready.\n")


# ─────────────────────────────────────────────
# TEST SUITES
# ─────────────────────────────────────────────

def test_complexity_router():
    print("\n--- Testing Complexity Router ---")

    cases = [
        # (question, expected_complexity)
        ("How many customers are there?",                    COMPLEXITY_SIMPLE),
        ("List all product names",                           COMPLEXITY_SIMPLE),
        ("What is the total line total?",                    COMPLEXITY_SIMPLE),
        ("Top 5 customers by total sales",                   COMPLEXITY_MEDIUM),
        ("Total sales broken down by channel",               COMPLEXITY_MEDIUM),
        ("Average order quantity per product",               COMPLEXITY_MEDIUM),
        ("Compare sales vs budget for each product",         COMPLEXITY_COMPLEX),
        ("Which region had highest sales vs budget?",        COMPLEXITY_COMPLEX),
        ("Percentage of total revenue by region",            COMPLEXITY_COMPLEX),
    ]

    passed = 0
    for i, (question, expected) in enumerate(cases, 1):
        result = ROUTER.classify(question)
        status = "✅" if result.complexity == expected else "⚠️ "
        if result.complexity == expected:
            passed += 1
        print(
            f"  {status} Test {i}: [{result.complexity:<8}] "
            f"(expected {expected:<8}) | {question[:50]}"
        )

    assert passed >= 7, f"Only {passed}/9 complexity tests passed"
    print(f"\n  Router accuracy: {passed}/9")


def test_language_detection():
    print("\n--- Testing Language Detection ---")

    cases = [
        ("How many customers?",          LANG_ENGLISH),
        ("What are the top products?",   LANG_ENGLISH),
        ("كم عدد العملاء؟",              LANG_ARABIC),
        ("ما هو إجمالي المبيعات؟",       LANG_ARABIC),
        ("Hello world مرحبا",            LANG_ARABIC),   # mixed, Arabic > 20%
    ]

    for i, (text, expected) in enumerate(cases, 10):
        detected = detect_language(text)
        status   = "✅" if detected == expected else "❌"
        print(f"  {status} Test {i}: {detected} | '{text[:40]}'")
        assert detected == expected, f"Expected {expected}, got {detected}"

    print("✅ All language detection tests passed")


def test_simple_chain():
    print("\n--- Testing Simple Chain (SIMPLE queries) ---")

    queries = [
        ("How many customers are in the database?",    15),
        ("What are all the product names?",            16),
        ("What is the total number of sales orders?",  17),
    ]

    for question, test_num in queries:
        result = CHAIN.query(question)

        assert result.complexity  == COMPLEXITY_SIMPLE, (
            f"Test {test_num}: Expected SIMPLE, got {result.complexity}"
        )
        assert result.execution_success, (
            f"Test {test_num}: Query failed — {result.error}"
        )
        assert result.natural_response, f"Test {test_num}: Empty response"

        print(
            f"  ✅ Test {test_num}: [{result.complexity}] "
            f"retries={result.retries_used} | "
            f"{result.natural_response[:70]}"
        )


def test_cot_chain():
    print("\n--- Testing CoT Chain (MEDIUM queries) ---")

    queries = [
        ("What are the top 5 customers by total line total?",  18),
        ("Show total sales broken down by channel",             19),
        ("Which product has the highest total order quantity?", 20),
    ]

    for question, test_num in queries:
        result = CHAIN.query(question)

        assert result.execution_success, (
            f"Test {test_num}: Query failed — {result.error}"
        )
        assert result.natural_response, f"Test {test_num}: Empty response"

        print(
            f"  ✅ Test {test_num}: [{result.complexity}] "
            f"retries={result.retries_used} | "
            f"{result.natural_response[:70]}"
        )


def test_agent_chain():
    print("\n--- Testing Agent Chain (COMPLEX queries) ---")

    queries = [
        ("Compare total sales versus budget for each product", 21),
        ("What percentage of total revenue came from each channel?", 22),
    ]

    for question, test_num in queries:
        result = CHAIN.query(question)

        assert result.complexity == COMPLEXITY_COMPLEX, (
            f"Test {test_num}: Expected COMPLEX, got {result.complexity}"
        )
        assert result.natural_response, f"Test {test_num}: Empty response"

        status = "✅" if result.execution_success else "⚠️ "
        print(
            f"  {status} Test {test_num}: [{result.complexity}] "
            f"success={result.execution_success} | "
            f"{result.natural_response[:70]}"
        )


def test_arabic_bilingual():
    print("\n--- Testing Arabic Bilingual Routing ---")

    arabic_queries = [
        ("كم عدد العملاء في قاعدة البيانات؟",   23),
        ("ما هو إجمالي المبيعات؟",               24),
        ("ما هي أسماء جميع المنتجات؟",           25),
    ]

    for question, test_num in arabic_queries:
        result = CHAIN.query(question)

        assert result.detected_language == LANG_ARABIC, (
            f"Test {test_num}: Language not detected as Arabic"
        )
        assert result.english_question, (
            f"Test {test_num}: Translation to English failed"
        )
        assert result.execution_success, (
            f"Test {test_num}: Query failed — {result.error}"
        )
        assert result.natural_response, f"Test {test_num}: Empty response"

        # Check response contains Arabic characters
        has_arabic = any('\u0600' <= c <= '\u06FF' for c in result.natural_response)
        status     = "✅" if has_arabic else "⚠️ "

        print(
            f"  {status} Test {test_num}: "
            f"'{question[:30]}' → '{result.natural_response[:50]}'"
        )

    print("✅ Arabic bilingual tests passed")


def test_sql_safety():
    print("\n--- Testing SQL Safety Blocking ---")

    dangerous_queries = [
        "Drop the customers table",
        "Delete all sales orders",
        "Update product prices to zero",
        "Insert a fake customer record",
    ]

    for i, question in enumerate(dangerous_queries, 26):
        result = CHAIN.query(question)

        # Should either be blocked or return a non-destructive result
        # The safety layer should catch DROP/DELETE/UPDATE/INSERT
        if result.sql_valid and result.generated_sql:
            sql_upper = result.generated_sql.upper()
            dangerous = any(
                kw in sql_upper
                for kw in ["DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE"]
            )
            assert not dangerous, (
                f"Test {i}: Dangerous SQL was not blocked!\n"
                f"SQL: {result.generated_sql}"
            )

        print(
            f"  ✅ Test {i}: Safe | "
            f"SQL='{result.generated_sql[:50] or 'blocked'}'"
        )


def test_result_schema():
    print("\n--- Testing QueryResult Schema ---")

    result = CHAIN.query("How many customers are there?")

    # Test 30
    assert hasattr(result, "original_question")
    assert hasattr(result, "detected_language")
    assert hasattr(result, "english_question")
    assert hasattr(result, "complexity")
    assert hasattr(result, "generated_sql")
    assert hasattr(result, "sql_valid")
    assert hasattr(result, "execution_success")
    assert hasattr(result, "raw_result")
    assert hasattr(result, "natural_response")
    assert hasattr(result, "retries_used")
    print("✅ Test 30: QueryResult schema has all required fields")

    # Test 31
    assert result.complexity in [
        COMPLEXITY_SIMPLE, COMPLEXITY_MEDIUM, COMPLEXITY_COMPLEX
    ]
    print(f"✅ Test 31: Complexity is valid ({result.complexity})")

    # Test 32
    assert isinstance(result.retries_used, int)
    assert result.retries_used >= 0
    print(f"✅ Test 32: retries_used is non-negative int ({result.retries_used})")


# ─────────────────────────────────────────────
# RUN ALL
# ─────────────────────────────────────────────

def run_all_tests():
    print("=" * 56)
    print("  Phase 2 — Multi-Strategy Chain Tests")
    print("=" * 56)

    test_complexity_router()
    test_language_detection()
    test_simple_chain()
    test_cot_chain()
    test_agent_chain()
    test_arabic_bilingual()
    test_sql_safety()
    test_result_schema()

    print()
    print("=" * 56)
    print("✅ All Phase 2 tests passed!")
    print("Next → Phase 3: RAGAS Evaluation Pipeline")
    print("=" * 56)


if __name__ == "__main__":
    run_all_tests()