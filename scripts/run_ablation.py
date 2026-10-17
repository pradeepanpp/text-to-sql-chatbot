# scripts/run_ablation.py
"""
Reproducible ablation study.

Runs the benchmark once per configuration and writes a comparison table
to data/eval/ablation.md. Every number in the README's ablation table
should come from this script.

Configurations:
    simple_only    every question → Simple Chain, no fallback
    cot_only       every question → CoT Chain, no fallback
    agent_only     every question → ReAct agent, no fallback
    router         router picks the strategy, no fallback
    full_system    router + self-correction fallback (production setting)

Cost note: 5 configs × 100 questions ≈ 500 pipeline runs with
gpt-4o-mini. Use --sample to try it on a subset first.

Note: --sample takes the FIRST N questions, and the first 40 are all
simple. Use the full set (no --sample) for a meaningful comparison.

Run:
    python scripts/run_ablation.py
"""

import sys
import argparse
sys.path.append(".")

from dotenv import load_dotenv
load_dotenv()

from src.text_to_sql.evaluation.benchmark import run_benchmark, RESULTS_DIR
from src.text_to_sql.utils.logger import logger

CONFIGS = [
    # tag,           strategy, allow_fallback
    ("simple_only",  "simple", False),
    ("cot_only",     "cot",    False),
    ("agent_only",   "agent",  False),
    ("router",       None,     False),
    ("full_system",  None,     True),
]


def _tier(bc: dict, tier: str) -> str:
    """Accuracy for one tier, or '—' if the sample has no questions of that tier."""
    if tier not in bc:
        return "—"
    return f"{bc[tier]['accuracy']:.0%} (n={bc[tier]['total']})"


def main():
    parser = argparse.ArgumentParser(description="Run ablation study")
    parser.add_argument("--sample", type=int, default=None)
    parser.add_argument("--delay",  type=float, default=0.0)
    parser.add_argument("--only",   nargs="*", help="subset of config tags")
    args = parser.parse_args()

    rows = []
    for tag, strategy, fallback in CONFIGS:
        if args.only and tag not in args.only:
            continue
        logger.info(f"\n### Ablation config: {tag}")
        report = run_benchmark(
            sample_size=args.sample, strategy=strategy,
            allow_fallback=fallback, delay_s=args.delay, tag=tag,
        )
        ov, bc, lat = report["overall"], report["by_complexity"], report["latency"]
        ci = ov["execution_accuracy_ci95"]
        rows.append(
            f"| {tag} | {ov['execution_accuracy']:.1%} ({ci[0]:.0%}–{ci[1]:.0%}) "
            f"| {_tier(bc, 'simple')} | {_tier(bc, 'medium')} | {_tier(bc, 'complex')} "
            f"| {lat['p50_ms'] / 1000:.1f}s | {lat['mean_ms_excl_infra'] / 1000:.1f}s "
            f"| {ov['infra_errors']} |"
        )

    n = args.sample or 100
    table = "\n".join([
        f"Ablation — {n} questions, execution accuracy (strict, 95% Wilson CI)",
        "",
        "| Config | Accuracy (95% CI) | Simple | Medium | Complex | p50 latency | Mean latency* | Infra errors |",
        "|---|---|---|---|---|---|---|---|",
        *rows,
        "",
        "*mean excluding rate-limit / API errors",
    ])
    path = f"{RESULTS_DIR}/ablation.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(table + "\n")
    print(table)
    logger.info(f"Ablation table saved → {path}")


if __name__ == "__main__":
    main()