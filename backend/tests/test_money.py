from decimal import Decimal

import pytest

from app.money import allocate_equal, format_money, parse_amount


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1000.00", "1000.00"), ("1000", "1000.00"), ("0.5", "0.50"), ("0.01", "0.01")],
)
def test_parse_amount_accepts_valid_strings(raw: str, expected: str) -> None:
    assert parse_amount(raw) == Decimal(expected)
    assert str(parse_amount(raw)) == expected


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ("10.005", "at most 2 decimal places"),
        ("0", "greater than zero"),
        ("0.00", "greater than zero"),
        ("-1.00", "plain decimal"),
        ("1e3", "plain decimal"),
        (" 10", "plain decimal"),
        ("", "plain decimal"),
        ("NaN", "plain decimal"),
        ("10000000000.00", "must not exceed"),
        (10.5, "must be a string"),
        (100, "must be a string"),
    ],
)
def test_parse_amount_rejects_invalid_values(raw: object, reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        parse_amount(raw)


@pytest.mark.parametrize(
    ("total", "count", "expected"),
    [
        ("100.00", 3, ["33.34", "33.33", "33.33"]),
        ("1000.00", 3, ["333.34", "333.33", "333.33"]),
        ("0.02", 3, ["0.01", "0.01", "0.00"]),
        ("10.00", 4, ["2.50", "2.50", "2.50", "2.50"]),
        ("0.05", 3, ["0.02", "0.02", "0.01"]),
        ("9999999999.99", 7, ["1428571428.57"] * 7),
    ],
)
def test_allocate_equal_gives_remainder_to_first_listed(
    total: str, count: int, expected: list[str]
) -> None:
    shares = allocate_equal(Decimal(total), count)
    assert [str(s) for s in shares] == expected
    assert sum(shares) == Decimal(total)


def test_format_money_never_renders_negative_zero() -> None:
    assert format_money(Decimal("-0.00")) == "0.00"
    assert format_money(Decimal("-333.33")) == "-333.33"
