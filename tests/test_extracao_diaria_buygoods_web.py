import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from playwright.sync_api import sync_playwright

from src.scripts.extracao_diaria_buygoods_web import (
    existing_local_export,
    export_action,
    add_selected_action,
    export_filename,
    export_path,
    parse_args,
    report_title,
)


class ExportNamingTests(unittest.TestCase):
    def test_uses_data_date_for_report_title_and_partitioned_path(self):
        day = date(2026, 10, 28)
        root = Path("/project")

        self.assertEqual(report_title(day), "Master Accounts - 2026-10-28")
        self.assertEqual(export_filename(day, ".xls"), "master_accounts_2026-10-28.xls")
        self.assertEqual(
            export_path(root, day, ".xls"),
            root / "exports" / "buygoods" / "web" / "2026" / "10" / "master_accounts_2026-10-28.xls",
        )

    def test_rejects_unknown_download_extension(self):
        with self.assertRaises(ValueError):
            export_filename(date(2026, 10, 28), ".csv")


class ExistingExportTests(unittest.TestCase):
    def test_json_sidecar_is_not_selected_as_the_source_spreadsheet(self):
        day = date(2026, 10, 28)
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            spreadsheet = export_path(root, day, ".xls")
            spreadsheet.parent.mkdir(parents=True)
            spreadsheet.touch()
            spreadsheet.with_suffix(".json").write_text("{}")

            self.assertEqual(existing_local_export(root, day), spreadsheet)


class ExportActionSelectorTests(unittest.TestCase):
    def test_finds_visible_export_action_when_hidden_duplicates_exist(self):
        html = (
            '<style>.d-none{display:none}</style>'
            '<div id="export" class="col-auto d-none">'
            '<a action="export" href="javascript:;">'
            '<i class="bi-download me-1"></i> Export</a></div>'
            '<div id="export" class="col-auto">'
            '<a action="export" href="javascript:;" onclick="window.clicked=true;return false">'
            '<i class="bi-download me-1"></i> Export</a></div>'
        )
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            try:
                page = browser.new_page()
                page.set_content(html)

                export_action(page).click(timeout=500)

                self.assertTrue(page.evaluate("window.clicked"))
            finally:
                browser.close()


class AddSelectedActionTests(unittest.TestCase):
    def test_finds_add_selected_anchor_without_link_role(self):
        html = (
            '<div role="dialog">'
            '<a action="add" class="btn btn-success btn-sm" '
            'onclick="window.clicked=true;return false">Add Selected</a>'
            '</div>'
        )
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            try:
                page = browser.new_page()
                page.set_content(html)

                add_selected_action(page.get_by_role("dialog")).click(timeout=500)

                self.assertTrue(page.evaluate("window.clicked"))
            finally:
                browser.close()




class CommandLineTests(unittest.TestCase):
    def test_debug_flag_enables_verbose_logging_mode(self):
        self.assertTrue(parse_args(["--debug"]).debug)
        self.assertFalse(parse_args([]).debug)
if __name__ == "__main__":
    unittest.main()
