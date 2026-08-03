"""Derived fields added on top of the cleansed silver data."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _band(value: float, bands: list[list]) -> str | None:
    if pd.isna(value):
        return None
    for lo, hi, label in bands:
        if hi is None:
            if value >= lo:
                return label
        elif lo <= value < hi:
            return label
    return None


def add_band_column(df: pd.DataFrame, source_col: str, target_col: str, bands: list[list]) -> pd.DataFrame:
    df[target_col] = df[source_col].apply(lambda v: _band(v, bands))
    return df


def add_derived_fields(df: pd.DataFrame, cfg: dict, was_flagged: pd.Series) -> pd.DataFrame:
    df = df.copy()
    bands = cfg["bands"]
    dq = cfg["data_quality"]

    df = add_band_column(df, "applicant_income", "income_band", bands["income"])
    df = add_band_column(df, "loan_amount", "loan_amount_band", bands["loan_amount"])
    df = add_band_column(df, "debt_to_income_ratio", "dti_band", bands["dti"])
    df = add_band_column(df, "loan_to_value_ratio", "ltv_band", bands["ltv"])

    df["application_processing_days"] = (
        (df["updated_timestamp"] - df["created_timestamp"]).dt.total_seconds() / 86400.0
    ).round(2)

    df["approval_indicator"] = (df["application_status"] == "Approved").astype(int)

    high_risk_scores = set(dq["high_risk_credit_scores"])
    df["high_risk_indicator"] = (
        (df["debt_to_income_ratio"] >= dq["high_risk_dti_threshold"])
        | (df["loan_to_value_ratio"] >= dq["high_risk_ltv_threshold"])
        | (df["credit_score_range"].isin(high_risk_scores))
    ).astype(int)

    df["data_quality_status"] = np.where(was_flagged.reindex(df.index, fill_value=False), "flagged", "clean")

    return df
