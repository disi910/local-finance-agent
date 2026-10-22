from datetime import date
from decimal import Decimal

from local_finance_agent import db
from local_finance_agent.fx import parse_norges_bank_csv

HEADER = (
    "FREQ;Frequency;BASE_CUR;Base Currency;QUOTE_CUR;Quote Currency;TENOR;Tenor;DECIMALS;CALCULATED;"
    "UNIT_MULT;Unit Multiplier;COLLECTION;Collection Indicator;TIME_PERIOD;OBS_VALUE"
)
CSV = "﻿" + "\n".join(
    [
        HEADER,
        "B;Business;EUR;Euro;NOK;Norwegian krone;SP;Spot;4;false;0;Units;C;ECB concertation time 14:15 CET;2026-01-02;11.7985",
        "B;Business;EUR;Euro;NOK;Norwegian krone;SP;Spot;4;false;0;Units;C;ECB concertation time 14:15 CET;2026-01-05;11.7795",
        "B;Business;SEK;Swedish krona;NOK;Norwegian krone;SP;Spot;2;false;2;Hundreds;C;ECB concertation time 14:15 CET;2026-01-02;109.16",
    ]
)


def test_parses_rates_as_decimals():
    rates = parse_norges_bank_csv(CSV)
    assert len(rates) == 3
    assert rates[0].currency == "EUR"
    assert rates[0].rate_date == date(2026, 1, 2)
    assert rates[0].nok_per_unit == Decimal("11.7985")


def test_unit_multiplier_gives_nok_per_single_unit():
    sek = next(r for r in parse_norges_bank_csv(CSV) if r.currency == "SEK")
    assert sek.nok_per_unit == Decimal("1.0916")


def test_loading_twice_inserts_nothing_new(tmp_path):
    con = db.connect(tmp_path / "test.duckdb")
    rates = parse_norges_bank_csv(CSV)
    assert db.load_fx(con, rates) == 3
    assert db.load_fx(con, rates) == 0
