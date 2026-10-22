from datetime import date
from decimal import Decimal

import pytest

from fixtures import DNB_SAMPLE, write_dnb_xlsx
from local_finance_agent import db
from local_finance_agent.ingest.dnb import parse_dnb

ACCOUNT = "dnb:brukskonto"


@pytest.fixture
def sample(tmp_path):
    return write_dnb_xlsx(tmp_path / "dnb_sample.xlsx", DNB_SAMPLE)


def test_skips_blank_and_summary_rows(sample):
    assert len(parse_dnb(sample, ACCOUNT)) == 6


def test_excel_dates_and_text_dates_both_parse(sample):
    transactions = parse_dnb(sample, ACCOUNT)
    assert [t.booked_on for t in transactions[:2]] == [date(2026, 1, 2), date(2026, 1, 3)]


def test_amounts_are_signed_decimals_in_ore(sample):
    amounts = [t.amount for t in parse_dnb(sample, ACCOUNT)]
    assert amounts == [
        Decimal("30000.00"),
        Decimal("-9000.00"),  # comma-decimal text, outflow written as a positive number
        Decimal("-412.30"),  # outflow written as a negative number
        Decimal("-49.00"),
        Decimal("-49.00"),
        Decimal("0.30"),  # 0.1 + 0.2 in Excel, without float noise
    ]
    assert all(isinstance(a, Decimal) for a in amounts)


def test_source_row_is_the_excel_row_number(sample):
    transactions = parse_dnb(sample, ACCOUNT)
    assert transactions[0].source_row == 2  # row 1 is the header
    assert transactions[-1].source_row == 7


def test_identical_rows_get_distinct_ids(sample):
    coffees = [t for t in parse_dnb(sample, ACCOUNT) if t.description == "KAFFEBAR OSLO"]
    assert len({t.transaction_id for t in coffees}) == 2


def test_missing_column_is_reported(tmp_path):
    path = write_dnb_xlsx(tmp_path / "wrong.xlsx", [], header=["Dato", "Tekst", "Beløp"])
    with pytest.raises(ValueError, match="missing columns"):
        parse_dnb(path, ACCOUNT)


def test_importing_twice_inserts_nothing_new(sample, tmp_path):
    con = db.connect(tmp_path / "test.duckdb")
    transactions = parse_dnb(sample, ACCOUNT)

    first = db.load(con, transactions, sample.name, file_sha256="abc")
    second = db.load(con, transactions, sample.name, file_sha256="abc")

    assert first.rows_inserted == 6
    assert second.rows_inserted == 0
    assert second.rows_skipped_duplicate == 6


def test_same_file_cannot_be_imported_under_a_second_account(sample, tmp_path):
    con = db.connect(tmp_path / "test.duckdb")
    db.load(con, parse_dnb(sample, ACCOUNT), sample.name, file_sha256="abc")

    with pytest.raises(ValueError, match="already imported as dnb:brukskonto"):
        db.load(con, parse_dnb(sample, "dnb:bsu"), sample.name, file_sha256="abc")
    assert con.execute("SELECT count(*) FROM raw_transactions WHERE account = 'dnb:bsu'").fetchone()[0] == 0
