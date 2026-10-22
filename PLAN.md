# Local Finance Agent — Project Plan

## Guiding principles

1. **Code computes, the model explains.** No number in an answer may come from the LLM itself.
2. **Private by default.** Personal data never leaves the machine and never enters git.
3. **Measure, don't claim.** Every component that involves ML gets an evaluation with published numbers.
4. **Finish before expanding.** Each milestone ends in something that works and is committed.

## Constraints

- **Hardware:** M2 Mac, 8 GB unified memory, no discrete GPU. Realistic model size is 3–4B parameters at 4-bit quantization.
- **Small-model design rules:** about five tools, strict schemas, output validation with retry, narrow functions instead of free-form SQL.
- **Network boundary:** only public price and FX data may be fetched. Everything else is offline.
- **Docker on macOS cannot use the Mac's GPU (Metal).** Run Ollama natively; containerize the rest.

## Definitions

- **Base currency:** NOK. All values are converted on the relevant date.
- **Transfer:** money moving between two of my own accounts (for example DNB → Firi). Neither income nor spending.
- **Consumption:** money leaving my accounts for goods and services. Buying assets is *not* consumption.
- **Savings rate:** (income − consumption) / income, per month.
- **Holding:** quantity of an asset in an account on a given date.

---

## M0 — Setup

- [x] Repository, folder structure and `.gitignore`; verify `data/raw/` is ignored
- [x] Python environment with uv and core dependencies
- [x] Ollama installed; a 3–4B instruct model with tool calling pulled and responding
- [x] README and PLAN committed; private GitHub repository created

**Done when:** a fresh clone followed by `uv sync` works, and no personal data exists in the git history.

## M1 — Ingestion

- [ ] Export one statement from each source; document column formats in `docs/sources.md` (headers and types only, no real values) (DNB and Kraken documented; Firi missing)
- [x] Define the normalized transaction schema with Pydantic (date, amount, currency, account, source, description, source ID)
- [x] DNB parser (Excel export; Norwegian date format, comma decimals)
- [ ] Firi parser
- [x] Kraken parser (ledger export; asset codes such as `XXBT`, `ZEUR`)
- [x] Stable transaction IDs: use the source's own IDs where available, otherwise a hash plus an occurrence index for identical same-day transactions
- [x] Idempotent load into a raw DuckDB table
- [ ] Synthetic fixtures for each source, with parser tests (Kraken and DNB done; Firi missing)

**Done when:** importing the same file twice gives the same row count, and all fixtures parse.

## M2 — Transformation and transfer matching (dbt)

- [x] Initialize a dbt project with dbt-duckdb in `transform/`
- [x] Staging model per source → one unified transactions model
- [x] Transfer matching: opposite amounts across my own accounts within a few days (currency-adjusted); ambiguous cases go to a review list
- [x] dbt tests: unique IDs, not-null fields, accepted values
- [x] Monthly summary models (income, consumption, transfers, savings rate)

**Done when:** one full month, checked by hand, has every transfer correctly matched.

## M3 — Valuation

- [ ] Choose a public source for crypto prices and NOK exchange rates; cache everything locally (NOK exchange rates done: Norges Bank; crypto prices open)
- [ ] Daily holdings per asset and account
- [ ] Value holdings in NOK by date; net worth over time
- [ ] Cost basis and realized/unrealized gains (FIFO)
- [ ] Verify the Norwegian cost-basis rules with Skatteetaten (for display accuracy only, not tax reporting)

**Done when:** holdings match the balances the exchanges report, and gains match a few hand-calculated cases.

## M4 — Categorization

- [ ] Category taxonomy of about 15 categories
- [ ] Label about 500 real transactions as a private evaluation set (never committed)
- [ ] Build a synthetic evaluation set that can be committed, for reproducibility
- [ ] Baseline: keyword rules
- [ ] Embedding similarity (sentence-transformers) against labeled examples
- [ ] LLM fallback for low-confidence cases
- [ ] Corrections from the UI become new labeled examples
- [ ] Report macro-F1 and a confusion matrix for each approach

**Done when:** the categorization results table in the README is filled in.

## M5 — Agent

- [ ] Tools (about five): `query_spending`, `get_balance`, `get_holdings`, `project_savings`, `check_budget`
- [ ] Pydantic schemas for every tool
- [ ] Hand-written agent loop (no framework): call model → validate tool call → run tool → model phrases the result
- [ ] Validation and retry on invalid tool calls
- [ ] Grounding check: every number in an answer must appear in a tool result
- [ ] Benchmark of 100 questions with answers computed by SQL
- [ ] Compare 2–3 models or quantization levels that fit in 8 GB: answer accuracy, tool accuracy, tokens/s, peak memory

**Done when:** benchmark results and the model comparison are in the README.

## M6 — Dashboard

- [ ] FastAPI endpoints for summaries, holdings and chat
- [ ] React + Recharts: spending by category per month, savings rate, net worth over time, holdings
- [ ] Chat panel connected to the agent
- [ ] Category correction directly from the transaction list

**Done when:** the full flow (import → view → ask → correct) works in the browser.

## M7 — Savings planner

- [ ] Store historical returns for a broad index locally
- [ ] Monte Carlo simulation of monthly savings scenarios
- [ ] Show percentile bands with visible assumptions, never a single number
- [ ] No projections for crypto

**Done when:** the agent can answer "what if I save X per month for Y years?" with a range and its assumptions.

## M8 — Quality and release

- [ ] Privacy test: pytest-socket blocks all network access except the allowed price source
- [ ] GitHub Actions running tests and evaluations on synthetic data
- [ ] Docker Compose for everything except Ollama
- [ ] README: results, screenshots, setup instructions, a short write-up of failure cases
- [ ] Review the full git history for personal data, then make the repository public

**Done when:** a stranger can clone the repository and run it on synthetic data with one command.

## Stretch goals

- [ ] LoRA fine-tuning of a ~1B model with MLX for categorization, compared against M4 results
- [ ] Subscription and recurring-payment detection
- [ ] Budget alerts

---

## Open questions

- Which public source for crypto prices? (NOK exchange rates: Norges Bank, decided 2026-10-21)
- Exact export format from Firi (Kraken documented in `docs/sources.md`)
- Final category taxonomy
- Which 3–4B models to compare

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-10-07 | All personal data processed locally | Core purpose of the project |
| 2026-10-07 | The model never computes numbers | LLMs invent numbers; tools are deterministic and testable |
| 2026-10-07 | CSV import only, no APIs | No stored credentials |
| 2026-10-07 | DuckDB instead of Postgres | Single file, built for analytical queries, reads CSV directly |
| 2026-10-07 | No agent framework | Keep the loop transparent and explainable |
| 2026-10-07 | No investment recommendations or crypto projections | Regulated area; small model; unreliable for volatile assets |
| 2026-10-16 | DNB parser reads Excel exports, with format settings as constants at the top of `dnb.py` | The export is an `.xlsx` file; `inspect` shows the layout without printing values |
| 2026-10-16 | Amounts stored as `Decimal`, never float; Kraken CSV read as text | Avoid rounding noise in money values |
| 2026-10-16 | Transaction ID is the source's own ID where one exists (Kraken), otherwise a SHA-256 hash with an occurrence number | Re-imports skip duplicates while identical same-day rows stay distinct |
| 2026-10-16 | Source labels kept unchanged in `raw_type`; one raw DuckDB table loaded with `ON CONFLICT DO NOTHING` | Interpretation is left to dbt; idempotent imports |
| 2026-10-21 | Importing the same file (by SHA-256) under a second account is refused | A statement imported as two accounts doubled every DNB row, and hash IDs include the account, so they could not catch it |
| 2026-10-21 | NOK exchange rates from Norges Bank's open API, cached in `raw_fx_rates`; fiat legs valued at the latest rate on or before the booking date (at most 7 days old) | Official, free, no key; requests contain only currency codes and dates |
| 2026-10-21 | Transfers are auto-matched only when a pair is the only strict candidate (±5 days, 3% NOK gap, exact amount for the same asset) for both legs; looser pairs (±10 days, 10%) are offered as near misses; answers are stored in the ledger's `transfer_decisions` table | Wrong matches distort income and consumption silently; transaction IDs must never enter git |
| 2026-10-21 | Legs of ambiguous transfer pairs are left out of income and consumption until reviewed; `monthly_summary.open_review_legs` marks provisional months | A guessed classification would make the savings rate look final when it is not |
| 2026-10-21 | Kraken wallet `unknown` is read as the spot wallet, `.HOLD` assets as their currency, and spend + receive as a trade | Seen in the real export: trade groups span both wallets, and "Buy crypto" uses spend/receive |
| 2026-10-21 | dbt runs in-process through `dbtRunner` | The test suite's network block then covers dbt too |
