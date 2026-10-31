"""Daily report contract shared by every gateway and source: panel formula, schema check, atomic write."""

from __future__ import annotations

import json
import re
import tempfile
import unicodedata
from datetime import date, datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Iterable

import jsonschema
from jsonschema import FormatChecker

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "daily_report.schema.json"

# Ledger-shaped inputs (names from the BuyGoods /transactions.php "Net" line) that every source maps into.
LEDGER_FIELDS = (
    "sales",
    "fees",
    "refunds",
    "chargebacks",
    "commissions",
    "commissions_voids",
    "sale_taxes",
    "sale_tax_refunds",
    "shipping_handling",
)


def account_key(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    key = re.sub(r"[^a-z0-9]+", "_", ascii_name.lower()).strip("_")
    if not key:
        raise ValueError(f"Account name cannot produce a JSON key: {name!r}")
    return key


def money(value: object) -> float:
    return float(re.sub(r"[^0-9.\-]", "", str(value or "")) or 0)


# Each gateway closes its day in its own clock: BuyGoods fixed GMT-4 (no DST), PagAmerican UTC.
BUYGOODS_TZ = timezone(timedelta(hours=-4))
PAGAMERICAN_TZ = timezone.utc


def yesterday(now: datetime, tz: tzinfo) -> date:
    """Default report date: the last full day in the gateway's timezone, not the machine's."""
    return now.astimezone(tz).date() - timedelta(days=1)


def account_metrics(account_name: str, ledger_line: dict, order_count: int, refund_count: int) -> dict:
    """Panel formulas, checked against the 2026-10-28 export: Gross = sales - fees, Taxes net of refunds.

    refund_count removes the US$ 1 fee per refund that the API ledger embeds and the panel omits.
    """
    ledger = {field: money(ledger_line.get(field)) for field in LEDGER_FIELDS}
    gross = ledger["sales"] - ledger["fees"]
    refunds = ledger["refunds"] - refund_count
    taxes = ledger["sale_taxes"] - ledger["sale_tax_refunds"]
    net = gross - ledger["commissions"] - refunds - ledger["chargebacks"] - taxes + ledger["commissions_voids"]

    def per_order(value: float) -> float:
        return round(value / order_count, 2) if order_count else 0

    return {
        "account_name": account_name,
        "gross_sales": round(gross, 2),
        "shipping_and_handling": round(ledger["shipping_handling"], 2),
        "commissions": round(ledger["commissions"], 2),
        "refunds": round(refunds, 2),
        "chargebacks": round(ledger["chargebacks"], 2),
        "commission_voids": round(ledger["commissions_voids"], 2),
        "affiliate_epo": per_order(ledger["commissions"] - ledger["commissions_voids"]),
        "taxes": round(taxes, 2),
        "aov": per_order(gross),
        "epo": per_order(net),
        "net_sales": round(net, 2),
    }


def finalize_report(accounts: Iterable[dict], report_date: date, gateway: str, source: str) -> dict:
    keyed = {}
    for account in accounts:
        key = account_key(account["account_name"])
        if key in keyed:
            raise ValueError(
                f"Account slug collision for {keyed[key]['account_name']!r} and {account['account_name']!r}: {key}"
            )
        keyed[key] = account

    report = {
        "gateway": gateway,
        "report_date": report_date.isoformat(),
        "currency": "USD",
        "source": source,
        "contas": keyed,
    }
    with SCHEMA_PATH.open(encoding="utf-8") as schema_file:
        schema = json.load(schema_file)
    jsonschema.validate(report, schema, format_checker=FormatChecker())
    return report


def write_report(report: dict, output: Path) -> None:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing JSON report: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".part",
            delete=False,
        ) as json_file:
            temporary = Path(json_file.name)
            json.dump(report, json_file, ensure_ascii=False, indent=2, allow_nan=False)
            json_file.write("\n")
        temporary.replace(output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
