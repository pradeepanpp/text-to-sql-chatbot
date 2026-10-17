# src/text_to_sql/evaluation/benchmark.py
"""
Benchmark runner.

Runs the evaluation questions through the pipeline and measures:

  execution_accuracy        — generated SQL returns the same rows as the
                              reference SQL (strict; see metrics.py)
  execution_accuracy_lenient— same, but extra columns are allowed
  execution_success_rate    — SQL ran and an answer was produced
                              (NOT a correctness metric; reported so it is
                              never confused with accuracy)
  infra_errors              — rate limits / API errors, reported apart
                              from model mistakes
  router agreement          — router decision vs the dataset's tier label
  latency                   — mean / p50 / p95, with and without infra errors
  95% Wilson confidence intervals on every accuracy

Each question gets an `outcome`:
  correct | correct_extra_columns | wrong_result | sql_error |
  blocked | infra_error

Note on the agent: when the agent answers with several queries, only its
last successful query is compared with the reference, so for multi-step
questions agent accuracy is a lower bound. Those rows are flagged with
agent_multi_query=True for manual review.

Outputs:
  data/eval/benchmark_results[_<tag>].json   ← full results
  data/eval/benchmark_summary[_<tag>].txt    ← readable summary

Run:
    python scripts/run_benchmark.py
"""

import os
import sys
import json
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone

sys.path.append(".")

from dotenv import load_dotenv
load_dotenv()

from src.text_to_sql.chain.common import is_infra_error
from src.text_to_sql.database.executor import execute_readonly
from src.text_to_sql.safety.sql_guard import enforce_row_limit
from src.text_to_sql.evaluation.eval_dataset import EVAL_DATASET
from src.text_to_sql.evaluation.metrics import results_match, wilson_interval
from src.text_to_sql.utils.logger import logger

RESULTS_DIR = "data/eval"
DB_PATH     = os.getenv("DB_PATH", "database/sales.db")

CORRECT_OUTCOMES = {"correct"}
LENIENT_OUTCOMES = {"correct", "correct_extra_columns"}


def _paths(tag: str = "") -> tuple:
    suffix = f"_{tag}" if tag else ""
    return (
        f"{RESULTS_DIR}/benchmark_results{suffix}.json",
        f"{RESULTS_DIR}/benchmark_summary{suffix}.txt",
    )


# ─────────────────────────────────────────────
# EXECUTION HELPERS
# ─────────────────────────────────────────────

def run_sql(sql: str, db_path: str = DB_PATH, row_limit: int = 500) -> tuple:
    """Execute SQL read-only with the same row limit as production. Returns (ok, rows, error)."""
    if not sql:
        return False, [], "no SQL"
    try:
        res = execute_readonly(db_path, enforce_row_limit(sql, row_limit), max_rows=row_limit)
        return True, res.rows, ""
    except Exception as e:
        return False, [], str(e)


def answer_contains_data(natural_response: str) -> bool:
    """True if the answer looks like data rather than an error / 'no results'."""
    if not natural_response:
        return False
    no_data_signals = [
        "no results", "no data", "unable to retrieve",
        "error", "failed", "not found", "لا توجد",
    ]
    lower = natural_response.lower()
    return not any(sig in lower for sig in no_data_signals)


def classify_outcome(result, ref_ok: bool, ref_rows: list,
                     db_path: str = DB_PATH, row_limit: int = 500) -> tuple:
    """Return (outcome, generated_rows_ran_ok)."""
    if result.blocked:
        return "blocked", False
    if is_infra_error(result.error):
        return "infra_error", False
    if not result.execution_success or not result.generated_sql:
        return "sql_error", False

    gen_ok, gen_rows, _ = run_sql(result.generated_sql, db_path, row_limit)
    if not gen_ok or not ref_ok:
        return "sql_error", gen_ok
    if results_match(ref_rows, gen_rows, allow_extra_columns=False):
        return "correct", True
    if results_match(ref_rows, gen_rows, allow_extra_columns=True):
        return "correct_extra_columns", True
    return "wrong_result", True


# ─────────────────────────────────────────────
# BENCHMARK RUNNER
# ─────────────────────────────────────────────

def run_benchmark(
    sample_size:       int   = None,
    complexity_filter: str   = None,
    language_filter:   str   = None,
    strategy:          str   = None,
    allow_fallback:    bool  = True,
    delay_s:           float = 0.0,
    tag:               str   = "",
    chain                    = None,
    db_path:           str   = DB_PATH,
) -> dict:
    """
    Run the evaluation benchmark.

    Args:
        sample_size:       limit to the first N questions
        complexity_filter: only 'simple' / 'medium' / 'complex'
        language_filter:   only 'en' / 'ar'
        strategy:          force 'simple' / 'cot' / 'agent' (bypass router)
        allow_fallback:    False = measure a strategy without self-correction
        delay_s:           pause between questions (avoid rate limits)
        tag:               suffix for output files (e.g. ablation runs)
        chain:             pre-built TextToSQLChain (tests inject a fake LLM)
    """
    os.makedirs(RESULTS_DIR, exist_ok=True)

    dataset = EVAL_DATASET
    if complexity_filter:
        dataset = [q for q in dataset if q["complexity"] == complexity_filter]
    if language_filter:
        dataset = [q for q in dataset if q["language"] == language_filter]
    if sample_size:
        dataset = dataset[:sample_size]

    logger.info("=" * 56)
    logger.info(
        f"  Benchmark — {len(dataset)} questions | "
        f"strategy={strategy or 'router'} fallback={allow_fallback}"
    )
    logger.info("=" * 56)

    if chain is None:
        from src.text_to_sql.chain.sql_chain import TextToSQLChain
        chain = TextToSQLChain(db_path=db_path)
    row_limit = chain.guard.row_limit

    results     = []
    total_start = time.perf_counter()

    for i, item in enumerate(dataset, 1):
        question = item["question"]
        logger.info(f"[{i}/{len(dataset)}] {question[:60]}")

        t0 = time.perf_counter()
        result = chain.query(question, strategy=strategy, allow_fallback=allow_fallback)
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)

        ref_ok, ref_rows, ref_err = run_sql(item["reference_sql"], db_path, row_limit)
        outcome, _ = classify_outcome(result, ref_ok, ref_rows, db_path, row_limit)

        results.append({
            "index":                i,
            "question":             question,
            "complexity":           item["complexity"],
            "router_complexity":    result.complexity,
            "strategy":             result.strategy,
            "language":             item["language"],
            "tables":               item["tables"],
            "reference_sql":        item["reference_sql"],
            "reference_valid":      ref_ok,
            "reference_error":      ref_err,
            "generated_sql":        result.generated_sql,
            "agent_queries":        result.agent_queries,
            "agent_multi_query":    len(result.agent_queries) > 1,
            "outcome":              outcome,
            "execution_success":    result.execution_success,
            "has_data_in_response": answer_contains_data(result.natural_response),
            "fallback_used":        result.fallback_used,
            "retries_used":         result.retries_used,
            "blocked":              result.blocked,
            "detected_language":    result.detected_language,
            "natural_response":     result.natural_response,
            "error":                result.error,
            "latency_ms":           latency_ms,
        })

        logger.info(f"  → {outcome} | {latency_ms:.0f}ms | strategy={result.strategy}")
        if delay_s:
            time.sleep(delay_s)

    total_time = round(time.perf_counter() - total_start, 1)
    report     = compute_metrics(results, total_time)
    report["meta"].update({
        "timestamp":      datetime.now(timezone.utc).isoformat(),
        "strategy":       strategy or "router",
        "allow_fallback": allow_fallback,
        "model":          getattr(chain.llm, "model_name", type(chain.llm).__name__),
        "row_limit":      row_limit,
    })

    results_json, summary_txt = _paths(tag)
    with open(results_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    with open(summary_txt, "w", encoding="utf-8") as f:
        f.write(format_summary(report))
    logger.info(f"Results saved → {results_json}")
    logger.info(f"Summary saved → {summary_txt}")

    return report


# ─────────────────────────────────────────────
# METRICS
# ─────────────────────────────────────────────

def _group_metrics(rows: list) -> dict:
    n        = len(rows)
    correct  = sum(1 for r in rows if r["outcome"] in CORRECT_OUTCOMES)
    lenient  = sum(1 for r in rows if r["outcome"] in LENIENT_OUTCOMES)
    success  = sum(1 for r in rows if r["execution_success"])
    infra    = sum(1 for r in rows if r["outcome"] == "infra_error")
    lat      = [r["latency_ms"] for r in rows]
    return {
        "total":                  n,
        "correct":                correct,
        "accuracy":               round(correct / n, 4) if n else 0.0,
        "accuracy_ci95":          wilson_interval(correct, n),
        "accuracy_lenient":       round(lenient / n, 4) if n else 0.0,
        "execution_success_rate": round(success / n, 4) if n else 0.0,
        "infra_errors":           infra,
        "avg_latency_ms":         round(sum(lat) / n, 1) if n else 0.0,
    }


def compute_metrics(results: list, total_time: float) -> dict:
    """Compute all metrics from per-question records."""
    total = len(results)
    if total == 0:
        return {}

    outcomes = Counter(r["outcome"] for r in results)
    correct  = outcomes["correct"]
    lenient  = correct + outcomes["correct_extra_columns"]
    infra    = outcomes["infra_error"]
    non_infra_total = total - infra

    by_complexity = {
        tier: _group_metrics([r for r in results if r["complexity"] == tier])
        for tier in ("simple", "medium", "complex")
        if any(r["complexity"] == tier for r in results)
    }
    by_language = {
        lang: _group_metrics([r for r in results if r["language"] == lang])
        for lang in ("en", "ar")
        if any(r["language"] == lang for r in results)
    }
    by_strategy = defaultdict(list)
    for r in results:
        by_strategy[r["strategy"] or "none"].append(r)

    # Router: decision vs dataset label
    confusion = defaultdict(Counter)
    for r in results:
        confusion[r["complexity"]][r["router_complexity"]] += 1
    router_agree = sum(1 for r in results if r["complexity"] == r["router_complexity"])

    fallback_used    = sum(1 for r in results if r["fallback_used"])
    fallback_rescued = sum(
        1 for r in results if r["fallback_used"] and r["execution_success"]
    )

    latencies = sorted(r["latency_ms"] for r in results)
    lat_ok    = [r["latency_ms"] for r in results if r["outcome"] != "infra_error"]
    n         = len(latencies)

    return {
        "meta": {
            "total_questions": total,
            "total_time_sec":  total_time,
            "avg_time_per_q":  round(total_time / total, 1),
            "metric": (
                "execution_accuracy = generated SQL returns the same rows as "
                "the reference SQL (row/column order ignored, numbers rounded "
                "to 2 dp). Lenient also accepts extra columns."
            ),
        },
        "overall": {
            "execution_accuracy":           round(correct / total, 4),
            "execution_accuracy_ci95":      wilson_interval(correct, total),
            "execution_accuracy_lenient":   round(lenient / total, 4),
            "execution_accuracy_excl_infra": (
                round(correct / non_infra_total, 4) if non_infra_total else 0.0
            ),
            "execution_success_rate": round(
                sum(1 for r in results if r["execution_success"]) / total, 4
            ),
            "data_response_rate": round(
                sum(1 for r in results if r["has_data_in_response"]) / total, 4
            ),
            "infra_errors":      infra,
            "blocked":           outcomes["blocked"],
            "reference_errors":  sum(1 for r in results if not r["reference_valid"]),
            "fallback_used":     fallback_used,
            "fallback_rescued":  fallback_rescued,
            "total_retries":     sum(r["retries_used"] for r in results),
            "retry_rate":        round(fallback_used / total, 4),
        },
        "outcomes":      dict(outcomes),
        "by_complexity": by_complexity,
        "by_language":   by_language,
        "by_strategy":   {k: _group_metrics(v) for k, v in sorted(by_strategy.items())},
        "router": {
            "agreement_with_labels": round(router_agree / total, 4),
            "confusion": {label: dict(c) for label, c in confusion.items()},
        },
        "latency": {
            "mean_ms":             round(sum(latencies) / n, 1),
            "p50_ms":              latencies[n // 2],
            "p95_ms":              latencies[min(n - 1, int(n * 0.95))],
            "min_ms":              latencies[0],
            "max_ms":              latencies[-1],
            "mean_ms_excl_infra":  round(sum(lat_ok) / len(lat_ok), 1) if lat_ok else 0.0,
        },
        "detailed_results": results,
    }


def _pct(x: float) -> str:
    return f"{x:.1%}"


def _ci(ci: list) -> str:
    return f"[{ci[0]:.0%}–{ci[1]:.0%}]"


def format_summary(report: dict) -> str:
    """Build human-readable summary string."""
    m, ov, lat = report["meta"], report["overall"], report["latency"]
    lines = [
        "=" * 64,
        "  TEXT-TO-SQL BENCHMARK — EVALUATION REPORT",
        "=" * 64,
        f"  Questions evaluated : {m['total_questions']}",
        f"  Strategy / fallback : {m.get('strategy', 'router')} / {m.get('allow_fallback', True)}",
        f"  Total time          : {m['total_time_sec']:.0f}s",
        "",
        "── OVERALL ──",
        f"  Execution accuracy (strict)  : {_pct(ov['execution_accuracy'])}  "
        f"95% CI {_ci(ov['execution_accuracy_ci95'])}",
        f"  Execution accuracy (lenient) : {_pct(ov['execution_accuracy_lenient'])}",
        f"  Accuracy excl. infra errors  : {_pct(ov['execution_accuracy_excl_infra'])}",
        f"  SQL ran + answered (not accuracy): {_pct(ov['execution_success_rate'])}",
        f"  Infra errors (rate limit/API): {ov['infra_errors']}",
        f"  Fallback used / rescued      : {ov['fallback_used']} / {ov['fallback_rescued']}",
        f"  Outcomes: {report['outcomes']}",
        "",
        "── BY COMPLEXITY (dataset label) ──",
    ]
    for tier, v in report["by_complexity"].items():
        lines.append(
            f"  {tier:<8} {v['correct']:>3}/{v['total']:<3} acc={_pct(v['accuracy'])} "
            f"{_ci(v['accuracy_ci95'])}  lenient={_pct(v['accuracy_lenient'])}  "
            f"avg={v['avg_latency_ms']:.0f}ms"
        )
    lines += ["", "── BY LANGUAGE ──"]
    for lang, v in report["by_language"].items():
        name = "English" if lang == "en" else "Arabic"
        lines.append(
            f"  {name:<8} {v['correct']:>3}/{v['total']:<3} acc={_pct(v['accuracy'])} "
            f"{_ci(v['accuracy_ci95'])}"
        )
    lines += ["", "── BY STRATEGY (what ran first) ──"]
    for s, v in report["by_strategy"].items():
        lines.append(
            f"  {s:<8} {v['correct']:>3}/{v['total']:<3} acc={_pct(v['accuracy'])}  "
            f"avg={v['avg_latency_ms']:.0f}ms"
        )
    lines += [
        "",
        "── ROUTER ──",
        f"  Agreement with dataset labels: {_pct(report['router']['agreement_with_labels'])}",
        f"  Confusion (label → router): {report['router']['confusion']}",
        "",
        "── LATENCY ──",
        f"  Mean {lat['mean_ms']:.0f}ms | excl. infra {lat['mean_ms_excl_infra']:.0f}ms | "
        f"p50 {lat['p50_ms']:.0f}ms | p95 {lat['p95_ms']:.0f}ms | max {lat['max_ms']:.0f}ms",
        "=" * 64,
    ]
    return "\n".join(lines)


# Backwards-compatible names
_compute_metrics = compute_metrics
_format_summary  = format_summary
