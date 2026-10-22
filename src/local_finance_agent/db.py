"""DuckDB ledger: raw tables, written idempotently."""

from pathlib import Path

import duckdb

from local_finance_agent.schema import FxRate, ImportResult, Transaction

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

# One row per import run. The file hash catches the same statement being
# imported under a second account, which hash IDs alone cannot detect.
CREATE_IMPORTS = """
CREATE TABLE IF NOT EXISTS imports (
    file_sha256    VARCHAR NOT NULL,
    source_file    VARCHAR NOT NULL,
    source         VARCHAR NOT NULL,
    account        VARCHAR NOT NULL,
    rows_read      INTEGER NOT NULL,
    rows_inserted  INTEGER NOT NULL,
    imported_at    TIMESTAMPTZ DEFAULT current_timestamp
)
"""

CREATE_FX = """
CREATE TABLE IF NOT EXISTS raw_fx_rates (
    currency       VARCHAR NOT NULL,
    rate_date      DATE NOT NULL,
    nok_per_unit   DECIMAL(18, 8) NOT NULL,
    source         VARCHAR NOT NULL,
    fetched_at     TIMESTAMPTZ DEFAULT current_timestamp,
    PRIMARY KEY (currency, rate_date)
)
"""

# Manual answers from `review-transfers`. Holds transaction IDs, so it lives
# only in the ledger, never in git.
CREATE_DECISIONS = """
CREATE TABLE IF NOT EXISTS transfer_decisions (
    out_id         VARCHAR NOT NULL,
    in_id          VARCHAR NOT NULL,
    decision       VARCHAR NOT NULL CHECK (decision IN ('accept', 'reject')),
    decided_at     TIMESTAMPTZ DEFAULT current_timestamp,
    PRIMARY KEY (out_id, in_id)
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
    for statement in (CREATE_RAW, CREATE_IMPORTS, CREATE_FX, CREATE_DECISIONS):
        con.execute(statement)
    return con


def check_same_account(con: duckdb.DuckDBPyConnection, file_sha256: str, account: str, source_file: str) -> None:
    earlier = con.execute(
        "SELECT DISTINCT account FROM imports WHERE file_sha256 = ? AND account <> ?", [file_sha256, account]
    ).fetchall()
    if earlier:
        raise ValueError(
            f"{source_file} was already imported as {', '.join(a for (a,) in earlier)}; "
            f"importing it again as {account} would duplicate every row"
        )


def load(
    con: duckdb.DuckDBPyConnection,
    transactions: list[Transaction],
    source_file: str,
    file_sha256: str | None = None,
) -> ImportResult:
    account = ",".join(sorted({t.account for t in transactions}))
    if file_sha256:
        check_same_account(con, file_sha256, account, source_file)

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

    if file_sha256 and transactions:
        con.execute(
            "INSERT INTO imports (file_sha256, source_file, source, account, rows_read, rows_inserted) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [file_sha256, source_file, transactions[0].source, account, len(transactions), inserted],
        )

    return ImportResult(
        source_file=source_file,
        rows_read=len(transactions),
        rows_inserted=inserted,
        rows_skipped_duplicate=len(transactions) - inserted,
    )


def load_fx(con: duckdb.DuckDBPyConnection, rates: list[FxRate]) -> int:
    """Insert rates not already cached; returns the number of new rows."""
    count = lambda: con.execute("SELECT count(*) FROM raw_fx_rates").fetchone()[0]
    before = count()
    con.executemany(
        "INSERT INTO raw_fx_rates (currency, rate_date, nok_per_unit, source) VALUES (?, ?, ?, ?) "
        "ON CONFLICT DO NOTHING",
        [(r.currency, r.rate_date, r.nok_per_unit, r.source) for r in rates],
    )
    return count() - before
