import unittest

from src.common.athena import accounts_from_rows


class AccountsFromRowsTests(unittest.TestCase):
    def test_account_with_only_post_sale_events_has_zero_sales_and_orders(self):
        # Athena returns NULL for the sale-side sums when the account only had refunds that day.
        rows = [
            {
                "nm_conta": "Refunds Only",
                "sales": None,
                "fees": None,
                "sale_taxes": None,
                "commissions": None,
                "shipping_handling": None,
                "orders": None,
                "refunds": "52.00",
                "sale_tax_refunds": "2.00",
                "chargebacks": None,
                "commissions_voids": None,
            }
        ]

        [account] = accounts_from_rows(rows)

        self.assertEqual(account["account_name"], "Refunds Only")
        self.assertEqual((account["gross_sales"], account["aov"]), (0, 0))
        self.assertEqual((account["refunds"], account["taxes"], account["net_sales"]), (52.0, -2.0, -50.0))


if __name__ == "__main__":
    unittest.main()
