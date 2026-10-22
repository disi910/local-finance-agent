"""End to end: synthetic statements -> ledger -> dbt build, with networking blocked.

January 2026 on paper:
  income       30 000.00  salary
  consumption  10 210.30  rent 9 000, groceries 412.30, two coffees 49, and the
                         unanswered near miss 700
  transfers     brukskonto -> BSU 2 000 (same day, unique match)
                brukskonto -> Kraken 5 850 NOK = 500 EUR two days later (currency-adjusted)
                brukskonto -1 000 with two possible BSU credits (ambiguous, review)
                brukskonto -700 on 25 Jan, BSU +700 on 2 Feb (too far apart: near miss)
  February      Kraken BTC withdrawal to an account that is not imported
"""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from fixtures import write_dnb_xlsx
from local_finance_agent import db
from local_finance_agent.ingest.dnb import parse_dnb
from local_finance_agent.ingest.kraken import parse_kraken
from local_finance_agent.review import review_transfers
from local_finance_agent.schema import FxRate
from local_finance_agent.transform import run_dbt

ROOT = Path(__file__).parent.parent
PROJECT = ROOT / "transform"
KRAKEN = ROOT / "data" / "fixtures" / "kraken_ledgers_sample.csv"

BRUKSKONTO = [
    (datetime(2026, 1, 2), "LØNN ACME AS", None, None, 30000.0),
    (datetime(2026, 1, 3), "Husleie januar", None, 9000.0, None),
    (datetime(2026, 1, 3), "Nettbank til BSU", None, 2000.0, None),
    (datetime(2026, 1, 3), "VISA KORTKJØP KRYPTOBØRS", None, 5850.0, None),
    (datetime(2026, 1, 10), "KIWI 123 OSLO", None, 412.3, None),
    (datetime(2026, 1, 12), "KAFFEBAR OSLO", None, 49.0, None),
    (datetime(2026, 1, 12), "KAFFEBAR OSLO", None, 49.0, None),
    (datetime(2026, 1, 20), "Overføring", None, 1000.0, None),
    (datetime(2026, 1, 25), "Sparing", None, 700.0, None),
]
BSU = [
    (datetime(2026, 1, 3), "Fra brukskonto", None, None, 2000.0),
    (datetime(2026, 1, 20), "Fra brukskonto", None, None, 1000.0),
    (datetime(2026, 1, 22), "Innskudd", None, None, 1000.0),
    (datetime(2026, 2, 2), "Fra brukskonto", None, None, 700.0),
]
EUR_NOK = {date(2026, 1, 2): "11.60", date(2026, 1, 5): "11.62", date(2026, 1, 7): "11.65", date(2026, 1, 30): "11.70"}


def build_ledger(tmp_path: Path) -> Path:
    path = tmp_path / "ledger.duckdb"
    con = db.connect(path)
    for name, account, rows in (("bk.xlsx", "dnb:brukskonto", BRUKSKONTO), ("bsu.xlsx", "dnb:bsu", BSU)):
        db.load(con, parse_dnb(write_dnb_xlsx(tmp_path / name, rows), account), name)
    db.load(con, parse_kraken(KRAKEN), KRAKEN.name)
    db.load_fx(con, [FxRate(currency="EUR", rate_date=d, nok_per_unit=Decimal(r)) for d, r in EUR_NOK.items()])
    con.close()
    return path


def transform(tmp_path: Path, ledger: Path) -> None:
    dbt_args = ["--target-path", str(tmp_path / "target"), "--log-path", str(tmp_path / "logs")]
    assert run_dbt(ledger, PROJECT, extra_args=dbt_args), "dbt build failed (a model or a dbt test)"


def query(ledger: Path, sql: str) -> list[tuple]:
    con = db.connect(ledger)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


@pytest.fixture(scope="module")
def ledger(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("transform")
    path = build_ledger(tmp_path)
    transform(tmp_path, path)
    return path


def matched_pairs(ledger: Path) -> set[tuple]:
    return set(
        query(
            ledger,
            """
            SELECT o.account, o.amount::DOUBLE, i.account, i.asset, i.amount::DOUBLE, m.match_method
            FROM transfer_matches m
            JOIN fct_transactions o ON o.transaction_id = m.out_id
            JOIN fct_transactions i ON i.transaction_id = m.in_id
            """,
        )
    )


def test_unique_and_currency_adjusted_transfers_are_matched(ledger):
    assert matched_pairs(ledger) == {
        ("dnb:brukskonto", -2000.0, "dnb:bsu", "NOK", 2000.0, "unique"),
        ("dnb:brukskonto", -5850.0, "kraken:spot-main", "EUR", 500.0, "unique"),
    }


def test_ambiguous_and_unmatched_legs_go_to_review(ledger):
    rows = query(ledger, "SELECT reason, out_amount::DOUBLE, in_booked_on FROM transfer_review ORDER BY ALL")
    assert rows == [
        ("ambiguous", -1000.0, date(2026, 1, 20)),
        ("ambiguous", -1000.0, date(2026, 1, 22)),
        ("near_miss", -700.0, date(2026, 2, 2)),
        ("unmatched_exchange_leg", -0.001, None),
    ]


def test_kinds(ledger):
    kinds = dict(query(ledger, "SELECT kind, count(*) FROM fct_transactions GROUP BY 1"))
    # transfers: 2 matched pairs, 3 ambiguous legs, 1 unmatched withdrawal.
    # Near-miss legs keep their normal kind until a pair is accepted.
    assert kinds == {"income": 2, "consumption": 5, "transfer": 8, "trade": 2}


def test_monthly_summary_matches_hand_calculation(ledger):
    assert january(ledger) == [(Decimal("30000.00"), Decimal("10210.30"), Decimal("7850.00"), 0.6597, 3)]


def review_and_rebuild(tmp_path: Path, answers: list[str]) -> Path:
    path = build_ledger(tmp_path)
    transform(tmp_path, path)
    con = db.connect(path)
    replies = iter(answers)
    review_transfers(con, ask=lambda _: next(replies), show=lambda _: None)
    con.close()
    transform(tmp_path, path)
    return path


def january(ledger: Path) -> list[tuple]:
    return query(
        ledger,
        "SELECT income_nok, consumption_nok, transfers_out_nok, savings_rate, open_review_legs "
        "FROM monthly_summary WHERE month = DATE '2026-01-01'",
    )


def test_accepted_pairs_become_manual_matches(tmp_path):
    # 1: the same-day BSU credit for the ambiguous -1 000; 1: the near miss
    path = review_and_rebuild(tmp_path, ["1", "1"])

    pairs = matched_pairs(path)
    assert ("dnb:brukskonto", -1000.0, "dnb:bsu", "NOK", 1000.0, "manual") in pairs
    assert ("dnb:brukskonto", -700.0, "dnb:bsu", "NOK", 700.0, "manual") in pairs
    assert query(path, "SELECT reason FROM transfer_review") == [("unmatched_exchange_leg",)]
    # The other +1 000 BSU credit has no counterpart left, so it is income
    assert january(path) == [(Decimal("31000.00"), Decimal("9510.30"), Decimal("9550.00"), 0.6932, 0)]


def test_rejected_pairs_are_income_and_consumption(tmp_path):
    path = review_and_rebuild(tmp_path, ["n", "s"])  # not a transfer; skip the near miss

    reasons = query(path, "SELECT reason, count(*) FROM transfer_review GROUP BY 1 ORDER BY 1")
    assert reasons == [("near_miss", 1), ("unmatched_exchange_leg", 1)]
    # -1 000 is now consumption and both +1 000 BSU credits are income
    assert january(path) == [(Decimal("32000.00"), Decimal("11210.30"), Decimal("7850.00"), 0.6497, 0)]
