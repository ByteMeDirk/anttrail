"""Orders placed from a cart."""

from dataclasses import dataclass

from shop.cart import Cart


@dataclass
class Order:
    """A cart that has been paid for."""

    order_id: str
    cart: Cart

    def total_cents(self) -> int:
        """Return the total the customer paid."""
        return self.cart.total_cents()
