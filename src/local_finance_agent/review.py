"""Answer the transfer pairs dbt could not match on its own.

Answers go to the ledger's transfer_decisions table and take effect on the
next `transform`.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import duckdb

FIAT = {"NOK", "EUR", "USD", "GBP", "SEK", "DKK", "CHF"}

QUERY = """
SELECT reason, anchor_side,
       out_id, out_booked_on, out_account, out_asset, out_amount, out_description,
       in_id, in_booked_on, in_account, in_asset, in_amount, in_description,
       day_gap, amount_gap_pct
FROM transfer_review
WHERE reason IN ('ambiguous', 'near_miss')
ORDER BY CASE anchor_side WHEN 'out' THEN out_booked_on ELSE in_booked_on END,
         CASE anchor_side WHEN 'out' THEN out_id ELSE in_id END,
         reason, amount_gap_pct, abs(day_gap)
"""


@dataclass(frozen=True)
class Leg:
    transaction_id: str
    booked_on: date
    account: str
    asset: str
    amount: Decimal
    description: str

    def __str__(self) -> str:
        if self.asset in FIAT:
            amount = f"{self.amount:+,.2f}"
        else:
            amount = format(self.amount.normalize(), "+f")
        return f"{self.booked_on}  {self.account:<18} {amount + ' ' + self.asset:>20}  {self.description}"


@dataclass(frozen=True)
class Option:
    reason: str
    out_leg: Leg
    in_leg: Leg
    day_gap: int
    amount_gap_pct: float | None


def open_questions(con: duckdb.DuckDBPyConnection) -> list[tuple[bool, Leg, list[Option]]]:
    """One question per anchor leg: (anchor is leaving its account, anchor, its options)."""
    questions: dict[str, tuple[bool, Leg, list[Option]]] = {}
    for row in con.execute(QUERY).fetchall():
        reason, leaving = row[0], row[1] == "out"
        option = Option(reason, Leg(*row[2:8]), Leg(*row[8:14]), row[14], row[15])
        anchor = option.out_leg if leaving else option.in_leg
        questions.setdefault(anchor.transaction_id, (leaving, anchor, []))[2].append(option)
    return list(questions.values())


def review_transfers(
    con: duckdb.DuckDBPyConnection,
    ask: Callable[[str], str] = input,
    show: Callable[[str], None] = print,
) -> int:
    """Ask about each open question; returns the number of decisions saved."""
    questions = open_questions(con)
    if not questions:
        show("No transfer pairs waiting for review.")
        return 0

    saved = 0
    used: set[str] = set()  # legs accepted earlier in this session
    for number, (leaving, anchor, options) in enumerate(questions, start=1):
        if anchor.transaction_id in used:
            continue
        options = [o for o in options if not {o.out_leg.transaction_id, o.in_leg.transaction_id} & used]
        if not options:
            continue

        show(f"\n[{number}/{len(questions)}] {'Leaving: ' if leaving else 'Entering:'} {anchor}")
        for choice, option in enumerate(options, start=1):
            other = option.in_leg if leaving else option.out_leg
            gap = f"{option.day_gap:+d} days"
            if option.amount_gap_pct:
                gap += f", {option.amount_gap_pct:.1%} apart in NOK"
            if option.reason == "near_miss":
                gap += ", near miss"
            show(f"   {choice}) {'Entering:' if leaving else 'Leaving: '} {other}  ({gap})")

        while True:
            answer = ask("Number = same transfer, n = none of these, s = skip, q = quit: ").strip().lower()
            if answer == "q":
                show(f"Saved {saved} decisions. Run `local-finance-agent transform` to apply them.")
                return saved
            if answer == "s":
                break
            if answer == "n":
                for option in options:
                    decide(con, option, "reject")
                saved += len(options)
                break
            if answer.isdigit() and 1 <= int(answer) <= len(options):
                option = options[int(answer) - 1]
                decide(con, option, "accept")
                used.update({option.out_leg.transaction_id, option.in_leg.transaction_id})
                saved += 1
                break
            show("Please answer with a listed number, n, s or q.")

    show(f"\nSaved {saved} decisions. Run `local-finance-agent transform` to apply them.")
    return saved


def decide(con: duckdb.DuckDBPyConnection, option: Option, decision: str) -> None:
    con.execute(
        "INSERT OR REPLACE INTO transfer_decisions (out_id, in_id, decision) VALUES (?, ?, ?)",
        [option.out_leg.transaction_id, option.in_leg.transaction_id, decision],
    )
