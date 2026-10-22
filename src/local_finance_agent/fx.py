"""Daily NOK exchange rates from Norges Bank's open data API.

This is one of the few allowed network calls: the request contains only
currency codes and dates, never personal data.
"""

import csv
import io
import urllib.parse
import urllib.request
from datetime import date, timedelta
from decimal import Decimal

from local_finance_agent.schema import FxRate

URL = "https://data.norges-bank.no/api/data/EXR/B.{currencies}.NOK.SP"
SOURCE = "norges-bank"

# Fiat codes Norges Bank quotes that can appear in the ledger. Crypto is priced in M3.
FIAT = {"EUR", "USD", "GBP", "SEK", "DKK", "CHF"}


def parse_norges_bank_csv(text: str) -> list[FxRate]:
    """Semicolon CSV, one row per currency and business day.

    UNIT_MULT is a power of ten: SEK and DKK are quoted per 100 units.
    """
    rows = csv.DictReader(io.StringIO(text.lstrip("﻿")), delimiter=";")
    return [
        FxRate(
            currency=row["BASE_CUR"],
            rate_date=date.fromisoformat(row["TIME_PERIOD"]),
            nok_per_unit=Decimal(row["OBS_VALUE"]).scaleb(-int(row["UNIT_MULT"])),
            source=SOURCE,
        )
        for row in rows
        if row["OBS_VALUE"]
    ]


def fetch_norges_bank(currencies: list[str], start: date, end: date) -> str:
    query = urllib.parse.urlencode(
        {"format": "csv", "startPeriod": start.isoformat(), "endPeriod": end.isoformat(), "locale": "en"}
    )
    url = URL.format(currencies="+".join(sorted(currencies))) + "?" + query
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8")


def ledger_currencies(con) -> list[str]:
    """Foreign fiat currencies that appear in the ledger (EUR.HOLD counts as EUR)."""
    rows = con.execute("SELECT DISTINCT regexp_replace(asset, '\\.HOLD$', '') FROM raw_transactions").fetchall()
    return sorted({asset for (asset,) in rows} & FIAT)


def ledger_start(con) -> date:
    """A week before the first transaction, so weekend bookings have a rate."""
    first = con.execute("SELECT min(booked_on) FROM raw_transactions").fetchone()[0]
    return (first or date.today()) - timedelta(days=7)
