"""Price calculations."""

TAX_RATE = 0.15


def apply_tax(amount_cents: int, rate: float) -> int:
    """Return the amount with tax added, rounded to a cent."""
    return round(amount_cents * (1 + rate))
