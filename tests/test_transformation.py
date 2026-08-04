"""Tests for the cleansing rules and derived-field logic in src/transformation."""
from __future__ import annotations

import pandas as pd

from src.transformation.cleansing import (
    apply_validation_rules,
    blank_strings_to_null,
    deduplicate,
    handle_missing_values,
    normalize_categoricals,
    parse_types,
)
from src.transformation.derive import add_derived_fields


def _prepared(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    df = parse_types(df)
    df = normalize_categoricals(df, cfg["data_quality"]["valid_application_statuses"])
    return df


def test_blank_strings_to_null_normalizes_empty_and_whitespace_only_cells(bronze_df_factory):
    df = bronze_df_factory([{"denial_reason": "", "property_county": "   "}])
    result = blank_strings_to_null(df)
    assert pd.isna(result.loc[0, "denial_reason"])
    assert pd.isna(result.loc[0, "property_county"])


def test_blank_strings_to_null_leaves_real_values_untouched(bronze_df_factory):
    df = bronze_df_factory([{"denial_reason": "Credit history"}])
    result = blank_strings_to_null(df)
    assert result.loc[0, "denial_reason"] == "Credit history"


def test_parse_types_handles_currency_formatted_strings(bronze_df_factory):
    df = bronze_df_factory([{"loan_amount": "$231,649.84"}])
    parsed = parse_types(df)
    assert parsed.loc[0, "loan_amount"] == 231649.84


def test_parse_types_coerces_unparseable_dates_to_nat(bronze_df_factory):
    df = bronze_df_factory([{"application_date": "not-a-date"}])
    parsed = parse_types(df)
    assert pd.isna(parsed.loc[0, "application_date"])


def test_normalize_categoricals_fixes_whitespace_and_case(bronze_df_factory, cfg):
    df = bronze_df_factory([{"property_state": " fl ", "application_status": "APPROVED"}])
    normalized = normalize_categoricals(df, cfg["data_quality"]["valid_application_statuses"])
    assert normalized.loc[0, "property_state"] == "FL"
    assert normalized.loc[0, "application_status"] == "Approved"


def test_apply_validation_rules_rejects_invalid_date(bronze_df_factory, cfg):
    df = _prepared(bronze_df_factory([{"application_id": "APP-BAD-DATE", "application_date": "garbage"}]), cfg)
    reject_log: list[dict] = []
    _, keep_mask, _ = apply_validation_rules(df, reject_log, cfg)
    assert not keep_mask.iloc[0]
    assert reject_log[0]["application_id"] == "APP-BAD-DATE"
    assert "application_date" in reject_log[0]["reason"]


def test_apply_validation_rules_rejects_negative_financials(bronze_df_factory, cfg):
    df = _prepared(bronze_df_factory([{"application_id": "APP-NEG", "loan_amount": "-250000.0"}]), cfg)
    reject_log: list[dict] = []
    _, keep_mask, _ = apply_validation_rules(df, reject_log, cfg)
    assert not keep_mask.iloc[0]


def test_apply_validation_rules_keeps_valid_row(bronze_df_factory, cfg):
    df = _prepared(bronze_df_factory([{}]), cfg)
    reject_log: list[dict] = []
    _, keep_mask, flags = apply_validation_rules(df, reject_log, cfg)
    assert keep_mask.iloc[0]
    assert not flags.iloc[0]
    assert reject_log == []


def test_handle_missing_values_imputes_income_with_group_median(bronze_df_factory, cfg):
    df = _prepared(
        bronze_df_factory([
            {"application_id": "APP-1", "loan_type": "FHA", "applicant_income": "100000"},
            {"application_id": "APP-2", "loan_type": "FHA", "applicant_income": "200000"},
            {"application_id": "APP-3", "loan_type": "FHA", "applicant_income": None},
        ]),
        cfg,
    )
    filled, flags = handle_missing_values(df)
    assert filled.loc[2, "applicant_income"] == 150000.0  # median of the FHA group
    assert flags.iloc[2]
    assert not flags.iloc[0]


def test_handle_missing_values_sets_not_specified_for_denied_without_reason(bronze_df_factory, cfg):
    df = _prepared(
        bronze_df_factory([{"application_status": "Denied", "denial_reason": None}]), cfg
    )
    filled, flags = handle_missing_values(df)
    assert filled.loc[0, "denial_reason"] == "Not Specified"
    assert flags.iloc[0]


def test_deduplicate_keeps_latest_update_per_application_id(bronze_df_factory, cfg):
    df = _prepared(
        bronze_df_factory([
            {"application_id": "APP-1", "application_status": "Incomplete",
             "updated_timestamp": "2024-01-01T00:00:00", "_ingestion_timestamp": pd.Timestamp("2024-01-01")},
            {"application_id": "APP-1", "application_status": "Approved",
             "updated_timestamp": "2024-02-01T00:00:00", "_ingestion_timestamp": pd.Timestamp("2024-02-01")},
        ]),
        cfg,
    )
    result = deduplicate(df)
    assert len(result) == 1
    assert result.loc[0, "application_status"] == "Approved"


def test_deduplicate_drops_exact_duplicate_rows(bronze_df_factory, cfg):
    df = _prepared(bronze_df_factory([{"application_id": "APP-1"}, {"application_id": "APP-1"}]), cfg)
    result = deduplicate(df)
    assert len(result) == 1


def test_add_derived_fields_flags_high_dti_as_high_risk(bronze_df_factory, cfg):
    df = _prepared(bronze_df_factory([{"debt_to_income_ratio": "0.50", "loan_to_value_ratio": "0.5", "credit_score_range": "740-779"}]), cfg)
    was_flagged = pd.Series([False], index=df.index)
    derived = add_derived_fields(df, cfg, was_flagged)
    assert derived.loc[0, "high_risk_indicator"] == 1
    assert derived.loc[0, "dti_band"] == "43%+"


def test_add_derived_fields_approval_indicator_matches_status(bronze_df_factory, cfg):
    df = _prepared(bronze_df_factory([{"application_status": "Denied"}]), cfg)
    was_flagged = pd.Series([False], index=df.index)
    derived = add_derived_fields(df, cfg, was_flagged)
    assert derived.loc[0, "approval_indicator"] == 0
    assert derived.loc[0, "data_quality_status"] == "clean"
