import unittest
from datetime import date

from src.scripts.extracao_diaria_pagamerican_lake import build_report


def row(product, **values):
    base = {key: None for key in ("sales", "fees", "sale_taxes", "commissions", "shipping_handling", "orders", "refunds", "chargebacks")}
    return {"nm_conta": product, **base, **values}


class BuildReportTests(unittest.TestCase):
    def test_maps_lake_rows_to_pagamerican_report(self):
        report = build_report(
            [row("SodaPeak", sales="400.00", fees="28.00", sale_taxes="20.00", commissions="250.00", orders="2", refunds="40.00")],
            date(2026, 10, 29),
        )

        self.assertEqual((report["gateway"], report["source"]), ("Pagamerican", "lake"))
        self.assertEqual(report["contas"]["sodapeak"]["net_sales"], 62.0)

    def test_order_without_front_item_fails_instead_of_guessing_the_account(self):
        with self.assertRaisesRegex(ValueError, "front"):
            build_report([row(None, sales="10.00", orders="1")], date(2026, 10, 29))


if __name__ == "__main__":
    unittest.main()
