# scripts/run_benchmark.py
"""
Run the full 100-question benchmark evaluation.

Options:
    --sample N     run only first N questions (default: all 100)
    --complexity   run only simple/medium/complex
    --language     run only en/ar

Examples:
    python scripts/run_benchmark.py
    python scripts/run_benchmark.py --sample 20
    python scripts/run_benchmark.py --complexity simple
    python scripts/run_benchmark.py --language ar
"""

import sys
import argparse
sys.path.append(".")

from dotenv import load_dotenv
load_dotenv()

from src.text_to_sql.evaluation.benchmark import run_benchmark
from src.text_to_sql.evaluation.eval_dataset import get_summary
from src.text_to_sql.utils.logger import logger


def main():
    parser = argparse.ArgumentParser(description="Run Text-to-SQL benchmark")
    parser.add_argument("--sample",     type=int, default=None,
                        help="Number of questions to evaluate (default: all)")
    parser.add_argument("--complexity", type=str, default=None,
                        choices=["simple", "medium", "complex"],
                        help="Filter by complexity tier")
    parser.add_argument("--language",   type=str, default=None,
                        choices=["en", "ar"],
                        help="Filter by language")
    args = parser.parse_args()

    # Show dataset summary
    summary = get_summary()
    logger.info(f"Dataset: {summary}")

    # Run benchmark
    report = run_benchmark(
        sample_size        = args.sample,
        complexity_filter  = args.complexity,
        language_filter    = args.language,
    )

    logger.info("Benchmark complete.")
    logger.info("Next → python tests/test_evaluation.py")


if __name__ == "__main__":
    main()