"""
Build database/sales.db from the CSV files in data/csv/
(Customers, Products, Regions, State_Regions, 2017_Budgets, sales_order).

Run from the project root:  python scripts/setup_database.py
"""

import sys

sys.path.append(".")

from src.text_to_sql.database.loader import load_all_csvs, verify_database
from src.text_to_sql.utils.logger import logger


def main():
    db_path = load_all_csvs(force=True)
    counts = verify_database(db_path)
    for table, count in sorted(counts.items()):
        logger.info(f"  {table:<25} {count:>8,} rows")
    logger.info(f"{len(counts)} tables in {db_path}")


if __name__ == "__main__":
    main()
