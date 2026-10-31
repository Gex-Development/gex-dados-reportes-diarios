import tempfile
import unittest
from datetime import date
from pathlib import Path

from openpyxl import Workbook

from src.transformations.pagamerican_report import transform_file

DAY = date(2026, 10, 29)


def write_export(path: Path, refunds: bool) -> None:
    workbook = Workbook()
    workbook.active.title = "OnePager"
    purchases = workbook.create_sheet("Purchases")
    purchases.append(["Order ID", "Purchase Type", "Product Name"])
    purchases.append([1, "Initial", "SodaPeak"])
    purchases.append([1, "Upsell", "Sodapril"])  # upsell of another product stays in the SodaPeak order
    purchases.append([2, "Initial", "SodaPeak"])
    purchases.append([3, "Initial", "Sodapril"])
    orders = workbook.create_sheet("Orders")
    orders.append(["Order ID", "Order Amount", "Creator Tax", "Creator Platform Fee", "Affiliation Amount"])
    orders.append([1, 300.0, 20.0, 21.0, 200.0])
    orders.append([2, 100.0, 0.0, 7.0, 50.0])
    orders.append([3, 80.0, 5.0, 6.0, None])
    if refunds:
        sheet = workbook.create_sheet("Refunds&Chargebacks")
        sheet.append(["Order ID", "Product Name", "Refundamount", "chargebackamount"])
        sheet.append([2, "SodaPeak", -40.0, None])
        sheet.append([3, "Sodapril", None, -80.0])
    workbook.save(path)


class PagAmericanTransformationTests(unittest.TestCase):
    def test_groups_orders_by_front_product_with_panel_formula(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "pagamerican.xlsx"
            write_export(source, refunds=True)

            report = transform_file(source, Path(directory) / "pagamerican.json", DAY)

        self.assertEqual(
            (report["gateway"], report["source"], report["report_date"]), ("Pagamerican", "web", "2026-10-29")
        )
        self.assertEqual(
            report["contas"]["sodapeak"],
            {
                "account_name": "SodaPeak",
                "gross_sales": 372.0,
                "shipping_and_handling": 0.0,
                "commissions": 250.0,
                "refunds": 40.0,
                "chargebacks": 0.0,
                "commission_voids": 0.0,
                "affiliate_epo": 125.0,
                "taxes": 20.0,
                "aov": 186.0,
                "epo": 31.0,
                "net_sales": 62.0,
            },
        )
        sodapril = report["contas"]["sodapril"]
        self.assertEqual((sodapril["chargebacks"], sodapril["net_sales"]), (80.0, -11.0))

    def test_missing_refunds_sheet_means_no_refunds(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "pagamerican.xlsx"
            write_export(source, refunds=False)

            report = transform_file(source, Path(directory) / "pagamerican.json", DAY)

        self.assertEqual(report["contas"]["sodapril"]["refunds"], 0.0)
        self.assertEqual(report["contas"]["sodapril"]["chargebacks"], 0.0)


if __name__ == "__main__":
    unittest.main()
