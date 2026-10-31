"""Read-only Athena access to the canonical lake, shared by the gateway lake extractions."""

from __future__ import annotations

import time

import boto3

from src.common.report import account_metrics, money

REGION = "us-east-1"
# canonico-gateways AGENTS/CONTEXT: lake reads go through this read-only profile, never `default`.
PROFILE = "canonico-validador-user"
DATABASE = "gex_db_prod_silver"
WORKGROUP = "primary"


def run_query(sql: str) -> list[dict]:
    athena = boto3.Session(profile_name=PROFILE, region_name=REGION).client("athena")
    execution_id = athena.start_query_execution(
        QueryString=sql, QueryExecutionContext={"Database": DATABASE}, WorkGroup=WORKGROUP
    )["QueryExecutionId"]
    while True:
        status = athena.get_query_execution(QueryExecutionId=execution_id)["QueryExecution"]["Status"]
        if status["State"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1)
    if status["State"] != "SUCCEEDED":
        raise RuntimeError(f"Athena query {execution_id} {status['State']}: {status.get('StateChangeReason')}")

    rows = []
    for page in athena.get_paginator("get_query_results").paginate(QueryExecutionId=execution_id):
        rows.extend([cell.get("VarCharValue") for cell in row["Data"]] for row in page["ResultSet"]["Rows"])
    header, *data = rows
    return [dict(zip(header, row)) for row in data]


def accounts_from_rows(rows: list[dict]) -> list[dict]:
    """Rows whose columns are named after LEDGER_FIELDS, plus nm_conta and orders."""
    return [account_metrics(row["nm_conta"].strip(), row, int(money(row["orders"])), 0) for row in rows]
