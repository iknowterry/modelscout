# shoplib

A small inventory, pricing and order library with a tiny command-line tool.
Standard library only, Python 3.11.

- `shoplib/inventory.py` - products and stock levels
- `shoplib/pricing.py` - discounts and tax
- `shoplib/orders.py` - placing and cancelling orders
- `shoplib/csvio.py` - catalog and order CSV import/export
- `shoplib/report.py` - plain-text sales and stock reports
- `shoplib/cli.py` - `python -m shoplib --catalog catalog.csv list|value|add|order`

All money is integer cents. Run the tests with:

    python3 -m unittest discover -s tests -t .
