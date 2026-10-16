"""Command-line entry point: `uv run local-finance-agent <command> ...`"""

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(prog="local-finance-agent")
    commands = parser.add_subparsers(dest="command", required=True)

    inspect_cmd = commands.add_parser("inspect", help="describe a CSV's format without printing values")
    inspect_cmd.add_argument("path", type=Path)

    import_cmd = commands.add_parser("import", help="import a statement into the ledger")
    import_cmd.add_argument("source", choices=["dnb", "kraken"])
    import_cmd.add_argument("path", type=Path)
    import_cmd.add_argument("--account", help="required for DNB, e.g. dnb:brukskonto")
    import_cmd.add_argument("--db", type=Path, default=Path("data/ledger.duckdb"))

    args = parser.parse_args()

    if args.command == "inspect":
        from local_finance_agent.ingest.inspect_file import describe

        describe(args.path)

    elif args.command == "import":
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
        result = db.load(con, transactions, args.path.name)
        print(
            f"{result.source_file}: read {result.rows_read}, "
            f"inserted {result.rows_inserted}, skipped {result.rows_skipped_duplicate} duplicates"
        )