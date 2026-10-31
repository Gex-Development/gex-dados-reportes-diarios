import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook

from src.scripts.extracao_diaria_pagamerican_web import check_period, export_filters, export_path


class ExportPathTests(unittest.TestCase):
    def test_partitions_report_by_data_date(self):
        self.assertEqual(
            export_path(Path("/project"), date(2026, 10, 28)),
            Path("/project/exports/pagamerican/web/2026/10/pagamerican_2026-10-28.xlsx"),
        )


class ExportFiltersTests(unittest.TestCase):
    def test_start_and_end_stay_on_the_same_utc_day(self):
        # The backend keeps only the date part of each bound and exports both days whole.
        self.assertEqual(
            export_filters(date(2026, 10, 29)),
            {"startDate": "2026-10-29T00:00:00.000Z", "endDate": "2026-10-29T23:59:59.999Z"},
        )


class CheckPeriodTests(unittest.TestCase):
    def write(self, directory: str, *rows: tuple[datetime, datetime]) -> Path:
        path = Path(directory) / "report.xlsx"
        workbook = Workbook()
        sheet = workbook.create_sheet("Purchases")
        sheet.append(["Purchase ID", "Checkout Initialized At", "Transaction Date"])
        for index, (checkout, paid) in enumerate(rows):
            sheet.append([index, checkout, paid])
        workbook.save(path)
        return path

    def test_accepts_order_opened_on_the_day_and_paid_after_midnight(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write(
                directory,
                (datetime(2026, 10, 28, 10, 0), datetime(2026, 10, 28)),
                (datetime(2026, 10, 28, 23, 53), datetime(2026, 10, 29)),
            )
            check_period(path, date(2026, 10, 28))

    def test_rejects_export_spilling_into_another_day(self):
        # What the panel's own "Yesterday" produced before the period was pinned: D and D+1 together.
        with tempfile.TemporaryDirectory() as directory:
            path = self.write(
                directory,
                (datetime(2026, 10, 29, 9, 0), datetime(2026, 10, 29)),
                (datetime(2026, 10, 30, 9, 0), datetime(2026, 10, 30)),
            )
            with self.assertRaisesRegex(ValueError, "2026-10-30"):
                check_period(path, date(2026, 10, 29))


if __name__ == "__main__":
    unittest.main()
