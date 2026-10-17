"""Load the six CSV files into the SQLite database (run once via scripts/setup_database.py)."""

import os
import sqlite3

import pandas as pd

from src.text_to_sql.constants import (
    TABLE_BUDGETS, TABLE_CUSTOMERS, TABLE_PRODUCTS, TABLE_REGIONS, TABLE_SALES, TABLE_STATE_REGIONS,
)
from src.text_to_sql.utils.logger import logger

DATA_DIR = "data/csv"
DB_PATH = "database/sales.db"

# CSV file -> (table name, {CSV column: database column})
CSV_CONFIG = {
    "Customers.csv": (
        TABLE_CUSTOMERS,
        {
            "Customer Index": "customer_index",
            "Customer Names": "customer_name",
        }
    ),
    "Products.csv": (
        TABLE_PRODUCTS,
        {
            "Index":        "product_index",
            "Product Name": "product_name",
        }
    ),
    "Regions.csv": (
        TABLE_REGIONS,
        {
            "id":            "id",
            "name":          "city_name",
            "county":        "county",
            "state_code":    "state_code",
            "state":         "state",
            "type":          "type",
            "latitude":      "latitude",
            "longitude":     "longitude",
            "area_code":     "area_code",
            "population":    "population",
            "households":    "households",
            "median_income": "median_income",
            "land_area":     "land_area",
            "water_area":    "water_area",
            "time_zone":     "time_zone",
        }
    ),
    "State_Regions.csv": (
        TABLE_STATE_REGIONS,
        {
            "State Code": "state_code",
            "State":      "state",
            "Region":     "region",
        }
    ),
    "2017_Budgets.csv": (
        TABLE_BUDGETS,
        {
            "Product Name":  "product_name",
            "2017 Budgets":  "budget_2017",
        }
    ),
    "sales_order.csv": (
        TABLE_SALES,
        {
            "OrderNumber":               "order_number",
            "OrderDate":                 "order_date",
            "Customer Name Index":       "customer_name_index",
            "Channel":                   "channel",
            "Currency Code":             "currency_code",
            "Warehouse Code":            "warehouse_code",
            "Delivery Region Index":     "delivery_region_index",
            "Product Description Index": "product_description_index",
            "Order Quantity":            "order_quantity",
            "Unit Price":                "unit_price",
            "Line Total":                "line_total",
            "Total Unit Cost":           "total_unit_cost",
        }
    ),
}


def load_all_csvs(data_dir: str = DATA_DIR, db_path: str = DB_PATH, force: bool = False) -> str:
    """Build the database from the CSVs. Returns the absolute database path."""
    if os.path.exists(db_path) and not force:
        logger.info(f"Database already exists: {db_path} (use force=True to rebuild)")
        return os.path.abspath(db_path)

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    logger.info(f"Building SQLite database at {db_path}...")
    conn = sqlite3.connect(db_path)

    loaded = []
    for csv_file, (table, renames) in CSV_CONFIG.items():
        csv_path = os.path.join(data_dir, csv_file)
        if not os.path.exists(csv_path):
            logger.warning(f"  Missing CSV: {csv_path}, skipping {table}")
            continue
        try:
            df = pd.read_csv(csv_path)
            df = df.rename(columns={k: v for k, v in renames.items() if k in df.columns})
            df.to_sql(table, conn, if_exists="replace", index=False)
            loaded.append(table)
            logger.info(f"  {table:<20} {len(df):>7,} rows  ({csv_file})")
        except Exception as e:
            logger.error(f"  Failed to load {csv_file}: {e}")

    conn.close()
    logger.info(f"Database ready: {len(loaded)}/6 tables loaded")
    return os.path.abspath(db_path)


def verify_database(db_path: str = DB_PATH) -> dict:
    """Return {table: row count}."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}\nRun: python scripts/setup_database.py")

    conn = sqlite3.connect(db_path)
    tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    conn.close()
    return counts
