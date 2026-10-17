<div align="center">

# Text-to-SQL Chatbot
Bilingual Arabic–English natural language querying over a SQLite sales database, with complexity-based routing between three SQL generation strategies, a SQL safety layer, and an execution-accuracy benchmark.

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![LangChain](https://img.shields.io/badge/Framework-LangChain-green.svg)](https://www.langchain.com/)
[![LangGraph](https://img.shields.io/badge/Agent-LangGraph-red.svg)](https://www.langchain.com/langgraph)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-teal.svg)](https://fastapi.tiangolo.com/)

</div>

<img width="1920" height="981" alt="Query interface" src="https://github.com/user-attachments/assets/e6e59bfa-0c77-4caf-a84c-1cfc796af7ad" />

<img width="1920" height="981" alt="Dashboard" src="https://github.com/user-attachments/assets/2b3ecd0e-1cde-4142-94fb-c3861d9afe92" />

---

## At a glance

**Problem.** Business users — sales managers, regional leads, finance — need answers from relational data but do not write SQL. BI dashboards only answer the questions someone built in advance, ad-hoc requests queue up with analysts, and in Arabic-speaking teams many users prefer to ask in Arabic. Letting an LLM write SQL against a production database also raises two hard questions: *is the answer correct*, and *can the model be tricked into changing or leaking data*?

**Solution.** A bilingual (English / Arabic) natural-language-to-SQL assistant. A question is routed by complexity to one of three SQL generation strategies, every generated query passes a safety layer and runs on a **read-only** connection, every execution is written to an audit log, and the answer comes back in the user's language together with the SQL that produced it.

**Results** (100-question bilingual benchmark, gpt-4o-mini):

- **80% execution accuracy** (95% CI 71–87%) — 90% simple, 94% medium, 44% complex questions
- A five-way ablation showed **chain-of-thought alone matches the full multi-strategy system** (82% vs 80%); the router's measurable benefit is latency, not accuracy
- The evaluation was audited and rebuilt: an early **"97%" claim was withdrawn** after finding the metric only checked that SQL *ran*; 5 incorrect reference queries were found and corrected against the data

**Stack:** Python · LangChain · LangGraph · OpenAI GPT-4o-mini · SQLite · FastAPI · Streamlit · Docker · pytest

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

Final system (router + self-correction fallback) on the 100-question benchmark, gpt-4o-mini, temperature 0.
Every number below comes from `scripts/run_ablation.py` (`data/eval/ablation.md`, `full_system` config).

| Metric | Value |
|---|---|
| Execution accuracy (strict) | **80%** (95% CI 71–87%) |
| Execution accuracy (lenient — extra columns allowed) | 84% |
| Simple / Medium / Complex | 90% / 94% / 44% (n = 40 / 35 / 25) |
| English / Arabic | 79% (n=85) / 87% (n=15) — confidence intervals overlap; no language difference can be claimed |
| By strategy that ran: Simple / CoT / Agent | 87% / 93% / 37% |
| Router agreement with tier labels | 73% |
| Latency p50 / mean / p95 | 3.2s / 3.9s / 8.1s |
| Infrastructure errors (rate limits, API) | 0 |

**How accuracy is measured.** For every question, the generated SQL and the reference SQL are both executed and their **results** are compared — row order and column names ignored, numbers rounded to 2 decimals. *Strict* requires the same columns; *lenient* also accepts extra columns (e.g. `SELECT *`). Rate-limit / API failures are reported separately as infrastructure errors, not as model mistakes. Every accuracy has a 95% Wilson confidence interval, because 15 Arabic questions or 25 complex questions are small samples.

### Ablation

Same 100 questions, strict execution accuracy:

| Config | Accuracy (95% CI) | Simple | Medium | Complex | p50 latency |
|---|---|---|---|---|---|
| Simple chain only | 72% (63–80%) | 88% | 83% | 32% | 2.3s |
| **CoT only** | **82% (73–88%)** | 92% | 94% | 48% | 3.8s |
| Agent only | 77% (68–84%) | 85% | 94% | 40% | 4.3s |
| Router, no fallback | 79% (70–86%) | 90% | 94% | 40% | 3.1s |
| Router + fallback (full system) | 80% (71–87%) | 90% | 94% | 44% | 3.2s |

What this shows:

- **CoT for every question is as accurate as the full multi-strategy system** (82% vs 80%; the confidence intervals overlap almost completely). The router's measurable benefit is lower latency (p50 3.2s vs 3.8s), not accuracy.
- **Complex questions are the weak spot for every configuration** (32–48%). On the 25 complex questions, CoT reached 64% lenient accuracy versus 52% for the ReAct agent (40% before the agent was given the schema context). Paired McNemar tests on these 25 questions show no statistically significant difference, so the sample is too small to rank them — but there is no evidence that the more expensive agent helps.
- **The largest remaining error source is schema naming, not the model:** the `regions` table stores *cities*, while the sales region (Midwest/Northeast/South/West) lives in `state_regions.region`. "Region" questions fail across all strategies.

### Evaluation history

| Version | Accuracy | What changed |
|---|---|---|
| v1 | "97%" | Metric only checked that the SQL ran without an error; agent answers counted as successful unconditionally. **Withdrawn.** |
| v2 | 77% | Metric replaced with result-set comparison against the reference SQL |
| v3 | 78% | 5 reference queries corrected: `total_unit_cost` is a per-unit cost (verified on all 64,104 rows: `line_total = order_quantity × unit_price` and unit cost < unit price) |
| v4 | 80% | ReAct agent given the same schema context as the chains; agent step-limit counted as a failure |

The v3–v4 changes were made after studying errors on this same benchmark, so these scores are optimistic. A held-out question set is needed to confirm they generalise.

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
| ReAct agent | compare / percentage / ranking / 3+ tables | LangGraph loop over 4 tools with the full schema context, capped at 24 graph steps | 1 per step (typically 3–8) |

Arabic questions add 2 calls (translate in and out).

### Safety layers

| Layer | What it does | Where |
|---|---|---|
| Input guard | 18 English + 6 Arabic injection regexes; for Arabic, also run on the English translation | `safety/sql_guard.py` |
| Statement allow-list | only a single `SELECT` / `WITH` statement | `check_read_only_statement` |
| Write block-list | DROP, DELETE, UPDATE, INSERT, ALTER, CREATE, ATTACH, PRAGMA, … | `check_sql_write_operations` |
| Resource guard | blocks CROSS JOIN and recursive CTEs; 10s execution timeout | `check_sql_complexity`, `database/executor.py` |
| Row limit | outer query gets `LIMIT ≤ 500` | `enforce_row_limit` |
| Table access control | optional per-guard table allow-list (regex based — see Known limitations) | `validate_table_access` |
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

The schema context sent to the LLM is built from the live database: column names and types, two sample rows per table, foreign-key relationships, and the distinct values of low-cardinality text columns (e.g. `channel`), so the model filters on real values.

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

- **The agent is the weakest strategy.** Questions the router labels complex go to the ReAct agent, which scores lowest (37% of the questions it handled). Its one clear strength is recovering from SQL errors.
- **"Region" is ambiguous in the schema** (`regions` = cities; region lives in `state_regions`) and causes failures in every strategy.
- **Router is keyword based.** It is fast and free but brittle (e.g. "channel" counts as a table, so single-table channel questions go to CoT). Its agreement with the dataset's tier labels is reported by the benchmark.
- **Translation round trip.** Arabic questions cost two extra LLM calls and inherit translation errors; names and numbers are asked to be preserved but this is not verified.
- **Small Arabic sample.** Only 15 of 100 benchmark questions are Arabic, mostly simple; language comparisons have wide confidence intervals.
- **Benchmark is hand-written for this schema.** Questions were not held out from development, so scores are optimistic compared to unseen questions.
- **Agent scoring is a lower bound** when the agent answers with several queries — only its last successful query is compared with the reference (several "wrong" agent answers contain the correct numbers in the text).
- **No authentication, caching, conversation memory, or cost tracking** — the API is a single-tenant demo.
- **Regex SQL policy.** The table allow-list can be bypassed with comma joins (`FROM a, b`) or quoted table names, and a `;` inside a string literal is wrongly blocked. A SQL parser (e.g. sqlglot) is the proper fix. The read-only connection still prevents any data modification.

### Next steps

1. Route complex questions to CoT and use the ReAct agent only as the fallback when CoT's SQL fails.
2. Add the region / city distinction to the data dictionary.
3. Ask the agent to finish with one query that returns the full answer, so every answer is traceable to a single audited SQL statement.
4. Build a held-out question set (balanced English / Arabic) written after development, and report accuracy on it.

---

## Tech stack

| Layer | Technology |
|---|---|
| LLM | GPT-4o-mini (OpenAI), temperature 0 |
| Orchestration | LangChain (LCEL chains) + LangGraph (`create_react_agent`) |
| Database | SQLite, read-only connections |
| API | FastAPI + Uvicorn |
| Dashboard | Streamlit |
| Evaluation | Custom 100-question benchmark, execution accuracy with Wilson CIs |
| Container | Docker + Docker Compose |