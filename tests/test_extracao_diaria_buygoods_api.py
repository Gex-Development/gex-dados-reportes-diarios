import unittest
from datetime import date

from src.common.report import account_metrics
from src.scripts.extracao_diaria_buygoods_api import count_orders, count_refunds, ledger_net_line

DAY = date(2026, 10, 28)

# Gelagen ledger "net" line for 2026-10-28 sales, as returned by /transactions.php.
GELAGEN_NET = {
    "date": "2026-10-29 08:12:03",
    "product_notes": "$26,252.94 Net ($225,156.04 Sales, ...)",
    "sales": "225156.04",
    "refunds": "61178.67",
    "chargebacks": "2377.46",
    "alerts": "1500.00",
    "fees": "16535.92",
    "fee_voids": "0.00",
    "shipping_handling": "0.00",
    "commissions": "110238.61",
    "commissions_voids": "326.91",
    "sale_taxes": "10095.44",
    "sale_tax_refunds": "2696.09",
}


def order(user, session, created, action="neworder", test="0"):
    return {"user_id": user, "sessid2": session, "rr_createdate": created, "action_type": action, "is_test": test}


def refund(order_id, codename, refunded, action="refund"):
    return {"order_id_global": order_id, "product_codename": codename, "action_type": action, "date_refunded": refunded}


class LedgerNetLineTests(unittest.TestCase):
    def test_picks_net_line_posted_the_morning_after_the_report_date(self):
        hold = {"date": "2026-10-29 08:12:04", "product_notes": "Allowance On Hold (2026-10-28 to 2026-10-28)"}
        previous_day = {**GELAGEN_NET, "date": "2026-10-28 08:12:01"}

        self.assertIs(ledger_net_line([previous_day, hold, GELAGEN_NET], DAY), GELAGEN_NET)

    def test_returns_none_when_ledger_has_no_net_line_for_the_day(self):
        self.assertIsNone(ledger_net_line([{**GELAGEN_NET, "date": "2026-10-28 08:12:01"}], DAY))


class CountOrdersTests(unittest.TestCase):
    def test_counts_checkout_sessions_on_day_excluding_cancel_and_test(self):
        orders = [
            order("1", "a", "2026-10-28 10:00:00"),
            order("1", "a", "2026-10-28 10:08:00"),  # upsell, same checkout
            order("1", "b", "2026-10-28 18:00:00", action="refund"),
            order("2", "a", "2026-10-28 11:00:00"),  # same sessid2, other customer
            order("3", "c", "2026-10-28 12:00:00", action="cancel"),
            order("4", "d", "2026-10-28 13:00:00", test="1"),
            order("5", "e", "2026-10-27 23:59:59"),
            order("6", "f", "2026-10-29 00:00:00"),
        ]

        self.assertEqual(count_orders(orders, DAY), 3)


class CountRefundsTests(unittest.TestCase):
    def test_counts_refunds_issued_on_day_whatever_the_sale_date(self):
        orders = [
            refund("A", "PP", "2026-10-28 09:00:00"),
            refund("A", "PP", "2026-10-28 09:00:00"),  # API duplicate
            refund("A", "UP1", "2026-10-28 23:59:59"),  # same order id, other item
            refund("B", "PP", "2026-10-29 00:00:01"),
            refund("C", "PP", "2026-10-28 10:00:00", action="chargeback"),
            refund("D", "PP", "0000-00-00 00:00:00", action="neworder"),
        ]

        self.assertEqual(count_refunds(orders, DAY), 2)


class AccountMetricsTests(unittest.TestCase):
    def test_maps_ledger_to_panel_metrics_net_of_one_dollar_refund_fee(self):
        metrics = account_metrics("Gelagen", GELAGEN_NET, 484, 235)

        self.assertEqual(
            metrics,
            {
                "account_name": "Gelagen",
                "gross_sales": 208620.12,
                "shipping_and_handling": 0.0,
                "commissions": 110238.61,
                "refunds": 60943.67,
                "chargebacks": 2377.46,
                "commission_voids": 326.91,
                "affiliate_epo": 227.09,
                "taxes": 7399.35,
                "aov": 431.03,
                "epo": 57.83,
                "net_sales": 27987.94,
            },
        )

    def test_per_order_metrics_are_zero_without_orders(self):
        refunds_only = {key: "0.00" for key in GELAGEN_NET}
        refunds_only["refunds"] = "52.00"

        metrics = account_metrics("Refunds Only", refunds_only, 0, 2)

        self.assertEqual((metrics["aov"], metrics["epo"], metrics["affiliate_epo"]), (0, 0, 0))
        self.assertEqual((metrics["refunds"], metrics["net_sales"]), (50.0, -50.0))


if __name__ == "__main__":
    unittest.main()
