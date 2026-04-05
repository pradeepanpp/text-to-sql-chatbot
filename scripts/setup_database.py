# scripts/setup_database.py
"""
One-time setup: load all CSV files into SQLite.

Run from project root:
    python scripts/setup_database.py

Place your CSV files in data/csv/ first:
    data/csv/Customers.csv
    data/csv/Products.csv
    data/csv/Regions.csv
    data/csv/State_Regions.csv
    data/csv/2017_Budgets.csv
    data/csv/sales_order.csv
"""

import sys
sys.path.append(".")

from src.text_to_sql.database.loader import load_all_csvs, verify_database
from src.text_to_sql.utils.logger import logger


def main():
    logger.info("=" * 50)
    logger.info("  Text-to-SQL — Database Setup")
    logger.info("=" * 50)

    # Build database
    db_path = load_all_csvs(force=True)

    # Verify
    logger.info("\nVerifying database...")
    counts = verify_database(db_path)

    logger.info("\nTable row counts:")
    for table, count in sorted(counts.items()):
        logger.info(f"  {table:<25} {count:>8,} rows")

    logger.info(f"\nTotal tables: {len(counts)}")
    logger.info(f"Database path: {db_path}")
    logger.info("=" * 50)
    


if __name__ == "__main__":
    main()