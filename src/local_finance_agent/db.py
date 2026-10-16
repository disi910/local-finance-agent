"""DuckDB ledger: one raw table, written idempotently."""

from pathlib import Path

import duckdb

from local_finance_agent.schema import ImportResult, Transaction

DEFAULT_DB = Path("data/ledger.duckdb")

CREATE_RAW = """
CREATE TABLE IF NOT EXISTS raw_transactions (
    transaction_id VARCHAR PRIMARY KEY,
    source         VARCHAR NOT NULL,
    source_id      VARCHAR,
    source_file    VARCHAR NOT NULL,
    source_row     INTEGER NOT NULL,
    account        VARCHAR NOT NULL,
    booked_on      DATE NOT NULL,
    occurred_at    TIMESTAMPTZ,
    asset          VARCHAR NOT NULL,
    amount         DECIMAL(38, 18) NOT NULL,
    fee            DECIMAL(38, 18) NOT NULL,
    fee_asset      VARCHAR,
    raw_type       VARCHAR NOT NULL,
    group_id       VARCHAR,
    description    VARCHAR NOT NULL,
    imported_at    TIMESTAMPTZ DEFAULT current_timestamp
)
"""

INSERT = """
INSERT INTO raw_transactions (
    transaction_id, source, source_id, source_file, source_row, account,
    booked_on, occurred_at, asset, amount, fee, fee_asset, raw_type,
    group_id, description
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT DO NOTHING
"""


def connect(db_path: Path = DEFAULT_DB) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.execute(CREATE_RAW)
    return con


def load(con: duckdb.DuckDBPyConnection, transactions: list[Transaction], source_file: str) -> ImportResult:
    count = lambda: con.execute("SELECT count(*) FROM raw_transactions").fetchone()[0]
    before = count()
    con.executemany(
        INSERT,
        [
            (
                t.transaction_id, t.source, t.source_id, t.source_file, t.source_row, t.account,
                t.booked_on, t.occurred_at, t.asset, t.amount, t.fee, t.fee_asset, t.raw_type,
                t.group_id, t.description,
            )
            for t in transactions
        ],
    )
    inserted = count() - before
    return ImportResult(
        source_file=source_file,
        rows_read=len(transactions),
        rows_inserted=inserted,
        rows_skipped_duplicate=len(transactions) - inserted,
    )