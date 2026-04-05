<div align="center">

# Text-to-SQL Chatbot
Bilingual Arabic–English natural language querying for relational databases with multi-strategy SQL generation, enterprise safety layer, and RAGAS-style evaluation.

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![LangChain](https://img.shields.io/badge/Framework-LangChain-green.svg)](https://www.langchain.com/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-red.svg)](https://www.langchain.com/langgraph)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-teal.svg)](https://fastapi.tiangolo.com/)
[![Evaluation](https://img.shields.io/badge/Evaluation-Custom_Benchmark-orange.svg)](https://github.com/)

</div>

<!-- Replace with your actual screenshots -->
<img width="1920" height="981" alt="Screenshot 2026-04-05 113851" src="https://github.com/user-attachments/assets/e6e59bfa-0c77-4caf-a84c-1cfc796af7ad" />


<img width="1920" height="981" alt="Screenshot 2026-04-05 114221" src="https://github.com/user-attachments/assets/2b3ecd0e-1cde-4142-94fb-c3861d9afe92" />


---

## Overview

This project converts natural language questions in **English or Arabic** into SQL queries against a regional sales database (65,381 rows, 6 tables). It is designed to handle the full spectrum of query complexity, from simple lookups to multi-table analytical joins, while blocking prompt injection and enforcing read-only database access.

**Key features**

- **Bilingual querying** — accepts Arabic or English questions, returns responses in the same language
- **Multi-strategy generation** — routes queries to Simple Chain, Chain-of-Thought, or ReAct Agent based on detected complexity
- **Enterprise safety layer** — prompt injection detection, read-only SQL enforcement, row limits, full audit trail
- **100-question benchmark** — evaluated across 3 complexity tiers and 2 languages with latency profiling
- **FastAPI backend** — REST API with Swagger UI, batch endpoints, and compliance statistics
- **Streamlit dashboard** — interactive UI with schema browser, query history, and audit stats

---

## Results

| Metric | Score |
|---|---|
| Overall execution accuracy | **97%** |
| Simple queries (40 samples) | **100%** |
| Medium queries (35 samples) | **100%** |
| Complex queries (25 samples) | **88%** |
| Arabic accuracy | **100%** |
| English accuracy | **96.5%** |

**Layer ablation** — each layer adds measurable value:

| Configuration | Accuracy | Latency |
|---|---|---|
| Complexity router only | 45.6% | 2ms |
| Router + CoT chain | 98.9% | 36ms |
| **Full system (all strategies)** | **97.0%** | ~5s avg |

---

## Architecture

```
Natural Language Question (English or Arabic)
        │
        ▼
┌───────────────────┐
│  Language Detect  │  Arabic → translate to English (GPT-4o-mini)
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ Complexity Router │  SIMPLE / MEDIUM / COMPLEX  (rule-based, zero cost)
└────────┬──────────┘
         │
    ┌────┴────────────────┐
    ▼          ▼          ▼
 Simple      CoT        ReAct
 Chain       Chain      Agent
 1 LLM call  ~5 calls   4 tools
    └────┬────────────────┘
         │
         ▼
┌───────────────────┐
│    SQL Guard      │  Injection · Write ops · Row limit · Audit log
└────────┬──────────┘
         │
         ▼
  SQLite DB → Format → Translate back (Arabic) → Response
```

**Three generation strategies**

- **Simple Chain** — direct single-step SQL generation for single-table lookups 
- **Chain-of-Thought** — step-by-step reasoning before SQL generation for joins and aggregations 
- **ReAct Agent** — LangGraph agent with 4 tools (`list_tables`, `get_schema`, `run_query`, `check_query`) for complex multi-table analysis 

**Five safety layers**

- Prompt injection detection (16 regex patterns, English + Arabic)
- Read-only SQL enforcement — DROP / DELETE / UPDATE / INSERT all blocked
- Row limit enforcement — 500 rows max, silently applied to every query
- Table access control — configurable per user or role
- Full JSONL audit trail written to `logs/sql_audit.jsonl`

---

## Database

Six tables, 65,381 rows of regional sales data:

| Table | Rows | Description |
|---|---|---|
| `sales_orders` | 64,104 | Main transactions — revenue, quantity, channel |
| `regions` | 994 | US city geographic data |
| `customers` | 175 | Customer names and index |
| `state_regions` | 48 | State → region mapping |
| `budgets` | 30 | 2017 product budget targets |
| `products` | 30 | Product catalog |



## Getting Started

**Prerequisites:** Python 3.10+, OpenAI API key

```bash
# 1. Clone and set up environment
git clone https://github.com/yourusername/text-to-sql-chatbot.git
cd text-to-sql-chatbot
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Mac/Linux
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env and add: OPENAI_API_KEY=sk-...

# 3. Build SQLite database from CSV files
python scripts/setup_database.py

# 4. Start API (Terminal 1)
uvicorn src.text_to_sql.api.main:app --port 8000 --reload

# 5. Start dashboard (Terminal 2)
streamlit run src/text_to_sql/dashboard/app.py
```

- API docs: http://localhost:8000/docs
- Dashboard: http://localhost:8501

### Docker

```bash
docker compose up
```


## Tech Stack

| Layer | Technology |
|---|---|
| LLM | GPT-4o-mini (OpenAI) |
| Framework | LangChain + LangGraph |
| Database | SQLite |
| Embeddings | Not required — SQL generation via LLM |
| API | FastAPI + Uvicorn |
| Dashboard | Streamlit |
| Evaluation | Custom 100-question benchmark |
| Container | Docker + Docker Compose |
