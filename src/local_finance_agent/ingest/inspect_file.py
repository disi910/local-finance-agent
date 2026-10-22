"""
Describe a CSV or Excel export's format without printing any of its values

"""

import csv
import math
import re
from datetime import date
from pathlib import Path

import pandas as pd

PATTERNS = [
    ("date dd.mm.yyyy", re.compile(r"^\d{2}\.\d{2}\.\d{4}$")),
    ("date yyyy-mm-dd", re.compile(r"^\d{4}-\d{2}-\d{2}$")),
    ("datetime yyyy-mm-dd hh:mm:ss", re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(\.\d+)?$")),
    ("number, comma decimal", re.compile(r"^-?[\d\s\u00a0.]*\d,\d+$")),
    ("number, dot decimal", re.compile(r"^-?\d+(\.\d+)?$")),
]

def classify_text(value: str) -> str:
    if value == "":
        return "empty"
    for name, pattern in PATTERNS:
        if pattern.match(value):
            return name
    return "text"

def classify_cell(value) -> str:
    # Excel types arrive typed: Date: datetime, Number: float

    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "empty"
    if isinstance(value, date):
        return "excel date"
    if isinstance(value, (int, float)):
        if value < 0:
            return "excel number (negative)"
        return "excel number"
    return classify_text(str(value).strip())

def print_columns(header: list[str], body: list[list], classify) -> None:
    print("Columns:")
    for i, name in enumerate(header):
        counts: dict[str, int] = {}
        for row in body:
            kind = classify(row[i]) if i < len(row) else "missing"
            counts[kind] = counts.get(kind, 0) + 1
        summary = ", ".join(f"{k} * {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))
        print(f"    {i:>2}. {name!r:<28} {summary}")

def find_header_row(rows: list[list]) -> int:
    """First row with 3+ text cells followed by a row containing a date or number"""
    for i, row in enumerate(rows[:20]):
        filled = [v for v in row if classify_cell(v) != "empty"]
        if len(filled) >= 3 and all(isinstance(v, str) for v in filled) and i + 1 < len(rows):
            next_kinds = {classify_cell(v) for v in rows[i + 1]}
            if any(k.startswith(("excel", "date", "number")) for k in next_kinds):
                return i
    return 0

def describe_excel(path: Path) -> None:
    sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=object)
    print(f"File:        {path.name}")
    print(f"Sheets:      {list(sheets)}")
    for sheet_name, df in sheets.items():
        rows = df.values.tolist()
        header_row = find_header_row(rows)
        header = [str(v).strip() if classify_cell(v) != "empty" else "" for v in rows[header_row]]
        body = rows[header_row + 1 :]
        print(f"\nSheet:       {sheet_name!r}")
        print(f"Header row:  {header_row} (0-based; {header_row} row(s) above it skipped)")
        print(f"Data rows:   {len(body)}")
        print_columns(header, body, classify_cell)
    print("\nCheck that the column names above contain no personal details before sharing.")


def describe_csv(path: Path) -> None:
    raw = path.read_bytes()
    encoding = "unknown"
    for candidate in ("utf-8-sig", "cp1252"):
        try:
            raw.decode(candidate)
            encoding = candidate
            break
        except UnicodeDecodeError:
            continue
    text = raw.decode(encoding)
    dialect = csv.Sniffer().sniff(text[:5000], delimiters=",;\t")
    rows = list(csv.reader(text.splitlines(), dialect))
    header, body = rows[0], rows[1:]
    print(f"File:       {path.name}")
    print(f"Encoding:   {encoding}")
    print(f"Delimiter:  {dialect.delimiter!r}")
    print(f"Data rows:  {len(body)}")
    print_columns(header, body, lambda v: classify_text(v.strip()))


def describe(path: Path) -> None:
    if path.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        describe_excel(path)
    else:
        describe_csv(path)