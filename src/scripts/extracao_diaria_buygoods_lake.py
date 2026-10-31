#!/usr/bin/env python3
"""Build yesterday's BuyGoods Master Accounts JSON from the canonical lake (Athena silver)."""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from loguru import logger

from src.common.athena import accounts_from_rows, run_query
from src.common.report import BUYGOODS_TZ, finalize_report, write_report, yesterday

ROOT = Path(__file__).resolve().parents[2]
REFUND_EVENTS = "('refund_total', 'refund_parcial', 'alerta_chargeback')"

# Day D is BuyGoods platform time (GMT-4); dt_dia is the UTC partition, so scan D-1..D+1 and cut locally.
# Each source column is renamed to the ledger field it stands for, so the panel formula is shared.
# No fl_teste filter: platform tests never reach silver, and fl_teste = 1 marks real internal purchases
# that the panel counts (fct_transacoes contract). Cancelled orders stay as sales too, as in the panel.
QUERY = """
WITH vendas AS (
  SELECT id_conta,
    sum(vl_coletado_usd) AS sales,
    sum(vl_taxa_gateway_usd) AS fees,
    sum(vl_iva_usd) AS sale_taxes,
    sum(vl_comissao_afiliado_usd) AS commissions,
    sum(coalesce(vl_frete_cobrado_usd, 0)) AS shipping_handling,
    count(DISTINCT id_cliente) AS orders
  FROM fct_transacoes
  WHERE cd_gateway = 'buygoods'
    AND dt_dia BETWEEN date '{start}' AND date '{end}'
    AND date(dt_transacao_utc - interval '4' hour) = date '{day}'
  GROUP BY 1
),
eventos AS (
  SELECT t.id_conta,
    sum(CASE WHEN e.cd_tipo_evento IN {refund_events}
      THEN coalesce(e.vl_evento_usd, 0) + coalesce(e.vl_evento_iva_usd, 0) END) AS refunds,
    sum(CASE WHEN e.cd_tipo_evento IN {refund_events} THEN coalesce(e.vl_evento_iva_usd, 0) END) AS sale_tax_refunds,
    sum(CASE WHEN e.cd_tipo_evento LIKE 'chargeback%'
      THEN coalesce(e.vl_evento_usd, 0) + coalesce(e.vl_evento_iva_usd, 0) + coalesce(e.vl_multa_usd, 0) END) AS chargebacks,
    -- shortcut: the lake has no commission voids; commission of items charged back that day matched 46/64
    -- accounts on 2026-10-28 and overshoots large accounts by up to US$ 2k. Replace once voids are modeled.
    sum(CASE WHEN e.cd_tipo_evento LIKE 'chargeback%' THEN t.vl_comissao_afiliado_usd END) AS commissions_voids
  FROM fct_eventos_pos_venda e
  JOIN fct_transacoes t ON t.id_transacao = e.id_transacao AND t.cd_gateway = 'buygoods'
  WHERE e.cd_gateway = 'buygoods'
    AND e.dt_dia BETWEEN date '{start}' AND date '{end}'
    AND date(e.dt_evento_utc - interval '4' hour) = date '{day}'
  GROUP BY 1
)
SELECT c.nm_conta, v.sales, v.fees, v.sale_taxes, v.commissions, v.shipping_handling, v.orders,
       e.refunds, e.sale_tax_refunds, e.chargebacks, e.commissions_voids
FROM dim_conta c
LEFT JOIN vendas v ON v.id_conta = c.id_conta
LEFT JOIN eventos e ON e.id_conta = c.id_conta
WHERE c.cd_gateway = 'buygoods' AND (v.id_conta IS NOT NULL OR e.id_conta IS NOT NULL)
ORDER BY c.nm_conta
"""


def report_path(root: Path, report_date: date) -> Path:
    return (
        root
        / "exports"
        / "buygoods"
        / "lake"
        / f"{report_date.year:04d}"
        / f"{report_date.month:02d}"
        / f"master_accounts_{report_date.isoformat()}.json"
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
    report_date = args.date or yesterday(datetime.now(timezone.utc), BUYGOODS_TZ)
    output = report_path(args.output_root.resolve(), report_date)
    logger.info("Starting BuyGoods lake extraction for {}", report_date)
    if output.exists():
        logger.info("JSON report already saved: {}", output)
        return 0

    sql = QUERY.format(
        day=report_date.isoformat(),
        start=(report_date - timedelta(days=1)).isoformat(),
        end=(report_date + timedelta(days=1)).isoformat(),
        refund_events=REFUND_EVENTS,
    )
    logger.debug(sql)
    rows = run_query(sql)
    if not rows:
        raise RuntimeError(f"Lake has no BuyGoods transactions or events for {report_date} yet")
    logger.info("{} accounts had movement", len(rows))
    write_report(finalize_report(accounts_from_rows(rows), report_date, "Buygoods", "lake"), output)
    logger.info("Saved JSON report: {}", output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        logger.exception("BuyGoods lake extraction failed")
        raise SystemExit(1) from error
