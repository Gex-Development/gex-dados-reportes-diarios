# Relatórios diários BuyGoods e PagAmerican

Run the browser-based BuyGoods Master Accounts export (default: yesterday in GMT-4, the BuyGoods day):

```bash
make buygoods
make buygoods DATE=2026-10-27
```

Run tests with `make test` and lint with `make lint` (ruff check + ruff format for Python, prettier for md/json). Enable detailed logs with `make buygoods DEBUG=1`. Override output root with `make buygoods OUTPUT_ROOT=/tmp/reports`. Every target accepts `DATE=AAAA-MM-DD`; without it, the default is the last full day in the gateway's clock (BuyGoods GMT-4, PagAmerican UTC), not the machine's. The panel formula, schema check and atomic write live in `src/common/report.py`; the Athena client shared by both lakes in `src/common/athena.py`. `.gitignore` keeps `.env`, `credentials/` and `exports/` (panel files carry customer PII) out of version control. After `npm install`, git hooks format staged files (ruff, prettier) and reject commit messages outside Conventional Commits (commitlint).

Browser automation lives in `src/scripts/extracao_diaria_buygoods_web.py`. It reads credentials and `BUYGOODS_URL_CONTA_2` from `.env`, sets the panel's Custom Range to the requested day, reuses an export already created for the same date (and checks a new one covers that day), and saves the spreadsheet under `exports/buygoods/web/AAAA/MM/master_accounts_AAAA-MM-DD.xls` (preserving `.xls` or `.xlsx` extension) plus JSON at the same path with `.json` extension. Every JSON in this project (BuyGoods web/API/lake and PagAmerican) follows `schemas/daily_report.schema.json`; the BuyGoods web JSON carries the same fields as the API JSON: Visitors, Conversion Rate, EPC and Affiliate EPC stay only in the spreadsheet, and rows whose metrics are all zero are omitted. The `Total` row is excluded, account keys use lowercase ASCII slugs, and duplicate slugs fail rather than overwrite data. Requires `uvx` and Google Chrome. Logs are INFO by default; `DEBUG=1` adds browser and export steps.

## Via API

```bash
make buygoods-api            # D-1
make buygoods-api DATE=2026-10-28
```

`src/scripts/extracao_diaria_buygoods_api.py` reads every account from `credentials/buygoods_account_tokens.csv` (`account_id`, `account_name`, `token`; never commit it) and writes `exports/buygoods/api/AAAA/MM/master_accounts_AAAA-MM-DD.json` with the same schema and `"source": "api"`. Money comes from the `/transactions.php` ledger `Net` line that closes day D (posted ~08:12 GMT-4 on D+1; before that the run fails). Panel formulas: Gross = sales − fees, Taxes = sale taxes − sale tax refunds, Net = Gross − Commissions − Refunds − Chargebacks − Taxes + Commission Voids. AOV, EPO and Affiliate EPO divide by the order count from `/orders.php` (distinct `user_id`+`sessid2` on D, without cancels or tests; matched the panel in 47/54 accounts, otherwise up to 2 orders high). The API has no Visitors, so the schema leaves out Visitors-based metrics. Only accounts with ledger movement are included.

Refunds = ledger refunds − US$ 1 per refund issued on D (the ledger embeds a $1 refund fee the panel omits; count comes from `/orders.php` filtered by `updated_at`). Against the 2026-10-28 panel export, on the 64 accounts present in both: Taxes, Chargebacks and Commission Voids 64/64 to the cent, Commissions 63/64, Refunds 62/64, Gross 55/64, Net 53/64, AOV 57/64. The API JSON also lists secondary accounts (`… 2`) that the panel login does not show.

## Via lake (Athena)

```bash
make buygoods-lake            # D-1
make buygoods-lake DATE=2026-10-28
```

`src/scripts/extracao_diaria_buygoods_lake.py` runs one Athena query (AWS profile `canonico-validador-user`, workgroup `primary`, database `gex_db_prod_silver`) over the canonical tables `fct_transacoes`, `fct_eventos_pos_venda` and `dim_conta`, and writes `exports/buygoods/lake/AAAA/MM/master_accounts_AAAA-MM-DD.json` with `"source": "lake"`, accounts sorted by name. Day D is GMT-4 (`dt_transacao_utc`/`dt_evento_utc` − 4h, partitions D-1..D+1). Following the `fct_transacoes` contract (canonico-gateways vault), nothing is filtered: platform tests never reach silver, `fl_teste = 1` marks real internal purchases, and cancelled orders remain sales. Each lake column is mapped to the matching ledger field, and the API panel formula is reused:

| Panel field                      | Lake                                                                                                                                                    |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Gross Sales                      | Σ `vl_coletado_usd` − Σ `vl_taxa_gateway_usd`                                                                                                           |
| Commissions                      | Σ `vl_comissao_afiliado_usd`                                                                                                                            |
| Refunds                          | Σ `vl_evento_usd` + `vl_evento_iva_usd` of `refund_total`, `refund_parcial`, `alerta_chargeback` (the US$ 1 fee sits in `vl_multa_usd` and is left out) |
| Chargebacks                      | Σ `vl_evento_usd` + `vl_evento_iva_usd` + `vl_multa_usd` of `chargeback_*`                                                                              |
| Taxes                            | Σ `vl_iva_usd` − refund IVA (`vl_evento_iva_usd` is an estimate: the sale line's IVA ratio, per the event contract)                                     |
| Commission Voids                 | not modeled in the lake; approximated by the commission of items charged back on D                                                                      |
| S&H                              | Σ `vl_frete_cobrado_usd` (already inside Gross; the panel always shows 0)                                                                               |
| Orders (AOV, EPO, Affiliate EPO) | distinct `id_cliente` on D                                                                                                                              |

Against the 2026-10-28 panel export (64 accounts): Chargebacks 64/64, Gross and Commissions 57/64, Refunds 46/64, Commission Voids 46/64, Taxes 34/64, Net 29/64. The lake lists the same 97 accounts as the API. Refunds match `/orders.php` `refund_amount` to the cent (Vapocept and Gelagen, 449 orders); the gap to the panel is between the ledger and `/orders`, not a lake defect. Known lake limits (vault): late refunds/chargebacks may land after D+1 (BuyGoods incremental is `updated_at` D−7 once a day), synthetic renewal rows `-B00n` carry an inferred date (`fl_data_aproximada = 1`), and the source keeps a single post-sale date per order × product.

## PagAmerican (web)

```bash
make pagamerican HEADED=1    # first run: log in on the browser window
make pagamerican             # next runs, headless (default: yesterday UTC)
make pagamerican DATE=2026-10-28
```

`src/scripts/extracao_diaria_pagamerican_web.py` opens `business.pagamerican.app/reports`, logs in with `PAGAMERICAN_LOGIN` / `PAGAMERICAN_PASSWORD` from `.env` when the session (`~/.pagamerican-profile`, outside the project) has expired, selects all six datasets (Purchases, Orders, Refunds & Chargebacks, Order Fulfillment, Abandoned Carts, Payouts) and format Excel, and saves `exports/pagamerican/web/AAAA/MM/pagamerican_AAAA-MM-DD.xlsx`. The panel's own periods are relative to the browser clock and its backend keeps only the date of each bound (its Yesterday exports D and D+1 whole), so the script clicks Yesterday only to enable "Generate report" and rewrites the export request to the UTC day D (00:00Z → 23:59Z), for any `DATE` the panel still holds. Before saving, every purchase's `Checkout Initialized At` must fall on D (the panel picks orders by checkout day, so an order opened at 23:53 and paid at 00:02 belongs to D); otherwise nothing is written. A dataset with no rows in the period (often Payouts) gets no sheet. An existing file for the date is never overwritten.

Then `src/transformations/pagamerican_report.py` writes `pagamerican_AAAA-MM-DD.json` next to the xlsx (`"gateway": "Pagamerican"`, `"source": "web"`). One account per front product of the order (the product of its `Initial` purchase in `Purchases`); upsells, refunds and chargebacks follow the order. Fields come from the `Orders` sheet: Gross = Order Amount − Creator Platform Fee, Commissions = Affiliation Amount, Taxes = Creator Tax, orders = rows; Refunds and Chargebacks = absolute `Refundamount` / `chargebackamount` from `Refunds&Chargebacks`. Net uses the BuyGoods formula and the sum over accounts matches the OnePager NET REVENUE (2026-10-29: 9,142.38). S&H and Commission Voids are 0 (not in the export). Unlike BuyGoods, refunds and chargebacks belong to the day's orders whatever their refund date, so they grow if the same day is exported again later.

## PagAmerican (API)

```bash
make pagamerican-api                    # D-1 (UTC)
make pagamerican-api DATE=2026-10-29
```

Set `PAGAMERICAN_API_KEY` in the environment or `.env`. The read-only Data API v1 script writes `exports/pagamerican/api/AAAA/MM/pagamerican_AAAA-MM-DD.json` (`"gateway": "Pagamerican"`, `"source": "api"`) without overwriting an existing report. Orders from UTC checkout day D (`checkoutInitializedAt`) are grouped by the `front` purchase's product; upsells stay with their order. API date filters use order creation, so the script reads D and D+1 and selects checkout D. Gross = `amountTransaction` − `amountCreatorPlatformFee`, commissions = `amountAffiliation`, taxes = `amountCreatorTax`, and refunds/chargebacks = `amountRefundedTotal` on D's orders, including later events available through today. `refundSource=alerta` on `/refunds` is not double-counted; chargeback alerts on `/chargebacks` are money returned and counted as chargebacks (matched the 2026-10-29 web export). S&H and Commission Voids are zero. The API retains roughly 10 days of data; historical re-extractions can fail or miss later events. The script rejects incomplete pagination rather than publishing a partial report.

## PagAmerican (lake)

```bash
make pagamerican-lake                   # D-1 (UTC)
make pagamerican-lake DATE=2026-10-29
```

`src/scripts/extracao_diaria_pagamerican_lake.py` uses the shared lake client `src/common/athena.py` (profile `canonico-validador-user`, workgroup `primary`, `gex_db_prod_silver`) and writes `exports/pagamerican/lake/AAAA/MM/pagamerican_AAAA-MM-DD.json` (`"source": "lake"`). PagAmerican is UTC at the source, so day D is `dt_dia = D`. One account per front product of the order (`cd_tipo_item = 'front'` within `id_grupo_pedido`; an order without front fails the run). Gross = Σ `vl_coletado_usd` − Σ `vl_taxa_gateway_usd`, Commissions = Σ `vl_comissao_afiliado_usd`, Taxes = Σ `vl_iva_usd`, S&H = Σ `vl_frete_cobrado_usd` (informative), orders = distinct `id_grupo_pedido`; Refunds = `refund_*` events (value + IVA) and Chargebacks = `chargeback_*` + `alerta_chargeback` (value + IVA + fine) of D's orders, any event date. Commission Voids = 0. The canonico-gateways vault keeps PagAmerican in onboarding (`production_acceptance=false`). On 2026-10-29 four accounts match the web JSON to the cent; SodaPeak differs by one order created 00:02Z on D whose checkout opened on D−1: the lake dates it by the sale, the panel by the checkout (known difference).

## Diff between sources

```bash
make diff GATEWAY=buygoods DATE=2026-10-28
make diff GATEWAY=pagamerican            # D-1
```

`src/scripts/diff_fontes.py` reads the existing web/api/lake JSONs of one gateway and day (no network), compares api and lake against `web` with a US$ 0.01 tolerance, and writes two files to `exports/<gateway>/diff/AAAA/MM/`, each validated against its schema:

- `diff_ai_AAAA-MM-DD.json` (`schemas/diff_ai.schema.json`): summary per source (accounts compared/equal, `faltando_na_fonte` = accounts the source lacks, `extra_na_fonte` = accounts only the source has, per-field equal/divergent counts and totals), plus only divergent or missing accounts with every source's value side by side, and a `contexto` note per source with its day definition and known differences.
- `diff_dashboard_AAAA-MM-DD.json` (`schemas/diff_dashboard.schema.json`): flat list, one row per account × field × compared source, equal rows included (`valor`, `valor_base`, `delta`, `delta_pct`, `status`).

The web JSON is required (it is the base) plus at least one of api/lake. Diffs are derived data and are rebuilt on every run (e.g. after the lake lands).
