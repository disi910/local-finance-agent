from datetime import date
from decimal import Decimal

from local_finance_agent.ingest.ids import IdFactory


def make_two_coffees():
    ids = IdFactory("dnb")
    args = ("dnb:brukskonto", date(2026, 3, 2), Decimal("-49.00"), "NOK", "KAFFEBAR OSLO")
    return ids.make(*args), ids.make(*args)


def test_identical_rows_get_different_ids():
    first, second = make_two_coffees()
    assert first != second


def test_ids_are_stable_across_imports():
    assert make_two_coffees() == make_two_coffees()


def test_amount_formatting_does_not_change_the_id():
    a = IdFactory("dnb").make("dnb:brukskonto", date(2026, 3, 2), Decimal("-49.00"), "NOK", "X")
    b = IdFactory("dnb").make("dnb:brukskonto", date(2026, 3, 2), Decimal("-49"), "NOK", "X")
    assert a == b