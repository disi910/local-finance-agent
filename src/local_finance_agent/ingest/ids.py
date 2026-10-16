"""Stable transaction IDs.

A transaction must get the same ID every time the same statement is imported,
so re-imports can be detected and skipped.
"""

import hashlib
from collections import Counter
from datetime import date
from decimal import Decimal


def canonical_amount(amount: Decimal) -> str:
    """'-100.50', '-100.5' and '-100.500' must all hash the same."""
    return format(amount.normalize(), "f")


class IdFactory:
    """Builds hash IDs for sources that have no IDs of their own.

    Two identical rows (same account, date, amount and text, e.g. two coffees
    on the same day) would hash to the same value, so each gets an occurrence
    number: the first is #1, the second #2. Because the occurrence count is
    based on the row's content, the same file always produces the same IDs.
    """

    def __init__(self, source: str) -> None:
        self.source = source
        self._seen: Counter[str] = Counter()

    def make(self, account: str, booked_on: date, amount: Decimal, asset: str, description: str) -> str:
        key = "|".join(
            [self.source, account, booked_on.isoformat(), canonical_amount(amount), asset, description.strip()]
        )
        self._seen[key] += 1
        digest = hashlib.sha256(f"{key}|{self._seen[key]}".encode()).hexdigest()[:24]
        return f"{self.source}:{digest}"