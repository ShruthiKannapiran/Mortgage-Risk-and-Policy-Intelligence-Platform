# Mortgage Risk and Policy Intelligence Platform

A small, production-oriented data platform: it ingests messy mortgage application
data, cleans and models it into a star schema, runs SQL analytics on it, serves it
through a dashboard and a REST API, and answers lending-policy questions with a
local, citation-backed RAG assistant.

---

## Overview

A financial institution receives mortgage applications from multiple systems as CSV
and JSON files, with real-world quality issues — missing values, duplicates, invalid
dates, wrong types. This project:

- Ingests and profiles the raw data
- Cleans it and builds a dimensional (star schema) model
- Runs automated data-quality checks and incremental loading
- Provides a Streamlit dashboard
- Answers lending-policy questions with a RAG assistant
- Exposes analytics, pipeline health, and the RAG assistant through an API

---

## Architecture

```

data/raw (CSV, JSON)
      │
      ▼
INGESTION            →  bronze_loan_application     (raw, as-received)
      │
      ▼
TRANSFORMATION       →  silver_loan_application      (cleaned, typed, deduplicated)
      │
      ▼
INCREMENTAL GOLD LOAD → fact_loan_application + 5 dim_* tables  (star schema)
      │
      ├─→ DATA QUALITY CHECKS   (10 pass/fail rules)
      ├─→ SQL ANALYTICS          (10 required business questions)
      ├─→ DASHBOARD              (Streamlit)
      └─→ API                    (FastAPI)

data/policy_documents → chunking → embeddings → FAISS index → /policy/ask or eval script

```

## Tech stack

- **Language:** Python 3.12, pandas
- **Warehouse:** DuckDB — zero-setup, file-based, no server to run
- **Dashboard:** Streamlit — Power BI isn't available on macOS
- **RAG:** sentence-transformers + FAISS — local, no API key, no cost
- **API:** FastAPI + uvicorn
- **Testing:** pytest
- **Containers:** Docker + Docker Compose

---

## Repository structure

```
data/            raw, processed (DuckDB file), rejected, policy_documents, vector_store
src/
  common/        config, db connection, logging
  ingestion/     readers, schema validation, Bronze load
  transformation/ cleansing, derived fields, Silver load
  database/      DDL, dimension upserts, incremental Gold load, audit log
  quality/       profiling (Bronze) + automated checks (Gold)
  rag/           document loading, embeddings, FAISS store, answer generation
  api/           FastAPI app, schemas, queries, dependencies
sql/
  ddl/           dimension, fact, audit table definitions
  analytics/     the 10 required SQL analysis queries
scripts/         generate_data, run_pipeline, run_sql_analytics, build_rag_index,
                 run_rag_evaluation, measure_performance, profile_transformation
dashboard/       Streamlit app
tests/           pytest suite + shared fixtures
reports/         generated profiling / DQ / performance / RAG-eval reports
diagrams/        dimensional model diagram
config/          config.yaml — all thresholds, paths, bands
```

---

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

`.env` holds non-secret local config only (warehouse path, log level, API host/port).
In Azure these would come from Key Vault instead of a plain file.

**Prerequisites:** Python 3.12, ~2 GB free disk, Docker + Compose (optional).

---

## Database setup

No server to install. DuckDB is embedded and file-based. All tables are created automatically on first pipeline run (`sql/ddl/*.sql`, via `src/database/schema_setup.py`, safe to re-run).

---

## Running the pipeline

Generate synthetic source data (once, or to regenerate):

```bash
python scripts/generate_data.py
```

Writes ~250K+ rows across two formats with injected quality issues (nulls,
duplicates, bad dates, negative values, wrong types).

Run the full pipeline — ingest, profile, transform, incremental Gold load, quality checks:

```bash
python scripts/run_pipeline.py
```

Idempotent: re-running against the same files doesn't duplicate Bronze rows, and the
Gold load only touches rows that are actually new or changed.

Run the 10 required SQL analytics queries:

```bash
python scripts/run_sql_analytics.py
```

Check run history directly:

```sql
SELECT * FROM pipeline_execution_log ORDER BY started_at DESC;
```

---

## Dashboard

```bash
streamlit run dashboard/app.py
```

Opens at `http://localhost:8501`. Loads the joined Gold view once (cached 5 min),
filters (date, state, lender, loan type, status, risk category) run in memory.
Includes Executive Summary, Trend, Geographic, and Lender/Product analysis.

---

## RAG assistant

Build the index (once, or when `data/policy_documents/*.md` changes):

```bash
python scripts/build_rag_index.py
```

Ask a question directly:

```python
from src.rag.pipeline import answer_question
result = answer_question("What is the maximum DTI allowed for a conventional loan?")
print(result.answer, result.citations)
```

Run the fixed 10-question evaluation set:

```bash
python scripts/run_rag_evaluation.py
```

Raw results: `reports/rag_evaluation_raw.json`. Human-reviewed findings and score:
`reports/rag_evaluation_results.md` — **8/10**. The system is extractive: it returns
real retrieved text with citations, never generates free-form text, and refuses to
answer when nothing clears the similarity threshold.

---

## API

```bash
uvicorn src.api.main:app --reload
```

Docs: `http://localhost:8000/docs`

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Liveness check |
| GET | `/pipeline/status` | Latest pipeline run(s) from the audit log |
| GET | `/portfolio/summary` | Headline metrics — filters: `state`, `lender`, `loan_type`, `status` |
| GET | `/portfolio/trends` | Monthly trend, same filters |
| GET | `/data-quality/latest` | Most recent DQ report (404 if pipeline hasn't run) |
| POST | `/policy/ask` | Ask the RAG assistant a question |

```bash
curl http://localhost:8000/health

curl "http://localhost:8000/portfolio/summary?state=TX&loan_type=Conventional"

curl -X POST http://localhost:8000/policy/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the maximum LTV for an FHA loan?"}'
```

Filter values are validated server-side — bad state codes, loan types, or statuses
return `422`, not a silent empty result. Unhandled errors return a generic `500`.

---

## Docker

```bash
docker compose up api dashboard
docker compose --profile tools run pipeline   # generate data + run pipeline + build RAG index
```

`./data` and `./reports` are mounted as volumes so output persists on the host.

---

## Testing

```bash
pytest tests/ -q
```

Expected: **33 passed**. Covers schema validation, CSV/JSON reading, ingestion
idempotency, malformed-row quarantine, every cleansing/derive rule, incremental load
classification, and the data-quality checks. Shared fixtures live in
`tests/conftest.py`.

---

## Assumptions

- Synthetic data (HMDA-style), fixed random seed for reproducibility. Injected
  quality-issue rates (~3% nulls, 1.5% duplicates, etc.) were chosen to give the
  quality framework something real to catch, not derived from a real-world statistic.
- All dimensions use Type-1 (overwrite) SCD for this exercise.
- `application_id` is the business key for deduplication; the most recently updated
  version wins.
- DTI/LTV slightly outside configured bounds are clipped and flagged, not rejected.
  Invalid dates and out-of-range income/loan/property values are rejected outright.

---

## Known limitations

- **Type-1 SCD only** — `dim_applicant` overwrites income band / credit score on
  update; historical values aren't retained.
- **Extractive RAG has no cross-passage reasoning** — it can only use what clears the
  similarity threshold, so a question needing two separate policy sections can miss
  one that scores just under the cutoff (see Q5 in the RAG eval). It also can't
  distinguish "no relevant info" from "question too ambiguous" (see Q8).
- **DuckDB↔pandas round-trips are the largest remaining pipeline cost** — profiling
  found ~1.1s of the ~3s transformation stage is data movement, not logic.
- **No real cloud deployment** — Azure equivalents are documented, not implemented.

---

## Future improvements

- Move `dim_applicant` to Type-2 SCD to preserve borrower history.
- Push more transformation logic into DuckDB-native SQL to cut pandas round-trips.
- Add reranking or multi-hop retrieval to RAG for cross-section questions.
- Orchestrate with Azure Data Factory/Fabric instead of a single script.
- Add authentication to the API before any real deployment.