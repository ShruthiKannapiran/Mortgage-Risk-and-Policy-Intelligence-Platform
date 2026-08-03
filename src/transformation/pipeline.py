"""Bronze -> Silver transformation pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.common.config import get_paths, load_config
from src.common.db import get_connection
from src.common.logging_setup import get_logger
from src.ingestion.pipeline import BRONZE_TABLE
from src.transformation.cleansing import (
    apply_validation_rules,
    blank_strings_to_null,
    deduplicate,
    handle_missing_values,
    normalize_categoricals,
    parse_types,
)
from src.transformation.derive import add_derived_fields

logger = get_logger("transformation")

SILVER_TABLE = "silver_loan_application"

SILVER_COLUMNS = [
    "application_id", "application_date", "applicant_id", "applicant_income", "loan_amount",
    "property_value", "loan_type", "interest_rate", "loan_term_months", "debt_to_income_ratio",
    "loan_to_value_ratio", "property_state", "property_county", "lender", "application_status",
    "denial_reason", "credit_score_range", "data_source_system", "created_timestamp",
    "updated_timestamp", "income_band", "loan_amount_band", "dti_band", "ltv_band",
    "application_processing_days", "approval_indicator", "high_risk_indicator",
    "data_quality_status", "_source_file",
]


@dataclass
class TransformationResult:
    rows_read: int
    rows_rejected: int
    rows_written: int
    rows_flagged: int


def run_transformation() -> TransformationResult:
    cfg = load_config()
    paths = get_paths()
    rejected_dir: Path = paths["rejected_dir"]
    rejected_dir.mkdir(parents=True, exist_ok=True)

    con = get_connection()
    df = con.execute(f"SELECT * FROM {BRONZE_TABLE}").df()
    rows_read = len(df)
    logger.info("Read %s row(s) from %s", rows_read, BRONZE_TABLE)

    reject_log: list[dict] = []

    df = blank_strings_to_null(df)
    df = parse_types(df)
    df = normalize_categoricals(df, cfg["data_quality"]["valid_application_statuses"])

    df, keep_mask, range_flags = apply_validation_rules(df, reject_log, cfg)
    df["_flagged_range"] = range_flags
    df = df.loc[keep_mask].copy()

    df, missing_flags = handle_missing_values(df)
    df["_flagged_missing"] = missing_flags

    was_flagged = df["_flagged_range"].fillna(False) | df["_flagged_missing"].fillna(False)
    df = df.drop(columns=["_flagged_range", "_flagged_missing"])

    # Attach as a real column so it survives dedup's sort/reset_index correctly,
    # instead of relying on row-position alignment which breaks after reset_index.
    df["_was_flagged_tmp"] = was_flagged
    df = deduplicate(df)
    was_flagged = df["_was_flagged_tmp"]
    df = df.drop(columns=["_was_flagged_tmp"])

    df = add_derived_fields(df, cfg, was_flagged)

    rejected_df = pd.DataFrame(reject_log)
    rows_rejected = len(rejected_df)
    if rows_rejected:
        reject_path = rejected_dir / "transformation_rejected.csv"
        rejected_df.to_csv(reject_path, index=False)
        logger.warning("Rejected %s row(s) during transformation -> %s", rows_rejected, reject_path)

    silver_df = df[SILVER_COLUMNS].rename(columns={"_source_file": "source_file"})

    con.execute(f"DROP TABLE IF EXISTS {SILVER_TABLE}")
    con.register("silver_df", silver_df)
    con.execute(f"CREATE TABLE {SILVER_TABLE} AS SELECT * FROM silver_df")
    con.unregister("silver_df")
    con.close()

    rows_flagged = int((silver_df["data_quality_status"] == "flagged").sum())
    logger.info(
        "Transformation complete: %s row(s) written to %s (%s flagged, %s rejected)",
        len(silver_df), SILVER_TABLE, rows_flagged, rows_rejected,
    )
    return TransformationResult(
        rows_read=rows_read, rows_rejected=rows_rejected, rows_written=len(silver_df), rows_flagged=rows_flagged,
    )


if __name__ == "__main__":
    run_transformation()
