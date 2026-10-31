#!/usr/bin/env python3
"""Build the daily PagAmerican JSON from read-only Data API v1 endpoints."""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv
from loguru import logger

from src.common.report import PAGAMERICAN_TZ, account_metrics, finalize_report, write_report, yesterday

ROOT = Path(__file__).resolve().parents[2]
BASE_URL = "https://external-api-service.pagamerican.app/api/v1"
LIMIT = 5000
IDS = {"orders": "orderId", "purchases": "purchaseId", "refunds": "refundRequestId", "chargebacks": "refundRequestId"}


def dedupe_page(rows: list[dict], id_field: str) -> list[dict]:
    seen = set()
    result = []
    for row in rows:
        identifier = row.get(id_field)
        if identifier is None:
            raise ValueError(f"INCOMPLETE API response: missing {id_field}")
        if identifier in seen:
            raise ValueError(f"INCOMPLETE API response: duplicate {id_field} at page boundary")
        seen.add(identifier)
        result.append(row)
    return result


class PagAmericanClient:
    def __init__(self, api_key: str):
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {api_key}", "Accept": "application/json"})

    def fetch(self, route: str, start: date, end: date) -> list[dict]:
        result = []
        day = start
        while day < end:
            page = 1
            rows = []
            while True:
                params = {
                    "from": day.isoformat(),
                    "to": (day + timedelta(days=1)).isoformat(),
                    "limit": LIMIT,
                    "page": page,
                }
                response = self.session.get(f"{BASE_URL}/{route}", params=params, timeout=60)
                if response.status_code == 429:
                    time.sleep(int(response.headers.get("Retry-After", "60")))
                    response = self.session.get(f"{BASE_URL}/{route}", params=params, timeout=60)
                if response.status_code != 200:
                    raise RuntimeError(
                        f"PagAmerican /{route} HTTP {response.status_code} for {day}; report not written"
                    )
                batch = response.json()["data"]
                rows.extend(batch)
                time.sleep(1.05)  # API limit: 60 requests/minute.
                if len(batch) < LIMIT:
                    break
                page += 1
            result.extend(dedupe_page(rows, IDS[route]))
            logger.info("/{}, {}: {} rows", route, day, len(rows))
            day += timedelta(days=1)
        return result


def build_report(
    orders: list[dict], purchases: list[dict], refunds: list[dict], chargebacks: list[dict], report_date: date
) -> dict:
    front_product = {}
    for purchase in purchases:
        if purchase["purchaseType"] != "front":
            continue
        product = purchase.get("productName")
        if not isinstance(product, str) or not product.strip():
            raise ValueError(f"PagAmerican order {purchase['orderId']} has no product on front purchase")
        order_id = str(purchase["orderId"])
        if order_id in front_product and front_product[order_id] != product.strip():
            raise ValueError(f"PagAmerican order {order_id} has conflicting front products")
        front_product[order_id] = product.strip()

    ledgers = defaultdict(lambda: defaultdict(float))
    counts = defaultdict(int)
    relevant_orders = set()
    for order in orders:
        if not order["checkoutInitializedAt"].startswith(report_date.isoformat()):
            continue
        order_id = str(order["orderId"])
        if order_id not in front_product:
            raise ValueError(f"PagAmerican order {order_id} has no front purchase")
        name = front_product[order_id]
        relevant_orders.add(order_id)
        ledger = ledgers[name]
        for field, api_field in (
            ("sales", "amountTransaction"),
            ("fees", "amountCreatorPlatformFee"),
            ("sale_taxes", "amountCreatorTax"),
            ("commissions", "amountAffiliation"),
        ):
            ledger[field] += order[api_field] or 0
        counts[name] += 1

    # Events are fetched from D through today, then joined to D's orders; never limit by event date D.
    for event in refunds:
        order_id = str(event["orderId"])
        if order_id in relevant_orders and event.get("refundSource") != "alerta":
            ledgers[front_product[order_id]]["refunds"] += abs(event["amountRefundedTotal"])
    for event in chargebacks:
        order_id = str(event["orderId"])
        if order_id in relevant_orders:
            ledgers[front_product[order_id]]["chargebacks"] += abs(event["amountRefundedTotal"])

    accounts = [account_metrics(name, ledger, counts[name], 0) for name, ledger in sorted(ledgers.items())]
    return finalize_report(accounts, report_date, "Pagamerican", "api")


def report_path(root: Path, report_date: date) -> Path:
    return (
        root
        / "exports"
        / "pagamerican"
        / "api"
        / f"{report_date.year:04d}"
        / f"{report_date.month:02d}"
        / f"pagamerican_{report_date}.json"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=date.fromisoformat, help="UTC report date, YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--output-root", type=Path, default=ROOT)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)
    logger.remove()
    logger.add(sys.stderr, level="DEBUG" if args.debug else "INFO")
    now = datetime.now(UTC)
    report_date = args.date or yesterday(now, PAGAMERICAN_TZ)
    output = report_path(args.output_root, report_date)
    if output.exists():
        logger.info("JSON report already saved: {}", output)
        return 0
    load_dotenv(ROOT / ".env", override=False)
    api_key = os.getenv("PAGAMERICAN_API_KEY")
    if not api_key:
        raise RuntimeError("PAGAMERICAN_API_KEY is missing from environment or .env")
    client = PagAmericanClient(api_key)
    # shortcut: D..D+1 catches observed midnight spillover; extend if checkouts can convert >1 day later.
    # API date window uses orderCreatedAt, while the panel selects checkoutInitializedAt.
    orders = client.fetch("orders", report_date, report_date + timedelta(days=2))
    purchases = client.fetch("purchases", report_date - timedelta(days=1), report_date + timedelta(days=2))
    event_end = max(now.date(), report_date) + timedelta(days=1)
    refunds = client.fetch("refunds", report_date, event_end)
    chargebacks = client.fetch("chargebacks", report_date, event_end)
    report = build_report(orders, purchases, refunds, chargebacks, report_date)
    write_report(report, output)
    logger.info("Saved JSON report: {}", output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        logger.error("PagAmerican API extraction failed: {}", error)
        raise SystemExit(1) from None
