#!/usr/bin/env python3
"""Build yesterday's PagAmerican JSON from the canonical lake (Athena silver)."""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from loguru import logger

from src.common.athena import accounts_from_rows, run_query
from src.common.report import PAGAMERICAN_TZ, finalize_report, write_report, yesterday

ROOT = Path(__file__).resolve().parents[2]

# PagAmerican is UTC at the source (canonico-gateways pagamerican.toml), so dt_dia is day D directly.
# Same grain as the web/API JSON: one account per front product of the order (id_grupo_pedido),
# refunds/chargebacks of D's orders whatever the event date. Alerts are chargebacks, as in the panel.
# Columns are renamed to the ledger fields of the shared panel formula; the panel subtracts no
# tax refund (refunds already carry their tax), so sale_tax_refunds stays out.
QUERY = """
WITH itens AS (
  SELECT * FROM fct_transacoes WHERE cd_gateway = 'pagamerican' AND dt_dia = date '{day}'
),
pedidos AS (
  SELECT id_grupo_pedido, max(CASE WHEN cd_tipo_item = 'front' THEN nm_produto END) AS produto
  FROM itens GROUP BY 1
),
vendas AS (
  SELECT p.produto,
    sum(i.vl_coletado_usd) AS sales,
    sum(i.vl_taxa_gateway_usd) AS fees,
    sum(i.vl_iva_usd) AS sale_taxes,
    sum(i.vl_comissao_afiliado_usd) AS commissions,
    sum(coalesce(i.vl_frete_cobrado_usd, 0)) AS shipping_handling,
    count(DISTINCT i.id_grupo_pedido) AS orders
  FROM itens i JOIN pedidos p ON p.id_grupo_pedido = i.id_grupo_pedido
  GROUP BY 1
),
eventos AS (
  SELECT p.produto,
    sum(CASE WHEN e.cd_tipo_evento LIKE 'refund%'
      THEN coalesce(e.vl_evento_usd, 0) + coalesce(e.vl_evento_iva_usd, 0) END) AS refunds,
    sum(CASE WHEN e.cd_tipo_evento LIKE 'chargeback%' OR e.cd_tipo_evento = 'alerta_chargeback'
      THEN coalesce(e.vl_evento_usd, 0) + coalesce(e.vl_evento_iva_usd, 0) + coalesce(e.vl_multa_usd, 0) END) AS chargebacks
  FROM fct_eventos_pos_venda e
  JOIN itens i ON i.id_transacao = e.id_transacao
  JOIN pedidos p ON p.id_grupo_pedido = i.id_grupo_pedido
  WHERE e.cd_gateway = 'pagamerican' AND e.dt_dia >= date '{day}'
  GROUP BY 1
)
SELECT v.produto AS nm_conta, v.sales, v.fees, v.sale_taxes, v.commissions, v.shipping_handling, v.orders,
       e.refunds, e.chargebacks
FROM vendas v LEFT JOIN eventos e ON e.produto IS NOT DISTINCT FROM v.produto
ORDER BY 1
"""


def build_report(rows: list[dict], report_date: date) -> dict:
    if any(row["nm_conta"] is None for row in rows):
        raise ValueError(f"Lake has PagAmerican orders without a front item on {report_date}; cannot name their account")
    return finalize_report(accounts_from_rows(rows), report_date, "Pagamerican", "lake")


def report_path(root: Path, report_date: date) -> Path:
    return (
        root
        / "exports"
        / "pagamerican"
        / "lake"
        / f"{report_date.year:04d}"
        / f"{report_date.month:02d}"
        / f"pagamerican_{report_date.isoformat()}.json"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=ROOT, help="Root directory for exports (default: project root)")
    parser.add_argument("--date", type=date.fromisoformat, help="Report date YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--debug", action="store_true", help="Log the Athena query")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logger.remove()
    logger.add(sys.stderr, level="DEBUG" if args.debug else "INFO", colorize=sys.stderr.isatty())
    report_date = args.date or yesterday(datetime.now(timezone.utc), PAGAMERICAN_TZ)
    output = report_path(args.output_root.resolve(), report_date)
    logger.info("Starting PagAmerican lake extraction for {}", report_date)
    if output.exists():
        logger.info("JSON report already saved: {}", output)
        return 0

    sql = QUERY.format(day=report_date.isoformat())
    logger.debug(sql)
    rows = run_query(sql)
    if not rows:
        raise RuntimeError(f"Lake has no PagAmerican transactions for {report_date} yet")
    write_report(build_report(rows, report_date), output)
    logger.info("Saved JSON report: {}", output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        logger.exception("PagAmerican lake extraction failed")
        raise SystemExit(1) from error
