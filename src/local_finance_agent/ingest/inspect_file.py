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
        counts = dict[str, int] = {}
        for row in body:
            kind = classify(row[i]) if i < len(row) else "missing"
            counts[kind] = counts.get(kind, 0) + 1
        summary = ", ".join(f"{k} * {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))
        print(f"    {i:>2}. {name!r:<28} {summary}")

