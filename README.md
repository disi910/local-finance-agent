# Local Finance Agent

*A private, local-first personal finance agent. Your financial data never leaves your machine.*

> **Status:** early development. See [PLAN.md](PLAN.md) for the roadmap.

## About

This project imports statements from **DNB**, **Firi** and **Kraken** into a single ledger, visualizes spending, savings and net worth, and answers questions in plain language through a small language model running locally on a laptop.

It is built around one principle: **code computes, the model explains.** Every number comes from SQL or Python. The language model only decides which tool to call and phrases the result, so it cannot invent a balance.

## Why

Financial data is some of the most sensitive personal data there is, yet most AI assistants require sending it to a third party. The project explores how much real utility a *small* local model (3–4B parameters, 4-bit quantized, on a MacBook with 8 GB of memory) can deliver when the system around it is designed to compensate for its limits, and it measures the result instead of assuming it.

## Features (planned)

- Import CSV exports from DNB, Firi and Kraken, with duplicate-safe re-imports
- Automatic detection of transfers between your own accounts
- Spending categorization (rules → embeddings → LLM fallback) that learns from your corrections
- Net worth and crypto holdings valued in NOK, with realized and unrealized gains
- Dashboard: spending by category, savings rate, net worth, holdings
- Chat interface backed by a small set of deterministic tools
- Savings scenarios using Monte Carlo simulation over historical index returns

## Non-goals

- **Investment recommendations.** The agent never tells you what to buy or sell.
- **Projections for crypto assets.** Their history is too short and volatile for meaningful simulation.
- **Tax reporting.** Gains are displayed for insight, not for filing.
- **Bank or exchange API connections.** CSV import only, so no credentials are ever stored.
- Multi-user support or cloud deployment.

## Privacy model

- All personal data is stored and processed locally.
- The only network access is fetching **public** price and currency data. Those requests contain tickers and dates, never personal data.
- This is enforced in the test suite: tests run with networking blocked except for the allowed price source.
- Real statements live in `data/raw/`, which is git-ignored. The repository contains only synthetic fixtures.

## Architecture

```
DNB / Firi / Kraken CSV exports
              │
      ingest (pandas)  ──►  DuckDB ledger
                               │
             dbt models: staging → unified → categorized → marts
                               │
        ┌──────────────────────┼──────────────────────┐
   FastAPI tools         React dashboard         eval suite
        │
   agent loop  ◄──►  local LLM (Ollama)
```

## Evaluation

Results will be published here as milestones are completed.

| Metric | Result |
|---|---|
| Categorization macro-F1 (rules / embeddings / LLM) | — |
| Answer accuracy on a 100-question benchmark | — |
| Tool-selection accuracy | — |
| Tokens/s and peak memory on M2, 8 GB | — |

## Tech stack

Python · FastAPI · Pydantic · pandas · DuckDB · dbt (dbt-duckdb) · Ollama · sentence-transformers · NumPy · React · Recharts · pytest · pytest-socket · Docker Compose · GitHub Actions

## Getting started

Setup instructions will be added when the first milestone is complete.

## Disclaimer

This is a personal project. Nothing it produces is financial or tax advice.