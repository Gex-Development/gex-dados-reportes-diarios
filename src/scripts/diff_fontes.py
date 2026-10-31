#!/usr/bin/env python3
"""Compare a gateway's daily JSONs (api, lake) against the web panel and write the AI and dashboard diffs."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import jsonschema
from jsonschema import FormatChecker
from loguru import logger

from src.common.report import BUYGOODS_TZ, PAGAMERICAN_TZ, write_report, yesterday

ROOT = Path(__file__).resolve().parents[2]
BASE = "web"
SOURCES = ("web", "api", "lake")
TOLERANCE = 0.01
FIELDS = (
    "gross_sales",
    "shipping_and_handling",
    "commissions",
    "refunds",
    "chargebacks",
    "commission_voids",
    "affiliate_epo",
    "taxes",
    "aov",
    "epo",
    "net_sales",
)
GATEWAYS = {
    "buygoods": ("Buygoods", "master_accounts"),
    "pagamerican": ("Pagamerican", "pagamerican"),
}
# Known, documented differences, so a reader does not mistake them for defects (README / docs/guia.md).
CONTEXT = {
    "Buygoods": {
        "web": "Painel Master Accounts; dia GMT-4.",
        "api": "Ledger /transactions (linha Net de D, publicada ~08:12 GMT-4 de D+1) + /orders; dia GMT-4. "
        "Refunds pela data do reembolso, sem a taxa de US$ 1. Pedidos = sessões user_id+sessid2 (até +2 vs painel). "
        "Traz contas secundárias que o login do painel não mostra.",
        "lake": "Canônico silver (Athena); dia GMT-4. Refunds batem com /orders e ficam abaixo do painel; "
        "IVA de refund estimado; commission_voids aproximado pela comissão dos chargebacks; "
        "S&H = frete cobrado (informativo); pedidos = clientes distintos.",
    },
    "Pagamerican": {
        "web": "Export do painel; dia UTC; refunds/chargebacks dos pedidos do dia, qualquer data de evento; alerta conta como chargeback.",
        "api": "Data API v1; pedido no dia da abertura do checkout (UTC); mesma semântica do painel.",
        "lake": "Canônico silver em onboarding (sem aceite); dia pela data da venda (UTC), não pelo checkout: "
        "pedido na virada do dia muda de dia. S&H = frete cobrado (informativo).",
    },
}


def _equal(a: float, b: float) -> bool:
    return round(abs(a - b), 2) <= TOLERANCE


def _status(account: str, base: dict, other: dict) -> str:
    if account not in other:
        return "faltando_na_fonte"
    if account not in base:
        return "extra_na_fonte"
    return "igual" if all(_equal(base[account][f], other[account][f]) for f in FIELDS) else "divergente"


def build_diff(gateway: str, report_date: date, reports: dict, paths: dict) -> tuple[dict, list[dict]]:
    base = reports[BASE]["contas"]
    compared = [source for source in SOURCES if source != BASE and reports.get(source)]
    contas = {source: reports[source]["contas"] for source in [BASE, *compared]}

    summary, rows, ai_accounts = {}, [], {}
    for source in compared:
        other = contas[source]
        both = sorted(base.keys() & other.keys())
        fields = {}
        for field in FIELDS:
            equal = sum(_equal(base[k][field], other[k][field]) for k in both)
            total_base = round(sum(base[k][field] for k in both), 2)
            total_source = round(sum(other[k][field] for k in both), 2)
            fields[field] = {
                "iguais": equal,
                "divergentes": len(both) - equal,
                "total_base": total_base,
                "total_fonte": total_source,
                "delta": round(total_source - total_base, 2),
            }
        summary[source] = {
            "contas_comparadas": len(both),
            "contas_iguais": sum(_status(k, base, other) == "igual" for k in both),
            "faltando_na_fonte": sorted(base.keys() - other.keys()),
            "extra_na_fonte": sorted(other.keys() - base.keys()),
            "campos": fields,
        }

        for key in sorted(base.keys() | other.keys()):
            status = _status(key, base, other)
            name = (base.get(key) or other[key])["account_name"]
            for field in FIELDS:
                value = other[key][field] if key in other else None
                value_base = base[key][field] if key in base else None
                delta = None if value is None or value_base is None else round(value - value_base, 2)
                rows.append(
                    {
                        "gateway": gateway,
                        "report_date": report_date.isoformat(),
                        "conta": key,
                        "account_name": name,
                        "campo": field,
                        "fonte": source,
                        "base": BASE,
                        "valor": value,
                        "valor_base": value_base,
                        "delta": delta,
                        "delta_pct": round(delta / abs(value_base) * 100, 2) if delta is not None and value_base else None,
                        "status": status if status != "divergente" or not _equal(value, value_base) else "igual",
                    }
                )
            if status != "igual":
                ai_accounts.setdefault(key, {"account_name": name, "status": {}, "campos": {}})["status"][source] = status

    for key, entry in ai_accounts.items():
        for field in FIELDS:
            values = {source: contas[source][key][field] if key in contas[source] else None for source in contas}
            present = [v for v in values.values() if v is not None]
            # Divergent: values disagree; absent somewhere: show only what is non-zero where it exists.
            if any(not _equal(present[0], v) for v in present) or (len(present) < len(values) and any(present)):
                entry["campos"][field] = values

    ai = {
        "gateway": gateway,
        "report_date": report_date.isoformat(),
        "currency": "USD",
        "base": BASE,
        "tolerancia": TOLERANCE,
        "fontes": {source: paths.get(source) for source in SOURCES},
        "contexto": {source: CONTEXT[gateway][source] for source in contas},
        "resumo": summary,
        "contas": dict(sorted(ai_accounts.items())),
    }
    return ai, rows


def _validate(document, schema_name: str) -> None:
    schema = json.loads((ROOT / "schemas" / schema_name).read_text(encoding="utf-8"))
    jsonschema.validate(document, schema, format_checker=FormatChecker())


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gateway", choices=sorted(GATEWAYS), help="Gateway to compare")
    parser.add_argument("--date", type=date.fromisoformat, help="Report date YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--output-root", type=Path, default=ROOT, help="Root directory for exports (default: project root)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logger.remove()
    logger.add(sys.stderr, level="INFO", colorize=sys.stderr.isatty())
    gateway, prefix = GATEWAYS[args.gateway]
    report_date = args.date or yesterday(datetime.now(timezone.utc), BUYGOODS_TZ if gateway == "Buygoods" else PAGAMERICAN_TZ)
    root = args.output_root.resolve()
    month = Path(f"{report_date.year:04d}") / f"{report_date.month:02d}"

    reports, paths = {}, {}
    for source in SOURCES:
        path = root / "exports" / args.gateway / source / month / f"{prefix}_{report_date.isoformat()}.json"
        paths[source] = str(path.relative_to(root)) if path.exists() else None
        reports[source] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    if reports[BASE] is None:
        raise RuntimeError(f"No {BASE} JSON for {gateway} {report_date}; it is the diff base")
    if not any(reports[source] for source in SOURCES if source != BASE):
        raise RuntimeError(f"No api or lake JSON for {gateway} {report_date} to compare with {BASE}")

    ai, rows = build_diff(gateway, report_date, reports, paths)
    _validate(ai, "diff_ai.schema.json")
    _validate(rows, "diff_dashboard.schema.json")
    out_dir = root / "exports" / args.gateway / "diff" / month
    for name, document in (("diff_ai", ai), ("diff_dashboard", rows)):
        output = out_dir / f"{name}_{report_date.isoformat()}.json"
        # Derived from the source JSONs, so rebuilding (e.g. after the lake lands) is safe.
        output.unlink(missing_ok=True)
        write_report(document, output)
        logger.info("Saved {}", output)
    for source, item in ai["resumo"].items():
        logger.info(
            "{} vs {}: {}/{} contas iguais, {} faltando, {} extras",
            source, BASE, item["contas_iguais"], item["contas_comparadas"],
            len(item["faltando_na_fonte"]), len(item["extra_na_fonte"]),
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        logger.exception("Diff failed")
        raise SystemExit(1) from error
