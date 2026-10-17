# scripts/run_benchmark.py
"""
Run the benchmark evaluation.

Options:
    --sample N        run only the first N questions (default: all 100)
    --complexity      run only simple / medium / complex
    --language        run only en / ar
    --strategy        force simple / cot / agent (bypass the router)
    --no-fallback     disable the self-correction fallback
    --delay S         pause S seconds between questions (rate limits)
    --tag NAME        write results to benchmark_results_NAME.json

Examples:
    python scripts/run_benchmark.py
    python scripts/run_benchmark.py --sample 20
    python scripts/run_benchmark.py --strategy cot --no-fallback --tag cot_only
    python scripts/run_benchmark.py --language ar
"""

import sys
import argparse
sys.path.append(".")

from dotenv import load_dotenv
load_dotenv()

from src.text_to_sql.evaluation.benchmark import run_benchmark, format_summary
from src.text_to_sql.evaluation.eval_dataset import get_summary
from src.text_to_sql.utils.logger import logger


def main():
    parser = argparse.ArgumentParser(description="Run Text-to-SQL benchmark")
    parser.add_argument("--sample",     type=int, default=None)
    parser.add_argument("--complexity", choices=["simple", "medium", "complex"])
    parser.add_argument("--language",   choices=["en", "ar"])
    parser.add_argument("--strategy",   choices=["simple", "cot", "agent"])
    parser.add_argument("--no-fallback", action="store_true")
    parser.add_argument("--delay",      type=float, default=0.0)
    parser.add_argument("--tag",        type=str, default="")
    args = parser.parse_args()

    logger.info(f"Dataset: {get_summary()}")

    report = run_benchmark(
        sample_size       = args.sample,
        complexity_filter = args.complexity,
        language_filter   = args.language,
        strategy          = args.strategy,
        allow_fallback    = not args.no_fallback,
        delay_s           = args.delay,
        tag               = args.tag,
    )
    print(format_summary(report))


if __name__ == "__main__":
    main()
