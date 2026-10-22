"""Parser for Kraken's "Ledgers" CSV export."""

import re
from decimal import Decimal
from pathlib import Path

import pandas as pd

from local_finance_agent.schema import Transaction

REQUIRED_COLUMNS = {"txid", "refid", "time", "type", "asset", "amount", "fee"}

# Older Kraken exports use legacy asset codes. Anything not listed is kept as-is.
ASSET_CODES = {
    "XXBT": "BTC", "XBT": "BTC",
    "XETH": "ETH",
    "XXDG": "DOGE", "XDG": "DOGE",
    "XLTC": "LTC",
    "XXRP": "XRP",
    "ZEUR": "EUR",
    "ZUSD": "USD",
    "ZGBP": "GBP",
}


def wallet_slug(wallet: str) -> str:
    """'spot / main' -> 'spot-main'"""
    return re.sub(r"[^a-z0-9]+", "-", wallet.lower()).strip("-") or "spot"


def normalize_asset(code: str) -> str:
    code = code.strip()
    return ASSET_CODES.get(code, code)


def parse_kraken(path: Path) -> list[Transaction]:
    # dtype=str: read everything as text so amounts never pass through float
    df = pd.read_csv(path, dtype=str, keep_default_na=False)

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"{path.name}: not a Kraken ledgers export, missing columns {sorted(missing)}")

    transactions = []
    for row_number, row in enumerate(df.to_dict("records"), start=2):  # row 1 is the header
        if not row["txid"]:
            continue  # pending entries without a ledger ID; the settled entry appears separately

        occurred_at = pd.to_datetime(row["time"], utc=True).to_pydatetime()
        asset = normalize_asset(row["asset"])

        transactions.append(
            Transaction(
                transaction_id=f"kraken:{row['txid']}",
                source="kraken",
                source_id=row["txid"],
                source_file=path.name,
                source_row=row_number,
                account=f"kraken:{wallet_slug(row.get('wallet', ''))}",
                booked_on=occurred_at.date(),
                occurred_at=occurred_at,
                asset=asset,
                amount=Decimal(row["amount"]),
                fee=Decimal(row["fee"] or "0"),
                fee_asset=normalize_asset(row.get("feecurrency") or row["asset"]),  # newer exports name it
                raw_type="/".join(t for t in (row["type"], row.get("subtype", "")) if t),
                group_id=row["refid"] or None,
                description="",
            )
        )
    return transactions