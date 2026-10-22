"""Run the dbt project in transform/ against the ledger."""

import os
from pathlib import Path

import duckdb

PROJECT_DIR = Path("transform")


def run_dbt(
    db_path: Path,
    project_dir: Path = PROJECT_DIR,
    command: str = "build",
    extra_args: list[str] | None = None,
) -> bool:
    """Run dbt in-process, so the test suite's network block also covers dbt.

    The caller must not hold a connection to the ledger: DuckDB allows one writer.
    """
    from dbt.cli.main import dbtRunner

    args = [command, "--project-dir", str(project_dir), "--profiles-dir", str(project_dir), *(extra_args or [])]
    previous = os.environ.get("LEDGER_DB")
    os.environ["LEDGER_DB"] = str(db_path.resolve())
    try:
        result = dbtRunner().invoke(args)
    finally:
        if previous is None:
            os.environ.pop("LEDGER_DB", None)
        else:
            os.environ["LEDGER_DB"] = previous
    return result.success


def summary(con: duckdb.DuckDBPyConnection) -> str:
    matched = con.execute("SELECT count(*) FROM transfer_matches").fetchone()[0]
    review = dict(con.execute("SELECT reason, count(*) FROM transfer_review GROUP BY 1").fetchall())
    months, first, last = con.execute(
        "SELECT count(*), strftime(min(month), '%Y-%m'), strftime(max(month), '%Y-%m') FROM monthly_summary"
    ).fetchone()
    return (
        f"Transfers: {matched} matched; to review: {review.get('ambiguous', 0)} ambiguous pairs, "
        f"{review.get('near_miss', 0)} near misses; "
        f"{review.get('unmatched_exchange_leg', 0)} exchange legs without a counterpart\n"
        f"Monthly summary: {months} months" + (f" ({first} to {last})" if months else "")
    )
