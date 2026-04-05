# src/text_to_sql/database/loader.py


import os
import sqlite3
import pandas as pd
from src.text_to_sql.utils.logger import logger
from src.text_to_sql.constants import (
    TABLE_CUSTOMERS, TABLE_PRODUCTS, TABLE_REGIONS,
    TABLE_STATE_REGIONS, TABLE_BUDGETS, TABLE_SALES,
)

# ── Paths ─────────────────────────────────────
DATA_DIR = "data/csv"
DB_PATH  = "database/sales.db"

# ── CSV filename → (table_name, column_rename_map) ──
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


def load_all_csvs(
    data_dir: str = DATA_DIR,
    db_path:  str = DB_PATH,
    force:    bool = False
) -> str:
    """
    Load all CSVs into SQLite.

    Args:
        data_dir: folder containing the CSV files
        db_path:  path to create/overwrite the SQLite database
        force:    if True, rebuild even if db already exists

    Returns:
        Absolute path to the created database
    """
    # Skip if already built
    if os.path.exists(db_path) and not force:
        logger.info(f"Database already exists: {db_path} (use force=True to rebuild)")
        return os.path.abspath(db_path)

    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    logger.info(f"Building SQLite database at {db_path}...")
    conn = sqlite3.connect(db_path)

    loaded = []
    for csv_file, (table_name, col_map) in CSV_CONFIG.items():
        csv_path = os.path.join(data_dir, csv_file)
        if not os.path.exists(csv_path):
            logger.warning(f"  Missing CSV: {csv_path} — skipping {table_name}")
            continue

        try:
            df = pd.read_csv(csv_path)

            # Rename columns to clean snake_case names
            # Only rename columns that exist in the file
            existing_renames = {
                k: v for k, v in col_map.items() if k in df.columns
            }
            df = df.rename(columns=existing_renames)

            # Write to SQLite — replace if exists
            df.to_sql(table_name, conn, if_exists="replace", index=False)
            loaded.append(table_name)
            logger.info(f"  ✓ {table_name:<20} {len(df):>7,} rows  ({csv_file})")

        except Exception as e:
            logger.error(f"  ✗ Failed to load {csv_file}: {e}")

    conn.close()
    logger.info(f"Database ready: {len(loaded)}/6 tables loaded")
    return os.path.abspath(db_path)


def verify_database(db_path: str = DB_PATH) -> dict:
    """
    Verify all tables exist and return row counts.

    Returns:
        dict mapping table_name → row_count
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"Database not found: {db_path}\n"
            "Run: python scripts/setup_database.py"
        )

    conn   = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    counts = {}
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        counts[table] = cursor.fetchone()[0]

    conn.close()
    return counts