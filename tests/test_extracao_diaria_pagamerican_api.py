import unittest
from datetime import date

from src.scripts.extracao_diaria_pagamerican_api import build_report, dedupe_page

DAY = date(2026, 10, 29)


class PagAmericanApiTests(unittest.TestCase):
    def test_front_product_owns_upsell_and_partial_refund(self):
        orders = [
            {
                "orderId": "one",
                "checkoutInitializedAt": "2026-10-29 15:00:00.000",
                "orderCreatedAt": "2026-10-29 15:00:00.000",
                "amountTransaction": 120,
                "amountCreatorPlatformFee": 10,
                "amountCreatorTax": 5,
                "amountAffiliation": 20,
            },
            {
                "orderId": "two",
                "checkoutInitializedAt": "2026-10-29 17:00:00.000",
                "orderCreatedAt": "2026-10-29 17:00:00.000",
                "amountTransaction": 50,
                "amountCreatorPlatformFee": 4,
                "amountCreatorTax": 2,
                "amountAffiliation": 10,
            },
        ]
        purchases = [
            {"orderId": "one", "purchaseType": "front", "productName": "SodaPeak"},
            {"orderId": "one", "purchaseType": "upsell", "productName": "Another Product"},
            {"orderId": "two", "purchaseType": "front", "productName": "SodaPeak"},
        ]
        refunds = [
            {
                "orderId": "one",
                "refundSource": "reembolso",
                "refundType": "partially_refunded",
                "amountRequested": 120,
                "amountRefundedTotal": 12.34,
            }
        ]
        chargebacks = [
            {"orderId": "two", "refundSource": "chargeback", "refundType": "chargeback", "amountRefundedTotal": 7.65}
        ]
        account = build_report(orders, purchases, refunds, chargebacks, DAY)["contas"]["sodapeak"]
        self.assertEqual(
            account,
            {
                "account_name": "SodaPeak",
                "gross_sales": 156,
                "shipping_and_handling": 0,
                "commissions": 30,
                "refunds": 12.34,
                "chargebacks": 7.65,
                "commission_voids": 0,
                "affiliate_epo": 15,
                "taxes": 7,
                "aov": 78,
                "epo": 49.5,
                "net_sales": 99.01,
            },
        )

    def test_event_ids_are_strings_and_chargeback_alert_is_returned_money(self):
        orders = [
            {
                "orderId": 123,
                "checkoutInitializedAt": "2026-10-29 10:00:00",
                "orderCreatedAt": "2026-10-29 10:05:00",
                "amountTransaction": 100,
                "amountCreatorPlatformFee": 0,
                "amountCreatorTax": 0,
                "amountAffiliation": 0,
            }
        ]
        purchases = [{"orderId": 123, "purchaseType": "front", "productName": "SodaPeak"}]
        refunds = [
            {"orderId": "123", "refundSource": "reembolso", "amountRefundedTotal": 8},
            {"orderId": "123", "refundSource": "alerta", "amountRefundedTotal": 100},
        ]
        chargebacks = [{"orderId": "123", "refundSource": "alerta", "amountRefundedTotal": 12}]
        account = build_report(orders, purchases, refunds, chargebacks, DAY)["contas"]["sodapeak"]
        self.assertEqual((account["refunds"], account["chargebacks"], account["net_sales"]), (8, 12, 80))

    def test_panel_date_is_checkout_day_not_order_creation_day(self):
        orders = [
            {
                "orderId": 123,
                "checkoutInitializedAt": "2026-10-28 23:53:21",
                "orderCreatedAt": "2026-10-29 00:02:47",
                "amountTransaction": 331.92,
            }
        ]
        purchases = [{"orderId": 123, "purchaseType": "front", "productName": "SodaPeak"}]
        self.assertEqual(build_report(orders, purchases, [], [], DAY)["contas"], {})

    def test_only_report_day_orders_count_and_events_of_those_orders_apply(self):
        orders = [
            {
                "orderId": "day",
                "checkoutInitializedAt": "2026-10-29 10:00:00",
                "orderCreatedAt": "2026-10-29 10:00:00",
                "amountTransaction": 100,
                "amountCreatorPlatformFee": 0,
                "amountCreatorTax": 0,
                "amountAffiliation": 0,
            },
            {
                "orderId": "next",
                "checkoutInitializedAt": "2026-10-30 00:00:00",
                "orderCreatedAt": "2026-10-30 00:00:00",
                "amountTransaction": 200,
            },
        ]
        purchases = [
            {"orderId": "day", "purchaseType": "front", "productName": "A"},
            {"orderId": "next", "purchaseType": "front", "productName": "B"},
        ]
        refunds = [
            {
                "orderId": "day",
                "refundSource": "reembolso",
                "amountRefundedTotal": 9,
                "requestedAt": "2026-10-30 09:00:00",
            },
            {"orderId": "next", "refundSource": "reembolso", "amountRefundedTotal": 88},
        ]
        account = build_report(orders, purchases, refunds, [], DAY)["contas"]
        self.assertEqual(list(account), ["a"])
        self.assertEqual((account["a"]["refunds"], account["a"]["aov"]), (9, 100))

    def test_unmatched_order_cannot_be_silently_attributed(self):
        with self.assertRaisesRegex(ValueError, "no front purchase"):
            build_report([{"orderId": "one", "checkoutInitializedAt": "2026-10-29 12:00:00"}], [], [], [], DAY)

    def test_blank_front_product_cannot_be_silently_attributed(self):
        with self.assertRaisesRegex(ValueError, "no product"):
            build_report(
                [{"orderId": "one", "checkoutInitializedAt": "2026-10-29 12:00:00"}],
                [{"orderId": "one", "purchaseType": "front", "productName": None}],
                [],
                [],
                DAY,
            )

    def test_deduplication_rejects_missing_rows_at_page_boundary(self):
        with self.assertRaisesRegex(ValueError, "INCOMPLETE"):
            dedupe_page([{"purchaseId": 1}, {"purchaseId": 2}, {"purchaseId": 2}], "purchaseId")
        self.assertEqual(
            dedupe_page([{"purchaseId": 1}, {"purchaseId": 2}], "purchaseId"), [{"purchaseId": 1}, {"purchaseId": 2}]
        )


if __name__ == "__main__":
    unittest.main()
