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
        "One row per US city (delivery location). "
        "Columns: id (primary key), city_name, county, state_code, state, type, "
        "latitude, longitude, area_code, population, households, median_income, "
        "land_area, water_area, time_zone."
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
        "Main sales transactions table — the largest table, one row per order line. "
        "Columns: order_number, order_date, customer_name_index (FK→customers), "
        "channel, currency_code, warehouse_code, "
        "delivery_region_index (FK→regions.id), product_description_index (FK→products), "
        "order_quantity (INT), unit_price (REAL), line_total (REAL), "
        "total_unit_cost (REAL, cost of ONE unit; line cost = order_quantity * total_unit_cost)."
    ),
}

# ── Query complexity tiers ────────────────────
COMPLEXITY_SIMPLE  = "simple"    # single table, no joins
COMPLEXITY_MEDIUM  = "medium"    # 2 tables, simple join or group by
COMPLEXITY_COMPLEX = "complex"   # 3+ tables, subqueries, aggregations

# ── Self-correction ───────────────────────────
MAX_SQL_RETRIES = 3

# ── Response language ─────────────────────────
LANG_ENGLISH = "en"
LANG_ARABIC  = "ar"