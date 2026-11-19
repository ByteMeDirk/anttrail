# Usage

This page shows how to work with carts and orders.

## Carts

A cart holds the items a customer wants to buy.

### Add an item

Call `Cart.add` with a SKU and a price in cents.

### Remove an item

Call `Cart.remove` with the SKU.

### Example

```python
# Build a cart with two items.
cart = Cart()
cart.add("pen", 150)
cart.add("ink", 900)
```

## Orders

An order is a cart that a customer has paid for.

### Place an order

Pass the cart to `Order`.

### Example

```python
# Turn the cart into an order.
order = Order("A-1", cart)
```

## Configure pricing

Prices come from `shop/pricing.py`. Change the tax rate there:

```python
# The tax rate is a fraction, not a percentage.
TAX_RATE = 0.15
```

### Rounding

Totals are rounded to the nearest cent.

## Limits

A cart holds at most 100 items.
