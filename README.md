<div align="center">

# Text-to-SQL Chatbot
Bilingual Arabic–English natural language querying over a SQLite sales database, with complexity-based routing between three SQL generation strategies, a SQL safety layer, and an execution-accuracy benchmark.

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![LangChain](https://img.shields.io/badge/Framework-LangChain-green.svg)](https://www.langchain.com/)
[![LangGraph](https://img.shields.io/badge/Agent-LangGraph-red.svg)](https://www.langchain.com/langgraph)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-teal.svg)](https://fastapi.tiangolo.com/)

</div>

<<<<<<< ours
<!-- Replace with your actual screenshots -->
![Dashboard Screenshot](docs/images/dashboard_english.png)

![Arabic Query Screenshot](docs/images/dashboard_arabic.png)
=======
<img width="1920" height="981" alt="Query interface" src="https://github.com/user-attachments/assets/e6e59bfa-0c77-4caf-a84c-1cfc796af7ad" />

<img width="1920" height="981" alt="Dashboard" src="https://github.com/user-attachments/assets/2b3ecd0e-1cde-4142-94fb-c3861d9afe92" />
>>>>>>> theirs

---

## Overview

Ask a question in **English or Arabic**; the system writes SQL, runs it read-only against a regional sales database (6 tables, ~65k rows) and answers in the same language.

- **Bilingual** — Arabic is detected by character ratio, translated to English for SQL generation, and the answer is translated back
- **Three strategies, one router** — a rule-based router (no LLM call) sends each question to a Simple chain, a Chain-of-Thought chain, or a LangGraph ReAct agent
- **Self-correction** — if generated SQL fails, a fallback chain regenerates it and feeds the SQL error back to the LLM (up to 3 attempts)
- **Safety layer** — prompt-injection checks, SELECT-only policy, row limit, query timeout, read-only database connection, JSONL audit log of every execution
- **Benchmark** — 100 questions (3 complexity tiers, English + Arabic), scored by **execution accuracy**: the generated SQL must return the same rows as a reference query
- **Serving** — FastAPI backend, Streamlit dashboard, Docker Compose

---

## Results

> Numbers below are produced by `scripts/run_benchmark.py` and `scripts/run_ablation.py`.
> Fill this section from `data/eval/benchmark_summary.txt` and `data/eval/ablation.md` after a run — do not edit numbers by hand.

| Metric | Value |
|---|---|
| Execution accuracy (strict, 95% CI) | _run benchmark_ |
| Execution accuracy (lenient — extra columns allowed) | _run benchmark_ |
| Simple / Medium / Complex | _run benchmark_ |
| English (n=85) / Arabic (n=15) | _run benchmark_ |
| Router agreement with tier labels | _run benchmark_ |
| Latency p50 / mean (excl. rate-limit errors) | _run benchmark_ |

**How accuracy is measured.** For every question, the generated SQL and the reference SQL are both executed and their **results** are compared — row order and column names ignored, numbers rounded to 2 decimals. *Strict* requires the same columns; *lenient* also accepts extra columns (e.g. `SELECT *`). Rate-limit / API failures are reported separately as infrastructure errors, not as model mistakes. Every accuracy has a 95% Wilson confidence interval, because 15 Arabic questions or 25 complex questions are small samples.

**Evaluation history.** The first version of the benchmark scored a question as correct when the generated SQL *ran without an error*. An audit of that run found queries that ran but answered a different question (e.g. grouping by state when asked for region) still counted as correct, and agent answers were counted as successful unconditionally. The metric was replaced with the result-set comparison above, and the earlier "97%" figure was withdrawn.

**Ablation.** `python scripts/run_ablation.py` runs five configurations on the same questions — Simple only, CoT only, Agent only, Router without fallback, Router + fallback — and writes the comparison table to `data/eval/ablation.md`.

---

## Architecture

```
Question (English or Arabic)
        │
        ▼
┌───────────────────┐
│ Language detect   │  Arabic-character ratio > 0.2 → Arabic
└────────┬──────────┘
         ▼
┌───────────────────┐
│ Input guard       │  injection regex (EN + AR) on the question ──► blocked
└────────┬──────────┘
         ▼  (Arabic only)
┌───────────────────┐
│ Translate → EN    │  GPT-4o-mini, then input guard again on the translation
└────────┬──────────┘
         ▼
┌───────────────────┐
│ Complexity router │  SIMPLE / MEDIUM / COMPLEX — regex + table keywords, 0 LLM calls
└────────┬──────────┘
    ┌────┴────────────────────┐
    ▼            ▼            ▼
 Simple        CoT          ReAct agent (LangGraph)
 2 LLM calls   2 LLM calls  1 call per step; tools: list_tables,
                            get_schema, run_query, check_query
    └────┬────────────────────┘
         ▼
┌───────────────────┐
│ SQLGuard.execute  │  SELECT-only · write keywords · CROSS JOIN/recursive ·
│                   │  table allow-list · LIMIT ≤ 500 · 10s timeout ·
│                   │  read-only SQLite connection · audit record
└────────┬──────────┘
         ▼
   failed (not blocked, not rate limit)? → fallback: regenerate + self-correct ×3
         ▼
 Answer (LLM) → translate back to Arabic if needed → response
```

No SQL is executed outside `SQLGuard.execute()` — including every query the agent runs.

### Generation strategies

| Strategy | When (router) | How | LLM calls |
|---|---|---|---|
| Simple chain | single table, no aggregation keywords | prompt → SQL | 2 (SQL + answer) |
| Chain-of-Thought | joins, GROUP BY, top-N, averages | reasoning + SQL in one call | 2 (reasoning/SQL + answer) |
| ReAct agent | compare / percentage / ranking / 3+ tables | LangGraph loop over 4 tools, capped at 16 graph steps | 1 per step (typically 3–8) |

<<<<<<< ours
- **Simple Chain** — direct single-step SQL generation for single-table lookups (~3s)
- **Chain-of-Thought** — step-by-step reasoning before SQL generation for joins and aggregations (~6s)
- **ReAct Agent** — LangGraph agent with 4 tools (`list_tables`, `get_schema`, `run_query`, `check_query`) for complex multi-table analysis (~30s)
=======
Arabic questions add 2 calls (translate in and out).
>>>>>>> theirs

### Safety layers

| Layer | What it does | Where |
|---|---|---|
| Input guard | 18 English + 6 Arabic injection regexes; for Arabic, also run on the English translation | `safety/sql_guard.py` |
| Statement allow-list | only a single `SELECT` / `WITH` statement | `check_read_only_statement` |
| Write block-list | DROP, DELETE, UPDATE, INSERT, ALTER, CREATE, ATTACH, PRAGMA, … | `check_sql_write_operations` |
| Resource guard | blocks CROSS JOIN and recursive CTEs; 10s execution timeout | `check_sql_complexity`, `database/executor.py` |
| Row limit | outer query gets `LIMIT ≤ 500` | `enforce_row_limit` |
| Table access control | optional per-guard table allow-list | `validate_table_access` |
| Read-only connection | SQLite opened with `mode=ro` — writes fail in the engine | `database/executor.py` |
| Audit trail | one JSONL record per blocked question and per SQL execution (SQL, strategy, row count, ms, error) | `logs/sql_audit.jsonl` |

The regex layers are a policy filter; the read-only connection is what guarantees the data cannot be modified.

---

## Database

Six tables of regional sales data (column names as created by `scripts/setup_database.py`):

| Table | Rows | Description |
|---|---|---|
| `sales_orders` | 64,104 | One row per order line — quantity, unit price, line total, cost, channel, warehouse |
| `regions` | 994 | US cities — city_name, state, population, median income, … |
| `customers` | 175 | Customer names and index |
| `state_regions` | 48 | State → region mapping |
| `budgets` | 30 | 2017 budget per product |
| `products` | 30 | Product catalog |

<<<<<<< ours
---

## API

<!-- Replace with your actual Swagger screenshot -->
![Swagger UI](docs/images/swagger_ui.png)

=======
The schema context sent to the LLM is built from the live database: column names and types, two sample rows per table, foreign-key relationships, and the distinct values of low-cardinality text columns (e.g. `channel`), so the model filters on real values.
>>>>>>> theirs

---

## Getting Started

**Prerequisites:** Python 3.10+, an OpenAI API key, the six CSV files in `data/csv/`.

```bash
# 1. Environment
git clone https://github.com/pradeepanpp/text-to-sql-chatbot.git
cd text-to-sql-chatbot
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt

# 2. Configure
cp .env.example .env            # then set OPENAI_API_KEY

# 3. Build the SQLite database from the CSVs
python scripts/setup_database.py

# 4. API (terminal 1)
uvicorn src.text_to_sql.api.main:app --port 8000

# 5. Dashboard (terminal 2)
streamlit run src/text_to_sql/dashboard/app.py
```

- API docs: http://localhost:8000/docs
- Dashboard: http://localhost:8501

### Tests

```bash
pytest -q
```

`tests/test_offline.py` needs no API key or data: it runs the real pipeline on a synthetic database with a scripted fake LLM (read-only enforcement, blocking before execution, Arabic injection, CoT SQL extraction, agent bookkeeping, benchmark scoring, API). The live suites (`test_chain.py`, `test_api.py`, `test_database.py`, `test_evaluation.py`) run automatically when `OPENAI_API_KEY`, `database/sales.db` and benchmark results are present.

### Benchmark and ablation

```bash
python scripts/run_benchmark.py                      # full system, 100 questions
python scripts/run_benchmark.py --sample 20          # quick check
python scripts/run_benchmark.py --strategy cot --no-fallback --tag cot_only
python scripts/run_ablation.py --sample 20           # 5 configs → data/eval/ablation.md
```

Add `--delay 1` if you hit OpenAI rate limits.

### Docker

```bash
python scripts/setup_database.py     # the database is mounted, not baked into the image
docker compose up --build
```

---

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/query` | One question (optional `language`: `en` / `ar`) |
| POST | `/query/batch` | Up to 20 questions, processed sequentially |
| GET | `/schema` | Tables, columns, row counts |
| GET | `/health` | Chain, guard and database status |
| GET | `/audit/stats` | Audit-log counts (blocked, suspicious, by language) |
| GET | `/benchmark` | Headline numbers from the latest benchmark run |

---

## Project structure

```
src/text_to_sql/
├── chain/
│   ├── sql_chain.py          orchestrator: language → guard → translate → route → execute → fallback
│   ├── complexity_router.py  rule-based SIMPLE / MEDIUM / COMPLEX
│   ├── simple_chain.py       direct SQL generation
│   ├── cot_chain.py          chain-of-thought SQL generation
│   ├── agent_chain.py        LangGraph ReAct agent + tools
│   └── common.py             QueryResult, guarded execute-and-answer helper
├── safety/sql_guard.py       input guard, SQL policy, audit log, SQLGuard.execute()
├── database/                 loader (CSV → SQLite), schema context, read-only executor
├── language/detector.py      Arabic / English detection
├── evaluation/               100-question dataset, benchmark runner, metrics
├── api/                      FastAPI app, routes, Pydantic schemas
└── dashboard/                Streamlit UI (talks to the API over HTTP)
scripts/                      setup_database, run_benchmark, run_ablation, test_query
tests/                        offline suite + live suites
```

---

## Known limitations

- **Router is keyword based.** It is fast and free but brittle (e.g. "channel" counts as a table, so single-table channel questions go to CoT). Its agreement with the dataset's tier labels is reported by the benchmark.
- **Translation round trip.** Arabic questions cost two extra LLM calls and inherit translation errors; names and numbers are asked to be preserved but this is not verified.
- **Small Arabic sample.** Only 15 of 100 benchmark questions are Arabic, mostly simple; language comparisons have wide confidence intervals.
- **Benchmark is hand-written for this schema.** Questions were not held out from development, so scores are optimistic compared to unseen questions.
- **Agent scoring is a lower bound** when the agent answers with several queries — only its last successful query is compared with the reference.
- **No authentication, caching, conversation memory, or cost tracking** — the API is a single-tenant demo.
- **Regex SQL policy.** A SQL parser (e.g. sqlglot) would be more robust than regex for table access control.

---

## Tech stack

| Layer | Technology |
|---|---|
| LLM | GPT-4o-mini (OpenAI), temperature 0 |
| Orchestration | LangChain (LCEL chains) + LangGraph (`create_react_agent`) |
| Database | SQLite, read-only connections |
| API | FastAPI + Uvicorn |
| Dashboard | Streamlit |
<<<<<<< ours
| Evaluation | Custom 100-question benchmark |
| Container | Docker + Docker Compose |
=======
| Evaluation | Custom 100-question benchmark, execution accuracy with Wilson CIs |
| Container | Docker + Docker Compose |
>>>>>>> theirs
