"""CSV import and export for the catalog and for orders."""
import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .errors import ValidationError
from .inventory import Inventory
from .models import Product

FIELDS = ["sku", "name", "price", "quantity"]


def parse_price(text):
    """Parse a price such as ``12.34`` or ``$1,234.50`` into integer cents.

    Raises ``ValidationError`` for negatives, junk and sub-cent amounts.
    """
    cleaned = text.strip().lstrip("$").replace(",", "")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        raise ValidationError(f"invalid price: {text!r}") from None
    cents = value * 100
    if not value.is_finite() or value < 0 or cents != cents.to_integral_value():
        raise ValidationError(f"invalid price: {text!r}")
    return int(cents)


def format_price(cents):
    """Plain decimal price for CSV output (no currency symbol)."""
    dollars, rem = divmod(cents, 100)
    return f"{dollars}.{rem:02d}"


def read_products(fileobj):
    """Read products from an open CSV file and return them as a list.

    The header must contain every column in ``FIELDS``. Problems are
    reported as ``ValidationError`` with the 1-based data row number.
    """
    reader = csv.DictReader(fileobj)
    for column in FIELDS:
        if column not in (reader.fieldnames or []):
            raise ValidationError(f"missing column: {column}")
    products = []
    for number, row in enumerate(reader, start=1):
        try:
            price = parse_price(row["price"])
        except ValidationError as exc:
            raise ValidationError(f"row {number}: {exc}") from None
        try:
            quantity = int(row["quantity"])
        except ValueError:
            raise ValidationError(f"row {number}: invalid quantity: {row['quantity']!r}") from None
        if quantity < 0:
            raise ValidationError(f"row {number}: invalid quantity: {row['quantity']!r}")
        products.append(Product(sku=row["sku"].strip(), name=row["name"].strip(),
                                price_cents=price, quantity=quantity))
    return products


def write_products(products, fileobj):
    """Write products to an open CSV file with a header row."""
    writer = csv.DictWriter(fileobj, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    for product in products:
        writer.writerow({
            "sku": product.sku,
            "name": product.name,
            "price": format_price(product.price_cents),
            "quantity": product.quantity,
        })


def load_catalog(path):
    """Load an ``Inventory`` from a CSV file; a missing file gives an empty one."""
    inventory = Inventory()
    if not Path(path).exists():
        return inventory
    with open(path, newline="") as fileobj:
        for product in read_products(fileobj):
            inventory.add_product(product)
    return inventory


def save_catalog(inventory, path):
    """Write the whole inventory to a CSV file, sorted by SKU."""
    with open(path, "w", newline="") as fileobj:
        write_products(list(inventory), fileobj)


def write_orders(service, fileobj):
    """Export every order as ``id,status,units,total`` rows (total in dollars)."""
    writer = csv.writer(fileobj, lineterminator="\n")
    writer.writerow(["id", "status", "units", "total"])
    for order in service.orders():
        writer.writerow([order.id, order.status, order.units,
                         format_price(service.total_cents(order))])
