from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

Source = Literal["dnb", "firi", "kraken"]

print(Source)

class Transaction(BaseModel):
    # Same row must get the same ID on every import
    transaction_id: str
    source: Source
    source_id: str | None = None

    # Lineage: lets you trace any number back to the exact file and row
    source_file: str
    source_row: int

    # Where and when
    account: str                   # e.g. "dnb:brukskonto", "kraken:spot-main"
    booked_on: date
    occurred_at: datetime | None = None  # exchanges give a timestamp, banks only a date

    # What moved
    asset: str                     # NOK, EUR, BTC: always the normalized code
    amount: Decimal                # signed: negative = left the account
    fee: Decimal = Decimal("0")    # kept separate; balance changes by amount - fee
    fee_asset: str | None = None

    # Context
    raw_type: str                  # the source's own label, unchanged; dbt interprets it later
    group_id: str | None = None    # links rows of one event, e.g. both legs of a trade
    description: str = ""

    model_config = {"frozen": True} # Immutable once created

class ImportResult(BaseModel):
    source_file: str
    rows_read: int
    rows_inserted: int
    rows_skipped_duplicate: int    # > 0 on a re-import is correct, not an error
    errors: list[str] = Field(default_factory=list)

