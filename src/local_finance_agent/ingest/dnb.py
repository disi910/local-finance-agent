"""Parser for DNB account transaction exports (Excel)."""

import math
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd

from local_finance_agent.ingest.ids import IdFactory
from local_finance_agent.schema import Transaction

# --- Format settings: copy these from `inspect` on your own file ----------
SHEET = 0                  # first sheet; or the sheet's name
HEADER_ROW = 0             # 0-based row of the column names ("Header row" in inspect)
DATE_FORMAT = "%d.%m.%Y"   # only used if dates are stored as text, not Excel dates
COL_DATE = "Dato"
COL_TEXT = "Forklaring"
COL_OUT = "Ut fra konto"   # money leaving the account
COL_IN = "Inn på konto"    # money entering the account
# ---------------------------------------------------------------------------

ORE = Decimal("0.01")


def is_empty(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value)) or str(value).strip() == ""


def to_date(value) -> date:
    if isinstance(value, datetime):  # Excel date cell (pandas Timestamp is a datetime)
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value).strip(), DATE_FORMAT).date()  # date stored as text


def to_nok(value) -> Decimal:
    """Excel number, or text like '1 234,50', -> Decimal rounded to øre."""
    if is_empty(value):
        return Decimal("0")
    if isinstance(value, (int, float)):
        # Excel stores numbers as floats; str() then rounding to øre removes float noise
        return Decimal(str(value)).quantize(ORE)
    text = str(value).replace("\u00a0", "").replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    return Decimal(text).quantize(ORE)


def parse_dnb(path: Path, account: str) -> list[Transaction]:
    # dtype=object keeps each cell's own type: datetime, float or str
    df = pd.read_excel(path, sheet_name=SHEET, header=HEADER_ROW, dtype=object)
    df.columns = [str(c).strip() for c in df.columns]

    missing = {COL_DATE, COL_TEXT, COL_OUT, COL_IN} - set(df.columns)
    if missing:
        raise ValueError(f"{path.name}: missing columns {sorted(missing)}; found {list(df.columns)}")

    ids = IdFactory("dnb")
    transactions = []
    for offset, row in enumerate(df.to_dict("records")):
        if is_empty(row[COL_DATE]):
            continue  # blank or summary rows

        booked_on = to_date(row[COL_DATE])
        # abs() on both: works whether DNB writes outflows as 500 or -500
        amount = abs(to_nok(row[COL_IN])) - abs(to_nok(row[COL_OUT]))
        description = "" if is_empty(row[COL_TEXT]) else str(row[COL_TEXT]).strip()

        transactions.append(
            Transaction(
                transaction_id=ids.make(account, booked_on, amount, "NOK", description),
                source="dnb",
                source_file=path.name,
                source_row=HEADER_ROW + 2 + offset,  # 1-based row number as shown in Excel
                account=account,
                booked_on=booked_on,
                asset="NOK",
                amount=amount,
                raw_type="",
                description=description,
            )
        )
    return transactions