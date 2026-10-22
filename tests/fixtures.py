"""Synthetic statement files, written at test time so no binary fixture is committed."""

from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

DNB_HEADER = ["Dato", "Forklaring", "Rentedato", "Ut fra konto", "Inn på konto"]

# Mixes what real exports contain: Excel date cells and dd.mm.yyyy text,
# Excel numbers and "1 234,50" text, outflows written as 500 and as -500,
# a blank row and a summary row without a date.
DNB_SAMPLE = [
    (datetime(2026, 1, 2), "LØNN ACME AS", datetime(2026, 1, 2), None, 30000.0),
    ("03.01.2026", "Husleie januar", "03.01.2026", "9 000,00", None),
    (datetime(2026, 1, 5), "KIWI 123 OSLO", datetime(2026, 1, 5), -412.3, None),
    (datetime(2026, 1, 6), "KAFFEBAR OSLO", datetime(2026, 1, 6), 49.0, None),
    (datetime(2026, 1, 6), "KAFFEBAR OSLO", datetime(2026, 1, 6), 49.0, None),
    (datetime(2026, 1, 7), "Vipps refusjon", datetime(2026, 1, 7), None, 0.1 + 0.2),
    (None, None, None, None, None),
    (None, "Sum", None, 9510.3, 30000.3),
]


def write_dnb_xlsx(path: Path, rows: list[tuple], header: list[str] = DNB_HEADER) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Siste transaksjoner"
    sheet.append(header)
    for row in rows:
        sheet.append(list(row))
    workbook.save(path)
    return path
