# tests/conftest.py
"""
Pytest setup.

Two kinds of tests live in this folder:

  Offline (always run, no API key, no real data):
      test_offline.py — runs on a small synthetic database with the same
      schema as database/sales.db and a fake LLM.

  Live (need OPENAI_API_KEY and/or the real database/benchmark files):
      test_chain.py, test_api.py, test_database.py, test_evaluation.py
      They are skipped automatically when their requirements are missing.

Run:  pytest -q
"""

import os
import random
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

REAL_DB      = "database/sales.db"
RESULTS_JSON = "data/eval/benchmark_results.json"

_has_key = bool(os.getenv("OPENAI_API_KEY", "").startswith("sk-"))
_has_db  = os.path.exists(REAL_DB)

collect_ignore = []
if not (_has_key and _has_db):
    collect_ignore += ["test_chain.py", "test_api.py"]
if not _has_db:
    collect_ignore += ["test_database.py"]
if not (os.path.exists(RESULTS_JSON) and _has_db):
    collect_ignore += ["test_evaluation.py"]


# ─────────────────────────────────────────────
# SYNTHETIC DATABASE
# ─────────────────────────────────────────────

STATES = [
    ("CA", "California", "West"), ("TX", "Texas", "South"),
    ("NY", "New York", "Northeast"), ("IL", "Illinois", "Midwest"),
    ("FL", "Florida", "South"), ("WA", "Washington", "West"),
]
CHANNELS   = ["Wholesale", "Distributor", "Export"]
WAREHOUSES = ["AXW291", "FLR025", "NXH382"]


def build_synthetic_db(path: str, n_orders: int = 600, seed: int = 7) -> str:
    """Create a small database with the production schema (column names
    exactly as loader.py produces them)."""
    rng  = random.Random(seed)
    conn = sqlite3.connect(path)
    c    = conn.cursor()
    c.executescript("""
        CREATE TABLE customers (customer_index INTEGER, customer_name TEXT);
        CREATE TABLE products (product_index INTEGER, product_name TEXT);
        CREATE TABLE regions (id INTEGER, city_name TEXT, county TEXT,
            state_code TEXT, state TEXT, type TEXT, latitude REAL,
            longitude REAL, area_code INTEGER, population INTEGER,
            households INTEGER, median_income INTEGER, land_area INTEGER,
            water_area INTEGER, time_zone TEXT);
        CREATE TABLE state_regions (state_code TEXT, state TEXT, region TEXT);
        CREATE TABLE budgets (product_name TEXT, budget_2017 REAL);
        CREATE TABLE sales_orders (order_number TEXT, order_date TEXT,
            customer_name_index INTEGER, channel TEXT, currency_code TEXT,
            warehouse_code TEXT, delivery_region_index INTEGER,
            product_description_index INTEGER, order_quantity INTEGER,
            unit_price REAL, line_total REAL, total_unit_cost REAL);
    """)
    c.executemany("INSERT INTO customers VALUES (?, ?)",
                  [(i, f"Customer {i} Ltd") for i in range(1, 21)])
    c.executemany("INSERT INTO products VALUES (?, ?)",
                  [(i, f"Product {i}") for i in range(1, 11)])
    c.executemany("INSERT INTO state_regions VALUES (?, ?, ?)", STATES)
    c.executemany("INSERT INTO budgets VALUES (?, ?)",
                  [(f"Product {i}", float(rng.randint(50_000, 400_000)))
                   for i in range(1, 11)])
    regions = []
    for i in range(1, 31):
        code, state, _ = STATES[i % len(STATES)]
        regions.append((i, f"City {i}", f"County {i}", code, state, "City",
                        30.0 + i, -100.0 - i, 200 + i, 10_000 * i, 4_000 * i,
                        40_000 + 500 * i, 100 + i, 5 + i, "America/Chicago"))
    c.executemany(f"INSERT INTO regions VALUES ({','.join('?' * 15)})", regions)
    orders = []
    for n in range(1, n_orders + 1):
        qty   = rng.randint(1, 20)
        price = round(rng.uniform(10, 500), 2)
        total = round(qty * price, 2)
        cost  = round(total * rng.uniform(0.4, 0.9), 2)
        orders.append((
            f"SO-{n:05d}",
            f"20{rng.randint(17, 21)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            rng.randint(1, 20), rng.choice(CHANNELS), "USD",
            rng.choice(WAREHOUSES), rng.randint(1, 30), rng.randint(1, 10),
            qty, price, total, cost,
        ))
    c.executemany(f"INSERT INTO sales_orders VALUES ({','.join('?' * 12)})", orders)
    conn.commit()
    conn.close()
    return path


@pytest.fixture(scope="session")
def synthetic_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "sales.db"
    return build_synthetic_db(str(path))


@pytest.fixture
def audit_log(tmp_path, monkeypatch):
    """Send audit records to a temp file; returns its path."""
    from src.text_to_sql.safety import sql_guard
    path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(sql_guard, "AUDIT_LOG_DIR", str(tmp_path))
    monkeypatch.setattr(sql_guard, "AUDIT_LOG_FILE", str(path))
    return path
