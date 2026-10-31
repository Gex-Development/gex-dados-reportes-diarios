"""Transform the PagAmerican Excel report into the daily JSON contract, one account per front product."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path

from openpyxl import load_workbook

from src.common.report import account_metrics, finalize_report, write_report


def _sheet_rows(workbook, name: str) -> list[dict]:
    # The panel omits the sheet of a dataset with no rows in the period (e.g. no refunds that day).
    if name not in workbook.sheetnames:
        return []
    header, *rows = workbook[name].iter_rows(values_only=True)
    return [dict(zip(header, row)) for row in rows if any(value is not None for value in row)]


def build_report(workbook, report_date: date) -> dict:
    front_product = {
        row["Order ID"]: row["Product Name"].strip()
        for row in _sheet_rows(workbook, "Purchases")
        if row["Purchase Type"] == "Initial"
    }
    # Same ledger-shaped fields as BuyGoods, so the panel formula is shared:
    # Net = (amount - platform fee) - affiliation - refunds - chargebacks - creator tax, which matches
    # the OnePager NET REVENUE of the 2026-10-29 export to the cent.
    ledgers: dict[str, dict] = defaultdict(lambda: defaultdict(float))
    order_counts: dict[str, int] = defaultdict(int)
    for row in _sheet_rows(workbook, "Orders"):
        if row["Order ID"] not in front_product:
            raise ValueError(f"PagAmerican order {row['Order ID']} has no Initial purchase to name its product")
        ledger = ledgers[front_product[row["Order ID"]]]
        ledger["sales"] += row["Order Amount"] or 0
        ledger["fees"] += row["Creator Platform Fee"] or 0
        ledger["sale_taxes"] += row["Creator Tax"] or 0
        ledger["commissions"] += row["Affiliation Amount"] or 0
        order_counts[front_product[row["Order ID"]]] += 1
    # Refunds/chargebacks of the period's orders, whatever their refund date (export semantics).
    for row in _sheet_rows(workbook, "Refunds&Chargebacks"):
        ledger = ledgers[front_product.get(row["Order ID"]) or row["Product Name"].strip()]
        ledger["refunds"] += abs(row["Refundamount"] or 0)
        ledger["chargebacks"] += abs(row["chargebackamount"] or 0)

    accounts = [account_metrics(name, ledger, order_counts[name], 0) for name, ledger in sorted(ledgers.items())]
    return finalize_report(accounts, report_date, "Pagamerican", "web")


def transform_file(source: Path, output: Path, report_date: date) -> dict:
    workbook = load_workbook(source, read_only=True, data_only=True)
    try:
        report = build_report(workbook, report_date)
    finally:
        workbook.close()
    write_report(report, output)
    return report
