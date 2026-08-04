"""Incremental gold-layer load.

Classifies every row coming out of the silver layer as NEW, UPDATED, or UNCHANGED
relative to what's already in `fact_loan_application`, using a row hash over the
business-meaningful columns (HASH_COLUMNS below) rather than a naive full reload. Only
NEW and UPDATED rows are written (delete-then-insert by application_id), which makes
re-running the pipeline against the same source data a no-op (idempotent, no duplicate
loading) and keeps repeat runs fast as the dataset grows.

If a run fails partway through, the fact table simply reflects whatever had already been
committed; re-running `load_gold` recomputes the same NEW/UPDATED/UNCHANGED classification
from scratch and safely finishes the job — no special recovery step is needed because the
comparison is always against current state, not against "what the last run did".
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

import duckdb
import pandas as pd

from src.common.logging_setup import get_logger
from src.database import audit
from src.database.dimensions import refresh_dim_date, refresh_dims_from_silver, resolve_surrogate_keys
from src.database.schema_setup import run_ddl

logger = get_logger("database.incremental")

FACT_TABLE = "fact_loan_application"

HASH_COLUMNS = [
    "applicant_income", "loan_amount", "property_value", "interest_rate",
    "debt_to_income_ratio", "loan_to_value_ratio", "application_processing_days",
    "application_status", "denial_reason", "income_band", "loan_amount_band",
    "dti_band", "ltv_band", "approval_indicator", "high_risk_indicator",
    "data_quality_status", "updated_timestamp", "source_file",
]

FACT_COLUMNS = [
    "application_id", "date_key", "applicant_key", "property_key", "lender_key",
    "loan_product_key", "applicant_income", "loan_amount", "property_value",
    "interest_rate", "debt_to_income_ratio", "loan_to_value_ratio",
    "application_processing_days", "application_status", "denial_reason", "income_band",
    "loan_amount_band", "dti_band", "ltv_band", "approval_indicator", "high_risk_indicator",
    "data_quality_status", "data_source_system", "application_date", "created_timestamp",
    "updated_timestamp", "source_file", "row_hash", "loaded_at",
]


@dataclass
class IncrementalLoadResult:
    run_id: str
    rows_read: int
    rows_new: int
    rows_updated: int
    rows_unchanged: int


def compute_row_hash(df: pd.DataFrame) -> pd.Series:
    return pd.util.hash_pandas_object(df[HASH_COLUMNS], index=False).astype(str)


def load_gold(con: duckdb.DuckDBPyConnection, silver_df: pd.DataFrame, run_id: str | None = None) -> IncrementalLoadResult:
    run_id = run_id or str(uuid.uuid4())
    run_ddl(con)
    audit.start_stage(con, run_id, "dimensional_load")

    try:
        refresh_dim_date(con)
        refresh_dims_from_silver(con, silver_df)
        resolved = resolve_surrogate_keys(con, silver_df)
        resolved["row_hash"] = compute_row_hash(resolved)
        resolved["loaded_at"] = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

        existing = con.execute(f"SELECT application_id, row_hash FROM {FACT_TABLE}").df()
        merged = resolved.merge(existing, on="application_id", how="left", suffixes=("", "_existing"))
        is_new = merged["row_hash_existing"].isna()
        is_updated = (~is_new) & (merged["row_hash"] != merged["row_hash_existing"])
        unchanged_count = int((~is_new & ~is_updated).sum())
        new_count = int(is_new.sum())
        updated_count = int(is_updated.sum())

        to_upsert = merged.loc[is_new | is_updated, FACT_COLUMNS].copy()

        if not to_upsert.empty:
            con.register("fact_upsert", to_upsert)
            con.execute(f"DELETE FROM {FACT_TABLE} WHERE application_id IN (SELECT application_id FROM fact_upsert)")
            con.execute(f"INSERT INTO {FACT_TABLE} ({', '.join(FACT_COLUMNS)}) SELECT {', '.join(FACT_COLUMNS)} FROM fact_upsert")
            con.unregister("fact_upsert")

        audit.finish_stage(
            con, run_id, "dimensional_load", "SUCCESS",
            rows_read=len(silver_df), rows_new=new_count, rows_updated=updated_count,
            rows_unchanged=unchanged_count,
        )
        logger.info(
            "Gold load complete (run_id=%s): %s new, %s updated, %s unchanged",
            run_id, new_count, updated_count, unchanged_count,
        )
        return IncrementalLoadResult(
            run_id=run_id, rows_read=len(silver_df), rows_new=new_count,
            rows_updated=updated_count, rows_unchanged=unchanged_count,
        )
    except Exception as exc:
        audit.finish_stage(con, run_id, "dimensional_load", "FAILED", error_message=str(exc))
        logger.exception("Gold load failed (run_id=%s)", run_id)
        raise


if __name__ == "__main__":
    from src.common.db import get_connection
    con = get_connection()
    silver_df = con.execute("SELECT * FROM silver_loan_application").df()
    load_gold(con, silver_df)
    con.close()
