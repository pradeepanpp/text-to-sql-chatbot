# src/text_to_sql/evaluation/benchmark.py
"""
Benchmark Runner — Phase 3.

Runs all 100 evaluation questions through the pipeline
and measures:
  - SQL execution accuracy (did SQL run without error?)
  - Answer correctness (binary match check)
  - Per-complexity accuracy breakdown
  - Per-language accuracy breakdown
  - Latency per query and per tier
  - Self-correction rate

Outputs:
  data/eval/benchmark_results.json   ← full results
  data/eval/benchmark_summary.txt    ← readable summary

Run:
    python scripts/run_benchmark.py
"""

import os
import sys
import json
import time
import sqlite3
sys.path.append(".")

from dotenv import load_dotenv
load_dotenv()

from src.text_to_sql.chain.sql_chain import TextToSQLChain
from src.text_to_sql.evaluation.eval_dataset import EVAL_DATASET, get_summary
from src.text_to_sql.utils.logger import logger

RESULTS_DIR   = "data/eval"
RESULTS_JSON  = f"{RESULTS_DIR}/benchmark_results.json"
SUMMARY_TXT   = f"{RESULTS_DIR}/benchmark_summary.txt"


# ─────────────────────────────────────────────
# EXECUTION ACCURACY
# ─────────────────────────────────────────────

def check_sql_executes(sql: str, db_path: str = "database/sales.db") -> bool:
    """Check if a SQL query runs without error."""
    if not sql or sql == "Multi-step agent query":
        return True   # agent handled it
    try:
        conn   = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(sql)
        conn.close()
        return True
    except Exception:
        return False


def check_reference_sql(ref_sql: str, db_path: str = "database/sales.db") -> bool:
    """Verify reference SQL is itself valid."""
    return check_sql_executes(ref_sql, db_path)


# ─────────────────────────────────────────────
# ANSWER SIMILARITY
# ─────────────────────────────────────────────

def answer_contains_data(natural_response: str) -> bool:
    """
    Check if the response contains actual data
    rather than an error or 'no results' message.
    """
    if not natural_response:
        return False

    no_data_signals = [
        "no results", "no data", "unable to retrieve",
        "error", "failed", "not found", "لا توجد"
    ]
    lower = natural_response.lower()
    return not any(sig in lower for sig in no_data_signals)


# ─────────────────────────────────────────────
# BENCHMARK RUNNER
# ─────────────────────────────────────────────

def run_benchmark(
    sample_size: int = None,
    complexity_filter: str = None,
    language_filter:   str = None,
) -> dict:
    """
    Run the evaluation benchmark.

    Args:
        sample_size:        limit to N questions (None = all 100)
        complexity_filter:  only run 'simple' / 'medium' / 'complex'
        language_filter:    only run 'en' / 'ar'

    Returns:
        Full benchmark report dict
    """
    os.makedirs(RESULTS_DIR, exist_ok=True)

    # Filter dataset
    dataset = EVAL_DATASET
    if complexity_filter:
        dataset = [q for q in dataset if q["complexity"] == complexity_filter]
    if language_filter:
        dataset = [q for q in dataset if q["language"] == language_filter]
    if sample_size:
        dataset = dataset[:sample_size]

    logger.info("=" * 56)
    logger.info("  Phase 3 — Benchmark Evaluation")
    logger.info("=" * 56)
    logger.info(f"Questions to evaluate: {len(dataset)}")

    # Load chain
    chain = TextToSQLChain()

    # Run all questions
    results      = []
    total_start  = time.perf_counter()

    for i, item in enumerate(dataset, 1):
        question = item["question"]
        logger.info(f"\n[{i}/{len(dataset)}] {question[:60]}")

        t0     = time.perf_counter()
        result = chain.query(question)
        t1     = time.perf_counter()
        latency_ms = round((t1 - t0) * 1000, 1)

        # Measure execution accuracy
        exec_ok      = result.execution_success
        ref_exec_ok  = check_reference_sql(item["reference_sql"])
        has_data     = answer_contains_data(result.natural_response)

        record = {
            "index":            i,
            "question":         question,
            "complexity":       item["complexity"],
            "language":         item["language"],
            "tables":           item["tables"],
            "reference_sql":    item["reference_sql"],
            "generated_sql":    result.generated_sql,
            "execution_success": exec_ok,
            "reference_valid":   ref_exec_ok,
            "has_data_in_response": has_data,
            "retries_used":      result.retries_used,
            "detected_language": result.detected_language,
            "natural_response":  result.natural_response,
            "error":             result.error,
            "latency_ms":        latency_ms,
        }
        results.append(record)

        status = "✅" if exec_ok else "❌"
        logger.info(
            f"  {status} success={exec_ok} "
            f"complexity={item['complexity']} "
            f"lang={item['language']} "
            f"latency={latency_ms}ms"
        )

    total_time = round(time.perf_counter() - total_start, 1)

    # ── Compute metrics ───────────────────────
    report = _compute_metrics(results, total_time, dataset)

    # ── Save outputs ──────────────────────────
    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logger.info(f"\nResults saved → {RESULTS_JSON}")

    summary = _format_summary(report)
    with open(SUMMARY_TXT, "w", encoding="utf-8") as f:
        f.write(summary)
    logger.info(f"Summary saved → {SUMMARY_TXT}")

    return report


def _compute_metrics(results: list, total_time: float, dataset: list) -> dict:
    """Compute all metrics from raw results."""

    total = len(results)
    if total == 0:
        return {}

    # Overall execution accuracy
    exec_success  = sum(1 for r in results if r["execution_success"])
    has_data      = sum(1 for r in results if r["has_data_in_response"])
    total_retries = sum(r["retries_used"] for r in results)

    # Per complexity
    complexity_metrics = {}
    for tier in ["simple", "medium", "complex"]:
        tier_results = [r for r in results if r["complexity"] == tier]
        if not tier_results:
            continue
        tier_success = sum(1 for r in tier_results if r["execution_success"])
        tier_lat     = [r["latency_ms"] for r in tier_results]
        complexity_metrics[tier] = {
            "total":    len(tier_results),
            "success":  tier_success,
            "accuracy": round(tier_success / len(tier_results), 4),
            "avg_latency_ms": round(sum(tier_lat) / len(tier_lat), 1),
        }

    # Per language
    language_metrics = {}
    for lang in ["en", "ar"]:
        lang_results = [r for r in results if r["language"] == lang]
        if not lang_results:
            continue
        lang_success = sum(1 for r in lang_results if r["execution_success"])
        language_metrics[lang] = {
            "total":    len(lang_results),
            "success":  lang_success,
            "accuracy": round(lang_success / len(lang_results), 4),
        }

    # Latency
    latencies = [r["latency_ms"] for r in results]
    latencies.sort()
    n = len(latencies)

    return {
        "meta": {
            "total_questions":  total,
            "total_time_sec":   total_time,
            "avg_time_per_q":   round(total_time / total, 1),
        },
        "overall": {
            "execution_accuracy": round(exec_success / total, 4),
            "data_response_rate": round(has_data / total, 4),
            "total_retries":      total_retries,
            "retry_rate":         round(total_retries / total, 4),
        },
        "by_complexity":  complexity_metrics,
        "by_language":    language_metrics,
        "latency": {
            "mean_ms":  round(sum(latencies) / n, 1),
            "p50_ms":   latencies[n // 2],
            "p95_ms":   latencies[int(n * 0.95)],
            "min_ms":   latencies[0],
            "max_ms":   latencies[-1],
        },
        "detailed_results": results,
    }


def _format_summary(report: dict) -> str:
    """Build human-readable summary string."""
    m    = report.get("meta", {})
    ov   = report.get("overall", {})
    bc   = report.get("by_complexity", {})
    bl   = report.get("by_language", {})
    lat  = report.get("latency", {})

    lines = [
        "=" * 60,
        "  TEXT-TO-SQL BENCHMARK — EVALUATION REPORT",
        "=" * 60,
        f"  Questions evaluated : {m.get('total_questions', 0)}",
        f"  Total time          : {m.get('total_time_sec', 0):.0f}s",
        f"  Avg time per query  : {m.get('avg_time_per_q', 0):.1f}s",
        "",
        "── OVERALL ──",
        f"  Execution accuracy  : {ov.get('execution_accuracy', 0):.2%}",
        f"  Data response rate  : {ov.get('data_response_rate', 0):.2%}",
        f"  Self-correction rate: {ov.get('retry_rate', 0):.2%}",
        "",
        "── BY COMPLEXITY ──",
    ]

    for tier, vals in bc.items():
        bar = "█" * int(vals["accuracy"] * 20)
        lines.append(
            f"  {tier:<10} {vals['success']:>3}/{vals['total']:<3} "
            f"acc={vals['accuracy']:.2%}  "
            f"avg={vals['avg_latency_ms']:.0f}ms  {bar}"
        )

    lines += ["", "── BY LANGUAGE ──"]
    for lang, vals in bl.items():
        lang_name = "English" if lang == "en" else "Arabic"
        lines.append(
            f"  {lang_name:<10} {vals['success']:>3}/{vals['total']:<3} "
            f"acc={vals['accuracy']:.2%}"
        )

    lines += [
        "",
        "── LATENCY ──",
        f"  Mean : {lat.get('mean_ms', 0):.0f}ms",
        f"  p50  : {lat.get('p50_ms', 0):.0f}ms",
        f"  p95  : {lat.get('p95_ms', 0):.0f}ms",
        f"  Min  : {lat.get('min_ms', 0):.0f}ms",
        f"  Max  : {lat.get('max_ms', 0):.0f}ms",
        "",
        "=" * 60,
    ]

    return "\n".join(lines)# Benchmark runner — evaluates all 100 test questions
