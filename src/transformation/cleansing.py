"""Cleansing rules for the bronze -> silver transformation.

Each function documents the rule it applies so the "documented rules" requirement in
the brief is satisfied in the code itself, not just in a separate document. Rows that
cannot be reasonably fixed (invalid dates, financial values outside plausible bounds,
unrecognized categorical values) are routed to a rejected-records frame with a reason;
everything else is corrected in place and flagged via `data_quality_status`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.common.logging_setup import get_logger

logger = get_logger("transformation.cleansing")

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN",
    "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV",
    "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN",
    "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}


def _reject(reject_log: list[dict], application_id: str, stage: str, reason: str) -> None:
    reject_log.append({"application_id": application_id, "stage": stage, "reason": reason})


def blank_strings_to_null(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    object_cols = df.select_dtypes(include=["object", "string"]).columns
    for col in object_cols:
        is_blank = df[col].notna() & (df[col].astype(str).str.strip() == "")
        if is_blank.any():
            df.loc[is_blank, col] = None
    return df


def parse_types(df: pd.DataFrame) -> pd.DataFrame:
    """Rule: coerce raw string columns to their proper types; unparseable -> NaN/NaT,
    handled explicitly by downstream validation rather than failing silently."""
    df = df.copy()
    for col in ["applicant_income", "loan_amount", "property_value", "interest_rate",
                "debt_to_income_ratio", "loan_to_value_ratio"]:
        cleaned = df[col].astype(str).str.replace(r"[,$]", "", regex=True).str.strip()
        df[col] = pd.to_numeric(cleaned, errors="coerce")
    df["loan_term_months"] = pd.to_numeric(df["loan_term_months"], errors="coerce").astype("Int64")
    for col in ["application_date", "created_timestamp", "updated_timestamp"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def normalize_categoricals(df: pd.DataFrame, valid_statuses: list[str]) -> pd.DataFrame:
    """Rule: trim whitespace and normalize case for property_state (upper) and
    application_status (matched case-insensitively against the known set)."""
    df = df.copy()
    df["property_state"] = df["property_state"].astype(str).str.strip().str.upper()

    status_lookup = {s.lower(): s for s in valid_statuses}
    df["application_status"] = (
        df["application_status"].astype(str).str.strip().str.lower().map(status_lookup)
    )
    return df


def apply_validation_rules(
    df: pd.DataFrame, reject_log: list[dict], cfg: dict
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Rule: reject rows that cannot be trusted even after normalization — an invalid
    application_date, a financial value outside plausible bounds, or an unrecognized
    state/status after normalization. Returns (df, keep_mask, flagged) so callers can
    also flag 'near-miss' rows that were fixed rather than rejected."""
    dq = cfg["data_quality"]
    keep_mask = pd.Series(True, index=df.index)
    flagged = pd.Series(False, index=df.index)

    def reject_where(mask: pd.Series, reason: str) -> None:
        nonlocal keep_mask
        newly_rejected = mask & keep_mask
        for app_id in df.loc[newly_rejected, "application_id"]:
            _reject(reject_log, app_id, "transformation", reason)
        keep_mask &= ~mask

    reject_where(df["application_date"].isna(), "invalid or unparseable application_date")

    for col, lo_key, hi_key, label in [
        ("applicant_income", "min_income", "max_income", "applicant_income"),
        ("loan_amount", "min_loan_amount", "max_loan_amount", "loan_amount"),
        ("property_value", "min_property_value", "max_property_value", "property_value"),
    ]:
        out_of_range = df[col].notna() & (
            (df[col] < dq[lo_key]) | (df[col] > dq[hi_key])
        )
        reject_where(out_of_range, f"{label} outside plausible range [{dq[lo_key]}, {dq[hi_key]}]")

    bad_rate = df["interest_rate"].notna() & (
        (df["interest_rate"] < dq["min_interest_rate"]) | (df["interest_rate"] > dq["max_interest_rate"])
    )
    reject_where(bad_rate, f"interest_rate outside plausible range [{dq['min_interest_rate']}, {dq['max_interest_rate']}]")

    reject_where(~df["property_state"].isin(US_STATES), "unrecognized property_state after normalization")
    reject_where(df["application_status"].isna(), "unrecognized application_status after normalization")

    # DTI/LTV out of the configured [min,max] bound: clip rather than reject (used for
    # ranking/analytics; small overshoot beyond 1.0/2.0 shouldn't discard an otherwise-valid loan)
    dti_flag = df["debt_to_income_ratio"].notna() & (
        (df["debt_to_income_ratio"] < dq["min_dti"]) | (df["debt_to_income_ratio"] > dq["max_dti"])
    )
    ltv_flag = df["loan_to_value_ratio"].notna() & (
        (df["loan_to_value_ratio"] < dq["min_ltv"]) | (df["loan_to_value_ratio"] > dq["max_ltv"])
    )
    df["debt_to_income_ratio"] = df["debt_to_income_ratio"].clip(dq["min_dti"], dq["max_dti"])
    df["loan_to_value_ratio"] = df["loan_to_value_ratio"].clip(dq["min_ltv"], dq["max_ltv"])
    flagged |= dti_flag | ltv_flag

    return df, keep_mask, flagged


def handle_missing_values(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Documented rules:
    - applicant_income / interest_rate missing -> impute with the median for the same
      loan_type (falls back to the overall median if the group is empty), flagged.
    - property_county / credit_score_range missing -> 'Unknown', flagged.
    - denial_reason missing while status == 'Denied' -> 'Not Specified', flagged.
      denial_reason missing while status != 'Denied' is expected, not an issue.
    """
    df = df.copy()
    flagged = pd.Series(False, index=df.index)

    for col in ["applicant_income", "interest_rate"]:
        missing = df[col].isna()
        if missing.any():
            group_median = df.groupby("loan_type")[col].transform("median")
            overall_median = df[col].median()
            df.loc[missing, col] = group_median[missing].fillna(overall_median)
            flagged |= missing

    for col in ["property_county", "credit_score_range"]:
        missing = df[col].isna() | (df[col].astype(str).str.strip() == "")
        if missing.any():
            df.loc[missing, col] = "Unknown"
            flagged |= missing

    denied_missing_reason = (df["application_status"] == "Denied") & (
        df["denial_reason"].isna() | (df["denial_reason"].astype(str).str.strip() == "")
    )
    df.loc[denied_missing_reason, "denial_reason"] = "Not Specified"
    flagged |= denied_missing_reason

    return df, flagged


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """Rule: drop exact duplicate rows first, then — since the same application_id can
    legitimately reappear across delivery batches as an update — keep only the most
    recent version per application_id, ranked by updated_timestamp then
    _ingestion_timestamp."""
    before = len(df)
    df = df.drop_duplicates(
        subset=[c for c in df.columns if c not in ("_ingestion_timestamp",)]
    )
    logger.info("Dropped %s exact duplicate row(s)", before - len(df))

    df = df.sort_values(["updated_timestamp", "_ingestion_timestamp"])
    df = df.drop_duplicates(subset=["application_id"], keep="last")
    return df.reset_index(drop=True)