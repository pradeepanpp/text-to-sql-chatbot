"""
Shared fixtures.

Offline tests use a small synthetic database with the production schema
and a scripted fake LLM, so they need no API key and no data (this is
what CI runs). Live tests use fixtures that skip themselves when the
OpenAI key, the real database or the benchmark report is missing.
"""

import json
import os
import random
import sqlite3

import pytest
from dotenv import load_dotenv
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

load_dotenv()

REAL_DB = "database/sales.db"
RESULTS_JSON = "data/eval/benchmark_results.json"

STATES = [
    ("CA", "California", "West"), ("TX", "Texas", "South"),
    ("NY", "New York", "Northeast"), ("IL", "Illinois", "Midwest"),
    ("FL", "Florida", "South"), ("WA", "Washington", "West"),
]
CHANNELS = ["Wholesale", "Distributor", "Export"]
WAREHOUSES = ["AXW291", "FLR025", "NXH382"]


def build_synthetic_db(path: str, n_orders: int = 600, seed: int = 7) -> str:
    """Small database with the production schema (column names as loader.py writes them)."""
    rng = random.Random(seed)
    conn = sqlite3.connect(path)
    c = conn.cursor()
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
    c.executemany("INSERT INTO customers VALUES (?, ?)", [(i, f"Customer {i} Ltd") for i in range(1, 21)])
    c.executemany("INSERT INTO products VALUES (?, ?)", [(i, f"Product {i}") for i in range(1, 11)])
    c.executemany("INSERT INTO state_regions VALUES (?, ?, ?)", STATES)
    c.executemany("INSERT INTO budgets VALUES (?, ?)",
                  [(f"Product {i}", float(rng.randint(50_000, 400_000))) for i in range(1, 11)])
    regions = []
    for i in range(1, 31):
        code, state, _ = STATES[i % len(STATES)]
        regions.append((i, f"City {i}", f"County {i}", code, state, "City", 30.0 + i, -100.0 - i,
                        200 + i, 10_000 * i, 4_000 * i, 40_000 + 500 * i, 100 + i, 5 + i, "America/Chicago"))
    c.executemany(f"INSERT INTO regions VALUES ({','.join('?' * 15)})", regions)
    orders = []
    for n in range(1, n_orders + 1):
        qty = rng.randint(1, 20)
        price = round(rng.uniform(10, 500), 2)
        total = round(qty * price, 2)
        cost = round(total * rng.uniform(0.4, 0.9), 2)
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


class ScriptedLLM(GenericFakeChatModel):
    """Returns the given messages in order. bind_tools is a no-op so the LangGraph agent accepts it."""

    def bind_tools(self, tools, **kwargs):
        return self


def make_chain(db: str, *responses):
    """Pipeline on `db` whose LLM replies with `responses` in order."""
    from src.text_to_sql.chain.sql_chain import TextToSQLChain
    from src.text_to_sql.safety.sql_guard import SQLGuard

    messages = [r if isinstance(r, AIMessage) else AIMessage(content=r) for r in responses]
    return TextToSQLChain(db_path=db, llm=ScriptedLLM(messages=iter(messages)),
                          guard=SQLGuard(row_limit=500, enable_audit=True))


def count_customers(db: str) -> int:
    conn = sqlite3.connect(db)
    n = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    conn.close()
    return n


@pytest.fixture(scope="session")
def synthetic_db(tmp_path_factory):
    return build_synthetic_db(str(tmp_path_factory.mktemp("db") / "sales.db"))


@pytest.fixture(autouse=True)
def audit_log(tmp_path, monkeypatch):
    """Every test writes audit records to a temp file, never to logs/."""
    from src.text_to_sql.safety import sql_guard
    path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(sql_guard, "AUDIT_LOG_DIR", str(tmp_path))
    monkeypatch.setattr(sql_guard, "AUDIT_LOG_FILE", str(path))
    return path


# Live fixtures: skipped when their requirements are missing

def has_api_key() -> bool:
    return os.getenv("OPENAI_API_KEY", "").startswith("sk-")


@pytest.fixture(scope="session")
def real_db():
    if not os.path.exists(REAL_DB):
        pytest.skip("needs database/sales.db (python scripts/setup_database.py)")
    return REAL_DB


@pytest.fixture(scope="session")
def live_chain(real_db):
    if not has_api_key():
        pytest.skip("needs OPENAI_API_KEY")
    from src.text_to_sql.chain.sql_chain import TextToSQLChain
    return TextToSQLChain(db_path=real_db)


@pytest.fixture(scope="session")
def live_client(real_db):
    if not has_api_key():
        pytest.skip("needs OPENAI_API_KEY")
    from fastapi.testclient import TestClient
    from src.text_to_sql.api.main import app
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="session")
def report():
    if not os.path.exists(RESULTS_JSON):
        pytest.skip("needs a benchmark report (python scripts/run_benchmark.py)")
    with open(RESULTS_JSON, encoding="utf-8") as f:
        return json.load(f)
