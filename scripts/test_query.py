# scripts/test_query.py
"""
Smoke test — verifies the full pipeline end-to-end.
Run after setup_database.py and setting OPENAI_API_KEY.

    python scripts/test_query.py
"""

import sys
sys.path.append(".")

from dotenv import load_dotenv
load_dotenv()

from src.text_to_sql.chain.sql_chain import TextToSQLChain
from src.text_to_sql.utils.logger import logger


TEST_QUESTIONS = [
    # English — simple
    "How many customers are in the database?",
    # English — aggregation
    "What is the total line total across all sales orders?",
    # English — filter
    "What are the names of all products?",
    # English — join
    "What is the total sales amount for Wholesale channel?",
    # Arabic
    "كم عدد العملاء في قاعدة البيانات؟",   # How many customers?
]


def main():
    logger.info("=" * 52)
    logger.info("  Text-to-SQL — Pipeline Smoke Test")
    logger.info("=" * 52)

    chain = TextToSQLChain()

    for i, question in enumerate(TEST_QUESTIONS, 1):
        logger.info(f"\n[Query {i}] {question}")
        logger.info("-" * 40)

        result = chain.query(question)

        logger.info(f"Language   : {result.detected_language}")
        if result.detected_language == "ar":
            logger.info(f"Translated : {result.english_question}")
        logger.info(f"SQL        : {result.generated_sql}")
        logger.info(f"Success    : {result.execution_success}")
        logger.info(f"Retries    : {result.retries_used}")
        logger.info(f"Response   : {result.natural_response}")

        if result.error and not result.execution_success:
            logger.error(f"Error      : {result.error}")

    logger.info("\n" + "=" * 52)
    logger.info("  Smoke test complete")
    logger.info("=" * 52)


if __name__ == "__main__":
    main()