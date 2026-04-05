# src/text_to_sql/constants.py
"""
Project-wide constants.
"""

# ── Table names ──────────────────────────────
TABLE_CUSTOMERS   = "customers"
TABLE_PRODUCTS    = "products"
TABLE_REGIONS     = "regions"
TABLE_STATE_REGIONS = "state_regions"
TABLE_BUDGETS     = "budgets"
TABLE_SALES       = "sales_orders"

ALL_TABLES = [
    TABLE_CUSTOMERS,
    TABLE_PRODUCTS,
    TABLE_REGIONS,
    TABLE_STATE_REGIONS,
    TABLE_BUDGETS,
    TABLE_SALES,
]

# ── Table descriptions for LLM context ───────
TABLE_DESCRIPTIONS = {
    TABLE_CUSTOMERS: (
        "Contains customer information. "
        "Columns: customer_index (INT, primary key), "
        "customer_name (TEXT, company name)."
    ),
    TABLE_PRODUCTS: (
        "Contains product catalog. "
        "Columns: product_index (INT, primary key), "
        "product_name (TEXT, e.g. 'Product 1')."
    ),
    TABLE_REGIONS: (
        "Contains US city and region geographic data. "
        "Columns: id, name (city), county, state_code, state, type, "
        "latitude, longitude, population, median_income, time_zone."
    ),
    TABLE_STATE_REGIONS: (
        "Maps US state codes to region names (North, South, East, West). "
        "Columns: state_code (TEXT), state (TEXT), region (TEXT)."
    ),
    TABLE_BUDGETS: (
        "Contains 2017 annual budget targets per product. "
        "Columns: product_name (TEXT), budget_2017 (REAL)."
    ),
    TABLE_SALES: (
        "Main sales transactions table — largest table (~11,000 rows). "
        "Columns: order_number, order_date, customer_name_index (FK→customers), "
        "channel (Wholesale/Distributor/Retail), currency_code, warehouse_code, "
        "delivery_region_index (FK→regions), product_description_index (FK→products), "
        "order_quantity (INT), unit_price (REAL), line_total (REAL), "
        "total_unit_cost (REAL)."
    ),
}

# ── Query complexity tiers ────────────────────
COMPLEXITY_SIMPLE  = "simple"    # single table, no joins
COMPLEXITY_MEDIUM  = "medium"    # 2 tables, simple join or group by
COMPLEXITY_COMPLEX = "complex"   # 3+ tables, subqueries, aggregations

# ── SQL safety — blocked operations ──────────
BLOCKED_SQL_KEYWORDS = [
    "DROP", "DELETE", "UPDATE", "INSERT",
    "ALTER", "CREATE", "TRUNCATE", "REPLACE",
    "GRANT", "REVOKE",
]

# ── Self-correction ───────────────────────────
MAX_SQL_RETRIES = 3

# ── Response language ─────────────────────────
LANG_ENGLISH = "en"
LANG_ARABIC  = "ar"