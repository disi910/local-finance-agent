"""`inspect` must describe a file's format without leaking any of its values."""

from pathlib import Path

from fixtures import DNB_HEADER, DNB_SAMPLE, write_dnb_xlsx
from local_finance_agent.ingest.inspect_file import describe

KRAKEN_FIXTURE = Path(__file__).parent.parent / "data" / "fixtures" / "kraken_ledgers_sample.csv"


def test_csv_shows_columns_but_no_values(capsys):
    describe(KRAKEN_FIXTURE)
    out = capsys.readouterr().out

    assert "'txid'" in out and "'amount'" in out
    assert "number, dot decimal" in out
    for value in ("LTEST1", "QTEST1", "ZEUR", "XXBT", "500.0000", "spot / main", "2026-01-05"):
        assert value not in out


def test_excel_shows_columns_but_no_values(tmp_path, capsys):
    describe(write_dnb_xlsx(tmp_path / "dnb.xlsx", DNB_SAMPLE))
    out = capsys.readouterr().out

    for name in DNB_HEADER:
        assert repr(name) in out
    assert "excel date" in out
    for value in ("KAFFEBAR", "LØNN", "Husleie", "30000", "9 000,00", "412", "03.01.2026"):
        assert value not in out
