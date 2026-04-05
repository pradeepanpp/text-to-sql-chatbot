# tests/test_evaluation.py
"""
Tests for Phase 3 — Evaluation Pipeline.

Run AFTER scripts/run_benchmark.py has completed.

Run: python tests/test_evaluation.py
"""

import sys
import os
import json
sys.path.append(".")

from src.text_to_sql.evaluation.eval_dataset import (
    EVAL_DATASET,
    get_by_complexity,
    get_by_language,
    get_summary,
)

RESULTS_JSON = "data/eval/benchmark_results.json"
SUMMARY_TXT  = "data/eval/benchmark_summary.txt"


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def load_report() -> dict:
    if not os.path.exists(RESULTS_JSON):
        raise FileNotFoundError(
            f"Report not found: {RESULTS_JSON}\n"
            "Run: python scripts/run_benchmark.py first"
        )
    with open(RESULTS_JSON, encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────
# TESTS
# ─────────────────────────────────────────────

def test_dataset_integrity():
    print("\n--- Testing Dataset Integrity ---")

    # Test 1 — dataset has 100 questions
    assert len(EVAL_DATASET) == 100, (
        f"Expected 100 questions, got {len(EVAL_DATASET)}"
    )
    print(f"✅ Test 1 passed: Dataset has {len(EVAL_DATASET)} questions")

    # Test 2 — all required fields present
    required = ["question", "reference_sql", "reference_ans",
                "complexity", "language", "tables"]
    for i, item in enumerate(EVAL_DATASET):
        for field in required:
            assert field in item, f"Item {i} missing field: {field}"
    print("✅ Test 2 passed: All items have required fields")

    # Test 3 — complexity distribution
    simple  = len(get_by_complexity("simple"))
    medium  = len(get_by_complexity("medium"))
    complex_= len(get_by_complexity("complex"))
    assert simple  > 0, "No simple questions"
    assert medium  > 0, "No medium questions"
    assert complex_> 0, "No complex questions"
    print(f"✅ Test 3 passed: simple={simple} medium={medium} complex={complex_}")

    # Test 4 — language distribution
    english = len(get_by_language("en"))
    arabic  = len(get_by_language("ar"))
    assert english > 0, "No English questions"
    assert arabic  > 0, "No Arabic questions"
    print(f"✅ Test 4 passed: English={english} Arabic={arabic}")

    # Test 5 — all reference SQL starts with SELECT
    for i, item in enumerate(EVAL_DATASET):
        sql = item["reference_sql"].strip().upper()
        assert sql.startswith("SELECT"), (
            f"Item {i} reference SQL doesn't start with SELECT: {sql[:50]}"
        )
    print("✅ Test 5 passed: All reference SQL starts with SELECT")

    # Test 6 — all complexity values are valid
    valid = {"simple", "medium", "complex"}
    for i, item in enumerate(EVAL_DATASET):
        assert item["complexity"] in valid, (
            f"Item {i} has invalid complexity: {item['complexity']}"
        )
    print("✅ Test 6 passed: All complexity values valid")

    # Test 7 — all language values are valid
    valid_lang = {"en", "ar"}
    for i, item in enumerate(EVAL_DATASET):
        assert item["language"] in valid_lang, (
            f"Item {i} has invalid language: {item['language']}"
        )
    print("✅ Test 7 passed: All language values valid")


def test_report_files():
    print("\n--- Testing Report Files ---")

    # Test 8 — JSON report exists
    assert os.path.exists(RESULTS_JSON), f"Missing: {RESULTS_JSON}"
    print(f"✅ Test 8 passed: {RESULTS_JSON} exists")

    # Test 9 — Summary text exists
    assert os.path.exists(SUMMARY_TXT), f"Missing: {SUMMARY_TXT}"
    print(f"✅ Test 9 passed: {SUMMARY_TXT} exists")

    # Test 10 — JSON is valid
    with open(RESULTS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, dict)
    print("✅ Test 10 passed: JSON report is valid")


def test_report_structure():
    print("\n--- Testing Report Structure ---")
    report = load_report()

    # Test 11 — top-level keys
    for key in ["meta", "overall", "by_complexity", "by_language",
                "latency", "detailed_results"]:
        assert key in report, f"Missing key: {key}"
    print("✅ Test 11 passed: All top-level keys present")

    # Test 12 — meta fields
    meta = report["meta"]
    assert meta["total_questions"] > 0
    assert meta["total_time_sec"]  > 0
    print(f"✅ Test 12 passed: meta — {meta['total_questions']} questions, {meta['total_time_sec']:.0f}s")

    # Test 13 — overall accuracy in [0, 1]
    ov = report["overall"]
    assert 0.0 <= ov["execution_accuracy"] <= 1.0
    assert 0.0 <= ov["data_response_rate"] <= 1.0
    print(f"✅ Test 13 passed: overall accuracy={ov['execution_accuracy']:.2%}")

    # Test 14 — latency ordering
    lat = report["latency"]
    assert lat["min_ms"] <= lat["p50_ms"] <= lat["p95_ms"] <= lat["max_ms"]
    print(f"✅ Test 14 passed: latency p50={lat['p50_ms']}ms p95={lat['p95_ms']}ms")

    # Test 15 — complexity breakdown present
    bc = report["by_complexity"]
    assert len(bc) >= 1
    for tier, vals in bc.items():
        assert "accuracy" in vals
        assert 0.0 <= vals["accuracy"] <= 1.0
    print(f"✅ Test 15 passed: Complexity breakdown has {len(bc)} tiers")

    # Test 16 — language breakdown present
    bl = report["by_language"]
    assert len(bl) >= 1
    print(f"✅ Test 16 passed: Language breakdown has {len(bl)} languages")

    # Test 17 — detailed results count matches meta
    assert len(report["detailed_results"]) == meta["total_questions"]
    print(f"✅ Test 17 passed: detailed_results has {len(report['detailed_results'])} items")


def test_result_quality():
    print("\n--- Testing Result Quality ---")
    report = load_report()
    ov     = report["overall"]
    bc     = report["by_complexity"]

    # Test 18 — overall execution accuracy > 50%
    assert ov["execution_accuracy"] >= 0.50, (
        f"Overall accuracy {ov['execution_accuracy']:.2%} < 50% — system underperforming"
    )
    print(f"✅ Test 18 passed: Overall accuracy {ov['execution_accuracy']:.2%} ≥ 50%")

    # Test 19 — simple queries should be most accurate
    if "simple" in bc:
        simple_acc = bc["simple"]["accuracy"]
        assert simple_acc >= 0.70, (
            f"Simple accuracy {simple_acc:.2%} < 70%"
        )
        print(f"✅ Test 19 passed: Simple accuracy {simple_acc:.2%} ≥ 70%")
    else:
        print("⏭  Test 19 skipped: no simple queries in this run")

    # Test 20 — no negative retries
    for r in report["detailed_results"]:
        assert r["retries_used"] >= 0
    print("✅ Test 20 passed: All retry counts non-negative")

    # Test 21 — language detection correct for all
    for r in report["detailed_results"]:
        assert r["detected_language"] in ["en", "ar"]
    print("✅ Test 21 passed: All detected languages are valid values")


def print_summary(report: dict):
    """Print key metrics for human review."""
    ov  = report["overall"]
    bc  = report["by_complexity"]
    bl  = report["by_language"]
    lat = report["latency"]
    m   = report["meta"]

    print("\n" + "─" * 56)
    print("  BENCHMARK SUMMARY")
    print("─" * 56)
    print(f"  Questions        : {m['total_questions']}")
    print(f"  Total time       : {m['total_time_sec']:.0f}s")
    print(f"  Exec accuracy    : {ov['execution_accuracy']:.2%}")
    print(f"  Data resp rate   : {ov['data_response_rate']:.2%}")
    print(f"  Self-correction  : {ov['retry_rate']:.2%}")
    print("─" * 56)
    for tier, vals in bc.items():
        print(f"  {tier:<10} {vals['accuracy']:.2%}  ({vals['avg_latency_ms']:.0f}ms avg)")
    print("─" * 56)
    for lang, vals in bl.items():
        name = "English" if lang == "en" else "Arabic "
        print(f"  {name}   {vals['accuracy']:.2%}")
    print("─" * 56)
    print(f"  p50 latency      : {lat['p50_ms']:.0f}ms")
    print(f"  p95 latency      : {lat['p95_ms']:.0f}ms")
    print("─" * 56)


# ─────────────────────────────────────────────
# RUN ALL
# ─────────────────────────────────────────────

def run_all_tests():
    print("=" * 56)
    print("  Phase 3 — Evaluation Tests")
    print("=" * 56)

    test_dataset_integrity()
    test_report_files()
    test_report_structure()
    test_result_quality()

    report = load_report()
    print_summary(report)

    print()
    print("=" * 56)
    print("✅ All Evaluation tests passed!")
    print("Next → Phase 4: Safety Layer")
    print("=" * 56)


if __name__ == "__main__":
    run_all_tests()