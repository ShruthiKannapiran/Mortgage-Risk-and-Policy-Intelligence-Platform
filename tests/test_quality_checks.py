"""Tests for the data-quality check functions in src/quality/checks.py."""
from __future__ import annotations

import pandas as pd

from src.quality.checks import (
    _check_accepted_status_values,
    _check_date_ranges,
    _check_dti_ltv_ranges,
    _check_duplicate_application_ids,
    _check_nulls,
    _check_positive_financials,
    _check_required_columns,
)


def _fact_df(**overrides) -> pd.DataFrame:
    base = dict(
        application_id=["APP-1", "APP-2"],
        application_date=[pd.Timestamp("2024-01-01"), pd.Timestamp("2024-02-01")],
        loan_amount=[250000.0, 180000.0],
        applicant_income=[85000.0, 60000.0],
        property_value=[310000.0, 220000.0],
        loan_product_key=[1, 2],
        application_status=["Approved", "Denied"],
        debt_to_income_ratio=[0.3, 0.35],
        loan_to_value_ratio=[0.8, 0.75],
    )
    base.update(overrides)
    return pd.DataFrame(base)


def test_check_required_columns_passes(cfg):
    result = _check_required_columns(_fact_df())
    assert result.passed


def test_check_nulls_fails_when_required_column_has_null(cfg):
    df = _fact_df(loan_amount=[250000.0, None])
    result = _check_nulls(df)
    assert not result.passed
    assert "loan_amount" in result.details


def test_check_duplicate_application_ids_detects_duplicates():
    df = _fact_df(application_id=["APP-1", "APP-1"])
    result = _check_duplicate_application_ids(df)
    assert not result.passed


def test_check_date_ranges_flags_dates_before_minimum(cfg):
    df = _fact_df(application_date=[pd.Timestamp("2015-01-01"), pd.Timestamp("2024-02-01")])
    result = _check_date_ranges(df, cfg)
    assert not result.passed


def test_check_accepted_status_values_flags_unknown_status(cfg):
    df = _fact_df(application_status=["Approved", "Not-A-Real-Status"])
    result = _check_accepted_status_values(df, cfg)
    assert not result.passed


def test_check_positive_financials_flags_negative_value():
    df = _fact_df(loan_amount=[250000.0, -1.0])
    result = _check_positive_financials(df)
    assert not result.passed


def test_check_dti_ltv_ranges_flags_out_of_bound_values(cfg):
    df = _fact_df(debt_to_income_ratio=[0.3, 1.5])
    result = _check_dti_ltv_ranges(df, cfg)
    assert not result.passed


def test_check_dti_ltv_ranges_passes_for_valid_values(cfg):
    result = _check_dti_ltv_ranges(_fact_df(), cfg)
    assert result.passed
