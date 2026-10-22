"""Command-line entry point: `uv run local-finance-agent <command> ...`"""

import argparse
from datetime import date
from pathlib import Path

DEFAULT_DB = Path("data/ledger.duckdb")


def main() -> None:
    parser = argparse.ArgumentParser(prog="local-finance-agent")
    commands = parser.add_subparsers(dest="command", required=True)

    inspect_cmd = commands.add_parser("inspect", help="describe a CSV's format without printing values")
    inspect_cmd.add_argument("path", type=Path)

    import_cmd = commands.add_parser("import", help="import a statement into the ledger")
    import_cmd.add_argument("source", choices=["dnb", "kraken"])
    import_cmd.add_argument("path", type=Path)
    import_cmd.add_argument("--account", help="required for DNB, e.g. dnb:brukskonto")
    import_cmd.add_argument("--db", type=Path, default=DEFAULT_DB)

    fx_cmd = commands.add_parser("fetch-fx", help="download daily NOK exchange rates from Norges Bank")
    fx_cmd.add_argument("--currencies", help="comma-separated, e.g. EUR,USD (default: fiat currencies in the ledger)")
    fx_cmd.add_argument("--start", type=date.fromisoformat, help="YYYY-MM-DD (default: a week before the first transaction)")
    fx_cmd.add_argument("--end", type=date.fromisoformat, help="YYYY-MM-DD (default: today)")
    fx_cmd.add_argument("--db", type=Path, default=DEFAULT_DB)

    transform_cmd = commands.add_parser("transform", help="run the dbt models and tests on the ledger")
    transform_cmd.add_argument("--db", type=Path, default=DEFAULT_DB)

    review_cmd = commands.add_parser("review-transfers", help="answer transfer pairs that could not be matched automatically")
    review_cmd.add_argument("--db", type=Path, default=DEFAULT_DB)

    args = parser.parse_args()

    if args.command == "inspect":
        from local_finance_agent.ingest.inspect_file import describe

        describe(args.path)

    elif args.command == "import":
        import hashlib

        from local_finance_agent import db
        from local_finance_agent.ingest.dnb import parse_dnb
        from local_finance_agent.ingest.kraken import parse_kraken

        if args.source == "dnb":
            if not args.account:
                parser.error("--account is required for DNB, e.g. --account dnb:brukskonto")
            transactions = parse_dnb(args.path, args.account)
        else:
            transactions = parse_kraken(args.path)

        con = db.connect(args.db)
        try:
            result = db.load(con, transactions, args.path.name, hashlib.sha256(args.path.read_bytes()).hexdigest())
        except ValueError as error:
            parser.exit(1, f"error: {error}\n")
        print(
            f"{result.source_file}: read {result.rows_read}, "
            f"inserted {result.rows_inserted}, skipped {result.rows_skipped_duplicate} duplicates"
        )

    elif args.command == "fetch-fx":
        from local_finance_agent import db, fx

        con = db.connect(args.db)
        currencies = (
            [c.strip().upper() for c in args.currencies.split(",") if c.strip()]
            if args.currencies
            else fx.ledger_currencies(con)
        )
        if not currencies:
            print("No foreign fiat currencies in the ledger; nothing to fetch.")
            return
        start = args.start or fx.ledger_start(con)
        end = args.end or date.today()
        rates = fx.parse_norges_bank_csv(fx.fetch_norges_bank(currencies, start, end))
        new = db.load_fx(con, rates)
        print(f"Norges Bank: {len(rates)} rates for {', '.join(currencies)} from {start} to {end}, {new} new")

    elif args.command == "transform":
        from local_finance_agent import db
        from local_finance_agent.transform import run_dbt, summary

        db.connect(args.db).close()  # make sure every raw table exists before dbt reads it
        if not run_dbt(args.db):
            parser.exit(1, "error: dbt build failed; see the output above\n")
        print("\n" + summary(db.connect(args.db)))

    elif args.command == "review-transfers":
        from local_finance_agent import db
        from local_finance_agent.review import review_transfers

        con = db.connect(args.db)
        if not con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'transfer_review'").fetchone()[0]:
            parser.exit(1, "error: run `local-finance-agent transform` first\n")
        review_transfers(con)
