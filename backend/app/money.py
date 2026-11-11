"""Money parsing and allocation. All arithmetic uses Decimal; float never touches an amount."""

import re
from decimal import Decimal

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
# Largest value that fits NUMERIC(12,2).
MAX_AMOUNT = Decimal("9999999999.99")

_AMOUNT_RE = re.compile(r"^\d+(\.\d+)?$")


def parse_amount(value: object) -> Decimal:
    """Parse a positive THB amount sent as a string such as "1000.00".

    Rejects non-strings (a JSON number may already have lost precision), signs, exponents,
    more than two decimal places, zero and anything that would not fit NUMERIC(12,2).
    """
    if not isinstance(value, str):
        raise ValueError('Amount must be a string such as "1000.00"')
    if not _AMOUNT_RE.match(value):
        raise ValueError('Amount must be a plain decimal number such as "1000.00"')
    if "." in value and len(value.split(".", 1)[1]) > 2:
        raise ValueError("Amount must have at most 2 decimal places")
    amount = Decimal(value)
    if amount <= 0:
        raise ValueError("Amount must be greater than zero")
    if amount > MAX_AMOUNT:
        raise ValueError(f"Amount must not exceed {MAX_AMOUNT}")
    return amount.quantize(CENT)


def to_satang(amount: Decimal) -> int:
    """Convert a 2-decimal-place amount to an integer number of satang."""
    satang = amount * 100
    if satang != satang.to_integral_value():
        raise ValueError(f"{amount} has more than 2 decimal places")
    return int(satang)


def from_satang(satang: int) -> Decimal:
    return (Decimal(satang) / 100).quantize(CENT)


def allocate_equal(total: Decimal, count: int) -> list[Decimal]:
    """Split `total` into `count` shares that differ by at most one satang.

    The leftover satang go one at a time to the first members in the order listed, so
    1000.00 / 3 -> [333.34, 333.33, 333.33] and the shares always sum to `total`.
    """
    if count <= 0:
        raise ValueError("count must be positive")
    base, remainder = divmod(to_satang(total), count)
    return [from_satang(base + (1 if i < remainder else 0)) for i in range(count)]


def format_money(amount: Decimal) -> str:
    """Render as a fixed 2-decimal string, never "-0.00"."""
    q = amount.quantize(CENT)
    return str(ZERO if q == 0 else q)
