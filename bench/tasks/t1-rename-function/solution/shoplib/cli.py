"""Command-line interface: ``python -m shoplib --catalog FILE <command>``."""
from __future__ import annotations

import argparse
import sys
from decimal import Decimal, InvalidOperation
from typing import Optional, Sequence

from . import csvio
from .errors import ShopError
from .inventory import Inventory
from .models import Product
from .money import format_cents
from .orders import OrderService


def _parse_price(text: str) -> int:
    """Argparse type: turn a price argument such as ``12.50`` into cents."""
    try:
        value = Decimal(text.strip())
    except InvalidOperation:
        raise argparse.ArgumentTypeError(f"invalid price: {text!r}") from None
    cents = value * 100
    if not value.is_finite() or value < 0 or cents != cents.to_integral_value():
        raise argparse.ArgumentTypeError(f"invalid price: {text!r}")
    return int(cents)


def _parse_item(text: str) -> tuple[str, int]:
    """Argparse type: turn ``SKU:QTY`` into a ``(sku, qty)`` pair."""
    sku, sep, qty = text.partition(":")
    if not sep or not sku or not qty.isdigit() or int(qty) <= 0:
        raise argparse.ArgumentTypeError(f"invalid item: {text!r} (expected SKU:QTY)")
    return sku, int(qty)


def _cmd_list(args: argparse.Namespace, inventory: Inventory) -> int:
    for product in inventory:
        print(f"{product.sku}\t{product.name}\t{product.quantity}\t{format_cents(product.price_cents)}")
    return 0


def _cmd_value(args: argparse.Namespace, inventory: Inventory) -> int:
    print(f"Total inventory value: {format_cents(inventory.total_value_cents())}")
    return 0


def _cmd_add(args: argparse.Namespace, inventory: Inventory) -> int:
    inventory.add_product(Product(args.sku, args.name, args.price, args.qty))
    csvio.save_catalog(inventory, args.catalog)
    print(f"added {args.sku}")
    return 0


def _cmd_order(args: argparse.Namespace, inventory: Inventory) -> int:
    service = OrderService(inventory)
    order = service.place(args.items)
    csvio.save_catalog(inventory, args.catalog)
    print(f"order {order.id}: {format_cents(service.total_cents(order))}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(prog="shoplib", description="Manage a small product catalog.")
    parser.add_argument("--catalog", default="catalog.csv", help="catalog CSV file (default: %(default)s)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="list all products")
    p_list.set_defaults(handler=_cmd_list)

    p_value = sub.add_parser("value", help="show the total stock value")
    p_value.set_defaults(handler=_cmd_value)

    p_add = sub.add_parser("add", help="add a product")
    p_add.add_argument("sku")
    p_add.add_argument("name")
    p_add.add_argument("price", type=_parse_price)
    p_add.add_argument("--qty", type=int, default=0, help="initial stock (default: 0)")
    p_add.set_defaults(handler=_cmd_add)

    p_order = sub.add_parser("order", help="place an order")
    p_order.add_argument("items", nargs="+", type=_parse_item, metavar="SKU:QTY")
    p_order.set_defaults(handler=_cmd_order)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the CLI and return the process exit code."""
    args = build_parser().parse_args(argv)
    try:
        inventory = csvio.load_catalog(args.catalog)
        return args.handler(args, inventory)
    except ShopError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
