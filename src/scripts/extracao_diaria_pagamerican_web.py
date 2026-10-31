#!/usr/bin/env python3
"""Download yesterday's PagAmerican full report (all datasets, Excel) from the business panel.

Logs in with PAGAMERICAN_LOGIN / PAGAMERICAN_PASSWORD from .env; the session stays in ~/.pagamerican-profile.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from dotenv import dotenv_values
from loguru import logger
from openpyxl import load_workbook
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from src.common.report import PAGAMERICAN_TZ, yesterday
from src.transformations.pagamerican_report import transform_file

ROOT = Path(__file__).resolve().parents[2]
REPORTS_URL = "https://business.pagamerican.app/reports"
LOGIN_URL = "https://business.pagamerican.app/login"
EXPORTS_API = "**/api/v1/exports"
# Session cookies live outside the project so they are never committed.
PROFILE_DIR = Path.home() / ".pagamerican-profile"
DATASETS = [
    "Purchases",
    "Orders",
    "Refunds & Chargebacks",
    "Order Fulfillment",
    "Abandoned Carts",
    "Payouts",
]


def export_path(root: Path, data_date: date) -> Path:
    return (
        root
        / "exports"
        / "pagamerican"
        / "web"
        / f"{data_date.year:04d}"
        / f"{data_date.month:02d}"
        / f"pagamerican_{data_date.isoformat()}.xlsx"
    )


def export_filters(data_date: date) -> dict:
    """UTC day D. The panel sends Yesterday as D 03:00Z..D+1 02:59Z, but the backend keeps only the
    date part of each bound and exports D and D+1 whole (seen on 2026-10-29), so pin both to D."""
    return {"startDate": f"{data_date.isoformat()}T00:00:00.000Z", "endDate": f"{data_date.isoformat()}T23:59:59.999Z"}


def chip_is_selected(chip) -> bool:
    """Clicking an active chip deselects it, so detect state first (aria/data-state/class)."""
    for attr in ("aria-pressed", "aria-checked", "aria-selected"):
        if (chip.get_attribute(attr) or "").lower() == "true":
            return True
    state = (chip.get_attribute("data-state") or "").lower()
    if state in ("on", "checked", "active", "selected"):
        return True
    cls = (chip.get_attribute("class") or "").lower()
    return any(k in cls for k in ("selected", "active", "checked"))


def select_datasets(page) -> None:
    for name in DATASETS:
        chip = page.get_by_role("button", name=name, exact=True)
        if chip.count() == 0:
            chip = page.get_by_text(name, exact=True)
        chip = chip.first
        chip.wait_for(state="visible", timeout=15_000)
        if chip_is_selected(chip):
            logger.debug("Dataset already selected: {}", name)
        else:
            chip.click()
            logger.debug("Dataset selected: {}", name)


def select_period(page) -> None:
    # Only enables "Generate report": the panel's "Yesterday" follows the browser timezone, so the
    # real period is pinned to UTC day D in the export request (pin_period) and checked after download.
    page.get_by_role("button", name="Select period").click()
    page.get_by_role("dialog").get_by_role("button", name="Yesterday", exact=True).click()


def check_period(path: Path, data_date: date) -> None:
    workbook = load_workbook(path, read_only=True)
    try:
        if "Purchases" not in workbook.sheetnames:
            return  # no sales that day: nothing to check
        header, *rows = workbook["Purchases"].iter_rows(values_only=True)
        # The panel picks orders by checkout day: a checkout opened at 23:53 and paid at 00:02 belongs to D.
        column = header.index("Checkout Initialized At")
        days = {row[column].date() for row in rows if row[column] is not None}
    finally:
        workbook.close()
    if days - {data_date}:
        raise ValueError(f"PagAmerican export for {data_date} has checkouts on {', '.join(map(str, sorted(days)))}")


def select_excel(page) -> None:
    excel = page.get_by_role("radio", name="Excel (.xlsx)")
    if excel.get_attribute("aria-checked") != "true":
        excel.click()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root", type=Path, default=ROOT, help="Root directory for exports (default: project root)"
    )
    parser.add_argument("--headed", action="store_true", help="Show the browser (needed for the first login)")
    parser.add_argument("--debug", action="store_true", help="Show detailed browser steps")
    parser.add_argument(
        "--date", type=date.fromisoformat, help="Report date YYYY-MM-DD, UTC day (default: yesterday UTC)"
    )
    return parser.parse_args(argv)


def download_report(target: Path, data_date: date, args: argparse.Namespace) -> None:
    config = dotenv_values(ROOT / ".env")
    login, password = config.get("PAGAMERICAN_LOGIN"), config.get("PAGAMERICAN_PASSWORD")

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(PROFILE_DIR), channel="chrome", headless=not args.headed, accept_downloads=True
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(REPORTS_URL, wait_until="networkidle")
            # Logged out, the panel stays on /reports and only shows "Session expired. Please log in again."
            reports_ready = page.get_by_role("button", name="Generate report")
            if not reports_ready.count():
                if login and password:
                    logger.info("PagAmerican session expired; logging in")
                    page.goto(LOGIN_URL, wait_until="networkidle")
                    page.locator('input[type="email"]').fill(login)
                    page.locator('input[type="password"]').fill(password)
                    page.get_by_role("button", name="Sign In", exact=True).click()
                    page.wait_for_url(lambda url: "/login" not in url, timeout=30_000)
                    page.goto(REPORTS_URL, wait_until="networkidle")
                    reports_ready.wait_for(state="visible", timeout=30_000)
                elif args.headed:
                    logger.info("Log in on the browser window and open Reports; waiting up to 5 minutes")
                    reports_ready.wait_for(state="visible", timeout=300_000)
                else:
                    raise RuntimeError(
                        "PagAmerican session expired: set PAGAMERICAN_LOGIN/PAGAMERICAN_PASSWORD in .env "
                        "or run `make pagamerican HEADED=1` and log in"
                    )

            select_datasets(page)
            select_period(page)
            select_excel(page)

            sent = []

            def pin_period(route) -> None:
                if route.request.method != "POST":
                    route.continue_()
                    return
                body = json.loads(route.request.post_data)
                body["filters"] = {**body.get("filters", {}), **export_filters(data_date)}
                sent.append(body)
                route.continue_(post_data=json.dumps(body))

            page.route(EXPORTS_API, pin_period)
            logger.info("Generating report")
            page.get_by_role("button", name="Generate report").click()
            try:
                page.get_by_text("Loading...").wait_for(state="visible", timeout=5_000)
            except PlaywrightTimeoutError:
                pass
            page.get_by_text("Loading...").wait_for(state="hidden", timeout=300_000)
            if len(sent) != 1:
                raise RuntimeError(f"Expected one export request to pin the period, saw {len(sent)}")
            logger.debug("Export request: {}", sent[0])

            with page.expect_download(timeout=120_000) as download_info:
                page.get_by_role("button", name="Download XLSX").or_(page.get_by_text("Download XLSX")).first.click()
            target.parent.mkdir(parents=True, exist_ok=True)
            # openpyxl only opens files ending in .xlsx, so keep the suffix on the partial download.
            temporary = target.with_name(f".{target.stem}.part{target.suffix}")
            try:
                download_info.value.save_as(temporary)
                check_period(temporary, data_date)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
            logger.info("Saved export: {}", target)
        finally:
            context.close()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logger.remove()
    logger.add(sys.stderr, level="DEBUG" if args.debug else "INFO", colorize=sys.stderr.isatty())
    data_date = args.date or yesterday(datetime.now(UTC), PAGAMERICAN_TZ)
    target = export_path(args.output_root.resolve(), data_date)
    logger.info("Starting PagAmerican export for {}", data_date)
    if target.exists():
        logger.info("Export already saved: {}", target)
    else:
        download_report(target, data_date, args)

    json_path = target.with_suffix(".json")
    if json_path.exists():
        logger.info("JSON report already saved: {}", json_path)
        return 0
    transform_file(target, json_path, data_date)
    logger.info("Saved JSON report: {}", json_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        logger.exception("PagAmerican export failed")
        raise SystemExit(1) from error
