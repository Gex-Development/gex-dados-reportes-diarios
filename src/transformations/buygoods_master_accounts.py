"""Transform BuyGoods Master Accounts spreadsheets into the daily JSON contract."""

from __future__ import annotations

import html
import math
from datetime import date
from pathlib import Path
from typing import Iterable

from src.common.report import finalize_report, write_report

COLUMN_MAP = {
    "Account": "account_name",
    "Gross Sales": "gross_sales",
    "S&H": "shipping_and_handling",
    "Commissions": "commissions",
    "Refunds": "refunds",
    "Chargebacks": "chargebacks",
    "Commission Voids": "commission_voids",
    "Affiliate EPO": "affiliate_epo",
    "Taxes": "taxes",
    "AOV": "aov",
    "EPO": "epo",
    "Net Sales": "net_sales",
}


def _numeric_value(value: object, source_column: str, row_number: int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{source_column} must be a finite number at spreadsheet row {row_number}")
    return value


def build_report(headers: Iterable[object], rows: Iterable[Iterable[object]], report_date: date) -> dict:
    header_indexes = {str(header).strip(): index for index, header in enumerate(headers)}
    missing = set(COLUMN_MAP) - header_indexes.keys()
    if missing:
        raise ValueError(f"Missing BuyGoods columns: {', '.join(sorted(missing))}")

    accounts = []
    for row_number, row in enumerate(rows, start=1):
        values = list(row)
        account_index = header_indexes["Account"]
        account_value = values[account_index] if account_index < len(values) else None
        if all(value is None or value == "" for value in values):
            continue
        if not isinstance(account_value, str) or not account_value.strip():
            raise ValueError(f"Account name is missing at spreadsheet data row {row_number}")
        # BuyGoods exports HTML entities in names, e.g. "Men&#039;s Growth".
        account_name = html.unescape(account_value.strip())
        if account_name.casefold() == "total":
            continue

        account = {"account_name": account_name}
        for source_column, property_name in COLUMN_MAP.items():
            if source_column == "Account":
                continue
            index = header_indexes[source_column]
            value = values[index] if index < len(values) else None
            account[property_name] = _numeric_value(value, source_column, row_number)
        # Visitors-only rows are all zero once Visitors is dropped; the API omits them too.
        if any(value for key, value in account.items() if key != "account_name"):
            accounts.append(account)

    return finalize_report(accounts, report_date, "Buygoods", "web")


def _spreadsheet_rows(source: Path) -> list[list[object]]:
    if source.suffix.lower() == ".xls":
        import xlrd

        workbook = xlrd.open_workbook(source, on_demand=True)
        try:
            sheet = workbook.sheet_by_index(0)
            return [[sheet.cell_value(row, column) for column in range(sheet.ncols)] for row in range(sheet.nrows)]
        finally:
            workbook.release_resources()
    if source.suffix.lower() == ".xlsx":
        from openpyxl import load_workbook

        workbook = load_workbook(source, read_only=True, data_only=True)
        try:
            return [list(row) for row in workbook.active.iter_rows(values_only=True)]
        finally:
            workbook.close()
    raise ValueError(f"Unsupported BuyGoods spreadsheet extension: {source.suffix}")


def transform_file(source: Path, output: Path, report_date: date) -> dict:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing JSON report: {output}")

    spreadsheet_rows = _spreadsheet_rows(source)
    header_index = next(
        (
            index
            for index, row in enumerate(spreadsheet_rows)
            if set(COLUMN_MAP).issubset({str(value).strip() for value in row})
        ),
        None,
    )
    if header_index is None:
        raise ValueError("Could not find the BuyGoods Master Accounts header row")

    report = build_report(spreadsheet_rows[header_index], spreadsheet_rows[header_index + 1 :], report_date)
    write_report(report, output)
    return report
