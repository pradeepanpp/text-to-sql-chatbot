import json
import os

from src.text_to_sql.database.executor import execute_readonly
from src.text_to_sql.evaluation import benchmark
from src.text_to_sql.evaluation.eval_dataset import EVAL_DATASET, get_by_complexity, get_by_language
from src.text_to_sql.evaluation.metrics import results_match, wilson_interval
from tests.conftest import make_chain


# Dataset

def test_dataset_shape():
    assert len(EVAL_DATASET) == 100
    for item in EVAL_DATASET:
        assert set(item) >= {"question", "reference_sql", "reference_ans", "complexity", "language", "tables"}
        assert item["reference_sql"].strip().upper().startswith("SELECT")
        assert item["complexity"] in {"simple", "medium", "complex"}
        assert item["language"] in {"en", "ar"}
    assert [len(get_by_complexity(t)) for t in ("simple", "medium", "complex")] == [40, 35, 25]
    assert [len(get_by_language(lang)) for lang in ("en", "ar")] == [85, 15]


def test_all_reference_sql_runs(synthetic_db):
    for item in EVAL_DATASET:
        execute_readonly(synthetic_db, item["reference_sql"])  # raises on error


# Metrics

def test_results_match_rules():
    ref = [("A", 10.0), ("B", 5.0)]
    assert results_match(ref, [(5.0, "B"), (10.004, "A")])                # row/column order, rounding
    assert not results_match(ref, [("A", 10.0), ("B", 6.0)])              # wrong value
    assert not results_match(ref, [("A", 10.0, 1), ("B", 5.0, 2)])        # extra column, strict
    assert results_match(ref, [("A", 10.0, 1), ("B", 5.0, 2)], allow_extra_columns=True)
    assert not results_match([("A",)], [("A",), ("B",)])                  # extra row


def test_wilson_interval():
    low, high = wilson_interval(15, 15)
    assert 0.79 < low < 0.80 and high == 1.0
    assert wilson_interval(0, 0) == (0.0, 0.0)


def test_benchmark_scores_results_not_execution(synthetic_db, tmp_path, monkeypatch):
    """A query that runs but returns the wrong data must count as wrong."""
    monkeypatch.setattr(benchmark, "RESULTS_DIR", str(tmp_path))
    chain = make_chain(
        synthetic_db,
        "SELECT COUNT(*) FROM customers", "20 customers.",               # Q1: correct
        "SELECT customer_index FROM customers", "Here are the names.",   # Q2: runs, wrong column
    )
    report = benchmark.run_benchmark(sample_size=2, chain=chain, db_path=synthetic_db)
    assert [r["outcome"] for r in report["detailed_results"]] == ["correct", "wrong_result"]
    assert report["overall"]["execution_accuracy"] == 0.5
    assert report["overall"]["execution_success_rate"] == 1.0  # both ran: not accuracy
    saved = json.loads((tmp_path / "benchmark_results.json").read_text(encoding="utf-8"))
    assert saved["overall"]["execution_accuracy"] == 0.5
    assert (tmp_path / "benchmark_summary.txt").exists()


# Saved benchmark report (skipped until scripts/run_benchmark.py has run)

def test_report_structure(report):
    for key in ["meta", "overall", "by_complexity", "by_language", "latency", "detailed_results"]:
        assert key in report
    assert report["meta"]["total_questions"] == len(report["detailed_results"]) > 0
    assert 0.0 <= report["overall"]["execution_accuracy"] <= 1.0
    assert 0.0 <= report["overall"]["data_response_rate"] <= 1.0
    assert os.path.exists("data/eval/benchmark_summary.txt")
    lat = report["latency"]
    assert lat["min_ms"] <= lat["p50_ms"] <= lat["p95_ms"] <= lat["max_ms"]
    for vals in report["by_complexity"].values():
        assert 0.0 <= vals["accuracy"] <= 1.0
    for r in report["detailed_results"]:
        assert r["retries_used"] >= 0 and r["detected_language"] in ("en", "ar")


def test_report_quality(report):
    """Regression gate: fail loudly if a new run is clearly worse."""
    assert report["overall"]["execution_accuracy"] >= 0.50
    if "simple" in report["by_complexity"]:
        assert report["by_complexity"]["simple"]["accuracy"] >= 0.70
