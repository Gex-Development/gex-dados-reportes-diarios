#!/usr/bin/env python3
"""Create or download a day's BuyGoods Master Accounts export (default: yesterday, GMT-4)."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import dotenv_values
from loguru import logger
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from src.common.report import BUYGOODS_TZ, yesterday
from src.transformations.buygoods_master_accounts import transform_file

ROOT = Path(__file__).resolve().parents[2]
ADMIN_URL = "https://admin.buygoods.com/"
MASTER_ACCOUNTS_URL = f"{ADMIN_URL}#master-accounts"
EXPORTS_URL = f"{ADMIN_URL}#exports"


def report_title(data_date: date) -> str:
    return f"Master Accounts - {data_date.isoformat()}"


def export_filename(data_date: date, extension: str) -> str:
    extension = extension.lower()
    if extension not in {".xls", ".xlsx"}:
        raise ValueError(f"Unsupported BuyGoods export extension: {extension}")
    return f"master_accounts_{data_date.isoformat()}{extension}"


def export_path(root: Path, data_date: date, extension: str) -> Path:
    return (
        root
        / "exports"
        / "buygoods"
        / "web"
        / f"{data_date.year:04d}"
        / f"{data_date.month:02d}"
        / export_filename(data_date, extension)
    )


def existing_local_export(root: Path, data_date: date) -> Path | None:
    folder = export_path(root, data_date, ".xls").parent
    matches = sorted(
        path
        for path in folder.glob(f"master_accounts_{data_date.isoformat()}.*")
        if path.suffix.lower() in {".xls", ".xlsx"}
    )
    return matches[0] if matches else None


def configure_day(page, data_date: date) -> None:
    logger.debug("Selecting Master Accounts date: {}", data_date)
    page.goto(MASTER_ACCOUNTS_URL, wait_until="domcontentloaded")
    date_button = page.locator("button.dropdown-toggle:visible").filter(
        has_text=re.compile(r"\d{1,2}, \d{4}.*-.*\d{1,2}, \d{4}")
    )
    date_button.first.wait_for(state="visible", timeout=30_000)
    if date_button.count() != 1:
        raise RuntimeError("Could not identify the Master Accounts date range control")

    date_button.click()
    picker = page.locator(".daterangepicker:visible")
    picker.locator('li[data-range-key="Custom Range"]').click()
    calendar = picker.locator(".drp-calendar.left")
    calendar.locator("select.yearselect").select_option(str(data_date.year))
    calendar.locator("select.monthselect").select_option(str(data_date.month - 1))  # 0-based months
    day = calendar.locator("td.available:not(.off)").filter(has_text=re.compile(rf"^{data_date.day}$"))
    day.click()  # range start
    day.click()  # range end: same day
    picker.get_by_role("button", name="Apply").click()
    expected = f"{data_date:%b} {data_date.day}, {data_date.year} - {data_date:%b} {data_date.day}, {data_date.year}"
    page.wait_for_function(
        "(expected) => [...document.querySelectorAll('button.dropdown-toggle')]"
        ".some(button => button.offsetParent !== null && button.innerText.includes(expected))",
        arg=expected,
        timeout=15_000,
    )
    logger.debug("BuyGoods date filter set to {}", expected)


def existing_export_link(page, title: str, data_date: date):
    logger.debug("Searching BuyGoods exports for report: {}", title)
    page.goto(EXPORTS_URL, wait_until="domcontentloaded")
    link = page.get_by_role("link", name=title, exact=True).first
    try:
        link.wait_for(state="visible", timeout=8_000)
    except PlaywrightTimeoutError:
        return None

    row = link.locator("xpath=ancestor::tr[1]")
    expected_day = f"{data_date.strftime('%B')} {data_date.day}, {data_date.year}"
    logger.debug("Found existing report for requested date")
    return link if expected_day in row.inner_text() else None



def export_action(page):
    return page.locator('a[action="export"]:visible').last


def add_selected_action(dialog):
    return dialog.locator('a[action="add"]:visible')

def create_export(page, title: str) -> None:
    logger.debug("Creating export form for {}", title)
    page.goto(MASTER_ACCOUNTS_URL, wait_until="domcontentloaded")
    export_action(page).click()
    dialog = page.get_by_role("dialog").filter(has_text="Export Master Accounts")
    dialog.wait_for(state="visible")
    dialog.locator("#report_title").fill(title)

    for batch in range(20):
        logger.debug("Selecting all available columns, batch {}", batch + 1)
        no_available_columns = dialog.get_by_text("No data available in table", exact=True)
        if no_available_columns.count() and no_available_columns.is_visible():
            break

        available_table = dialog.locator('table[id^="table_SPI_Table"]:visible').last
        before = available_table.inner_text().strip()
        select_all = dialog.locator('input[id^="checkall_SPI_Table"]').last
        if not before or not select_all.count():
            raise RuntimeError("Could not identify available Master Accounts columns")

        select_all.check()
        add_selected_action(dialog).click()
        page.wait_for_function(
            "before => {"
            " const tables = [...document.querySelectorAll('table[id^=\"table_SPI_Table\"]')]"
            "   .filter(table => table.offsetParent !== null);"
            " return tables.length && tables.at(-1).innerText.trim() !== before;"
            "}",
            arg=before,
            timeout=15_000,
        )
    else:
        raise RuntimeError("Available columns did not drain after 20 Add Selected cycles")

    if not no_available_columns.is_visible():
        raise RuntimeError("Not all available columns were added to the export")

    logger.debug("Submitting export request: {}", title)
    dialog.get_by_role("button", name="Create Export", exact=True).click()
    page.wait_for_url("**/#exports", timeout=60_000)


def save_download(page, link, root: Path, data_date: date) -> Path:
    with page.expect_download(timeout=60_000) as download_info:
        link.click()
    download = download_info.value
    logger.debug("BuyGoods download filename: {}", download.suggested_filename)
    target = export_path(root, data_date, Path(download.suggested_filename).suffix)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite existing export: {target}")

    temporary = target.with_name(f".{target.name}.part")
    try:
        download.save_as(temporary)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT,
        help="Root directory for exports (default: project root)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show detailed browser and export steps",
    )
    parser.add_argument("--date", type=date.fromisoformat, help="Report date YYYY-MM-DD, GMT-4 day (default: yesterday)")
    return parser.parse_args(argv)


def configure_logging(debug: bool) -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG" if debug else "INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        colorize=sys.stderr.isatty(),
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.debug)
    root = args.output_root.resolve()
    data_date = args.date or yesterday(datetime.now(timezone.utc), BUYGOODS_TZ)
    title = report_title(data_date)
    logger.info("Starting BuyGoods export for {}", data_date)

    saved = existing_local_export(root, data_date)
    if saved:
        logger.info("Export already saved: {}", saved)
    else:
        config = dotenv_values(ROOT / ".env")
        login = config.get("BUYGOODS_LOGIN")
        password = config.get("BUYGOODS_PASSWORD")
        login_url = config.get("BUYGOODS_URL_CONTA_2")
        if not all((login, password, login_url)):
            raise RuntimeError(".env must define BUYGOODS_LOGIN, BUYGOODS_PASSWORD and BUYGOODS_URL_CONTA_2")

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            try:
                page = browser.new_page(accept_downloads=True)
                logger.debug("Opening BuyGoods login page")
                page.goto(login_url, wait_until="domcontentloaded")
                email = page.get_by_label("Email Address")
                if email.count() and email.is_visible():
                    logger.debug("Submitting login credentials")
                    email.fill(login)
                    page.get_by_label("Password").fill(password)
                    page.get_by_role("button", name="Continue", exact=True).click()
                    page.wait_for_function(
                        "location.hostname === 'admin.buygoods.com' && !location.pathname.endsWith('/login')",
                        timeout=30_000,
                    )
                    logger.debug("BuyGoods login completed")

                configure_day(page, data_date)
                link = existing_export_link(page, title, data_date)
                if link is None:
                    logger.info("No existing export; creating {}", title)
                    create_export(page, title)
                    # The export takes the panel's current range; confirm it really covers the requested day.
                    link = existing_export_link(page, title, data_date)
                    if link is None:
                        raise RuntimeError(f"Created export {title!r} does not cover {data_date}")
                else:
                    logger.info("Reusing existing BuyGoods export: {}", title)

                logger.debug("Downloading report")
                saved = save_download(page, link, root, data_date)
                logger.info("Saved export: {}", saved)
            finally:
                browser.close()

    json_path = saved.with_suffix(".json")
    if json_path.exists():
        logger.info("JSON report already saved: {}", json_path)
        return 0

    transform_file(saved, json_path, data_date)
    logger.info("Saved JSON report: {}", json_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        logger.exception("BuyGoods export failed")
        raise SystemExit(1) from error
