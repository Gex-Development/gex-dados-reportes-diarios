#!/usr/bin/env python3
"""Build yesterday's BuyGoods Master Accounts JSON from the public API (/transactions + /orders)."""

from __future__ import annotations

import argparse
import csv
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from loguru import logger

from src.common.report import BUYGOODS_TZ, LEDGER_FIELDS, account_metrics, finalize_report, money, write_report, yesterday

ROOT = Path(__file__).resolve().parents[2]
CREDENTIALS_PATH = ROOT / "credentials" / "buygoods_account_tokens.csv"
API_URL = "https://admin3.buygoods.com/public/v2"
# Cloudflare answers 403 "error code: 1010" without a browser User-Agent.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def load_accounts(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        accounts = list(csv.DictReader(csv_file))
    for line, account in enumerate(accounts, start=2):
        if not all((account.get(column) or "").strip() for column in ("account_id", "account_name", "token")):
            raise ValueError(f"{path} line {line} must define account_id, account_name and token")
    return accounts


def _get(endpoint: str, account: dict, params: dict) -> requests.Response:
    headers = {**HEADERS, "Authorization": f"Bearer {account['token']}"}
    for attempt in range(5):
        try:
            response = requests.get(f"{API_URL}/{endpoint}", headers=headers, params=params, timeout=120)
            if response.status_code not in (429, 500, 502, 503, 504):
                return response
        except (requests.ConnectionError, requests.Timeout):
            pass
        time.sleep(2**attempt)
    raise RuntimeError(f"{endpoint} kept failing after 5 attempts")


def fetch_all(endpoint: str, key: str, account: dict, **window: date) -> list[dict]:
    """window: start_date/end_date (creation, GMT-4) or updated_at_start/updated_at_end (last change, UTC)."""
    items: list[dict] = []
    while True:
        params = {
            "account_id": account["account_id"],
            **{name: day.isoformat() for name, day in window.items()},
            "limit": 500,
            "offset": len(items),
        }
        response = _get(endpoint, account, params)
        # /orders.php answers 404 once offset passes the total: end of pages, not an error.
        if response.status_code == 404 and items:
            return items
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success"):
            raise RuntimeError(f"{endpoint} error: {payload}")
        batch = payload.get(key) or []
        items.extend(batch)
        if not batch or len(items) >= payload.get("pagination", {}).get("total", 0):
            return items


def ledger_net_line(transactions: list[dict], report_date: date) -> dict | None:
    """The ledger closes day D in a "$... Net (...)" line posted on D+1 around 08:12 GMT-4."""
    posted = (report_date + timedelta(days=1)).isoformat()
    for transaction in transactions:
        if (transaction.get("product_notes") or "").startswith("$") and str(transaction.get("date"))[:10] == posted:
            return transaction
    return None


def count_orders(orders: list[dict], report_date: date) -> int:
    # shortcut: panel order count matched distinct user_id+sessid2 in 47/54 accounts on 2026-10-28;
    # the rest overcount by 1-2 (upsells right after midnight). Revisit if AOV/EPO drift matters.
    day = report_date.isoformat()
    return len(
        {
            (order.get("user_id"), order.get("sessid2"))
            for order in orders
            if str(order.get("rr_createdate"))[:10] == day
            and order.get("action_type") != "cancel"
            and str(order.get("is_test")) != "1"
        }
    )


def count_refunds(orders: list[dict], report_date: date) -> int:
    """Ledger refunds carry a $1 fee per refund issued that day; the panel leaves it out."""
    day = report_date.isoformat()
    # Dedupe by order id + item: the API repeats rows and reuses order ids across items.
    return len(
        {
            (order.get("order_id_global"), order.get("product_codename"))
            for order in orders
            if order.get("action_type") == "refund" and str(order.get("date_refunded"))[:10] == day
        }
    )


def extract_account(account: dict, report_date: date) -> tuple[bool, dict | None]:
    """Returns (ledger closed for the day, metrics or None when the account had no movement)."""
    name = account["account_name"].strip()
    try:
        transactions = fetch_all(
            "transactions.php",
            "transactions",
            account,
            start_date=report_date,
            end_date=report_date + timedelta(days=2),
        )
        net_line = ledger_net_line(transactions, report_date)
        if net_line is None:
            return False, None
        if not any(money(net_line.get(field)) for field in LEDGER_FIELDS):
            return True, None
        # /orders.php cuts the edges of a one-day window; ask one extra day each side and filter locally.
        orders = fetch_all(
            "orders.php",
            "orders",
            account,
            start_date=report_date - timedelta(days=1),
            end_date=report_date + timedelta(days=1),
        )
        refunds = []
        if money(net_line.get("refunds")):
            # updated_at_* filters in UTC while payload dates are GMT-4: pad the window, filter locally.
            # shortcut: a refund issued on D whose order changes again after D+2 drops out; matters for backfills only.
            refunds = fetch_all(
                "orders.php",
                "orders",
                account,
                updated_at_start=report_date - timedelta(days=1),
                updated_at_end=report_date + timedelta(days=2),
            )
    except Exception as error:
        raise RuntimeError(f"BuyGoods API failed for {name} ({account['account_id']}): {error}") from error
    order_count = count_orders(orders, report_date)
    refund_count = count_refunds(refunds, report_date)
    logger.debug("{}: {} orders, {} refunds", name, order_count, refund_count)
    return True, account_metrics(name, net_line, order_count, refund_count)


def report_path(root: Path, report_date: date) -> Path:
    return (
        root
        / "exports"
        / "buygoods"
        / "api"
        / f"{report_date.year:04d}"
        / f"{report_date.month:02d}"
        / f"master_accounts_{report_date.isoformat()}.json"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=ROOT, help="Root directory for exports (default: project root)")
    parser.add_argument("--date", type=date.fromisoformat, help="Report date YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--debug", action="store_true", help="Show per-account details")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logger.remove()
    logger.add(sys.stderr, level="DEBUG" if args.debug else "INFO", colorize=sys.stderr.isatty())
    report_date = args.date or yesterday(datetime.now(timezone.utc), BUYGOODS_TZ)
    output = report_path(args.output_root.resolve(), report_date)
    logger.info("Starting BuyGoods API extraction for {}", report_date)
    if output.exists():
        logger.info("JSON report already saved: {}", output)
        return 0

    accounts = load_accounts(CREDENTIALS_PATH)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda account: extract_account(account, report_date), accounts))

    if not any(closed for closed, _ in results):
        raise RuntimeError(f"Ledger has no Net line for {report_date} yet; BuyGoods posts it around 08:12 GMT-4 next day")
    metrics = [account for _, account in results if account]
    logger.info("{} of {} accounts had movement", len(metrics), len(accounts))
    write_report(finalize_report(metrics, report_date, "Buygoods", "api"), output)
    logger.info("Saved JSON report: {}", output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        logger.exception("BuyGoods API extraction failed")
        raise SystemExit(1) from error
