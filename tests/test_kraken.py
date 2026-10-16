from decimal import Decimal
from pathlib import Path

from local_finance_agent import db
from local_finance_agent.ingest.kraken import parse_kraken

FIXTURE = Path(__file__).parent.parent / "data" / "fixtures" / "kraken_ledgers_sample.csv"


def test_parses_settled_rows_and_skips_pending():
    transactions = parse_kraken(FIXTURE)
    assert len(transactions) == 4  # the deposit row without a txid is skipped


def test_trade_legs_share_a_group_and_assets_are_normalized():
    transactions = parse_kraken(FIXTURE)
    trade = [t for t in transactions if t.group_id == "TTEST1-AAAAA-000001"]
    assert {t.asset for t in trade} == {"EUR", "BTC"}
    eur_leg = next(t for t in trade if t.asset == "EUR")
    assert eur_leg.amount == Decimal("-300.0000")
    assert eur_leg.fee == Decimal("1.2000")


def test_amounts_keep_full_precision():
    transactions = parse_kraken(FIXTURE)
    btc_buy = next(t for t in transactions if t.asset == "BTC" and t.amount > 0)
    assert btc_buy.amount == Decimal("0.003125")


def test_importing_twice_inserts_nothing_new(tmp_path):
    con = db.connect(tmp_path / "test.duckdb")
    transactions = parse_kraken(FIXTURE)

    first = db.load(con, transactions, FIXTURE.name)
    second = db.load(con, transactions, FIXTURE.name)

    assert first.rows_inserted == 4
    assert second.rows_inserted == 0
    assert second.rows_skipped_duplicate == 4


def test_wallet_becomes_a_clean_account_name():
    transactions = parse_kraken(FIXTURE)
    assert {t.account for t in transactions} == {"kraken:spot-main"}