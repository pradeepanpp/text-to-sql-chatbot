"""
Smoke test of the whole pipeline with the real model and database.
Needs OPENAI_API_KEY and database/sales.db.

Run:  python scripts/test_query.py
"""

import sys

sys.path.append(".")

from dotenv import load_dotenv

load_dotenv()

from src.text_to_sql.chain.sql_chain import TextToSQLChain
from src.text_to_sql.utils.logger import logger

QUESTIONS = [
    "How many customers are in the database?",
    "What is the total line total across all sales orders?",
    "What are the names of all products?",
    "What is the total sales amount for Wholesale channel?",
    "كم عدد العملاء في قاعدة البيانات؟",  # How many customers?
]


def main():
    chain = TextToSQLChain()
    for i, question in enumerate(QUESTIONS, 1):
        result = chain.query(question)
        logger.info(f"[{i}] {question}")
        if result.detected_language == "ar":
            logger.info(f"    Translated: {result.english_question}")
        logger.info(f"    SQL:      {result.generated_sql}")
        logger.info(f"    Success:  {result.execution_success} (retries {result.retries_used})")
        logger.info(f"    Answer:   {result.natural_response}")
        if result.error and not result.execution_success:
            logger.error(f"    Error:    {result.error}")


if __name__ == "__main__":
    main()
