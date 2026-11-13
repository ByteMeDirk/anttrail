"""A shopping cart."""

from shop.pricing import TAX_RATE, apply_tax

MAX_ITEMS = 100


class Cart:
    """Items a customer wants to buy."""

    def __init__(self) -> None:
        self.items: dict[str, int] = {}

    def add(self, sku: str, price_cents: int) -> None:
        """Add an item to the cart."""
        if len(self.items) >= MAX_ITEMS:
            raise ValueError("the cart is full")
        self.items[sku] = price_cents

    def remove(self, sku: str) -> None:
        """Remove an item from the cart."""
        del self.items[sku]

    def total_cents(self) -> int:
        """Return the cart total including tax."""
        subtotal = sum(self.items.values())
        return apply_tax(subtotal, TAX_RATE)
