"""Shared pytest fixtures."""
from __future__ import annotations

import pandas as pd
import pytest

from src.common.config import load_config


@pytest.fixture(scope="session")
def cfg() -> dict:
    return load_config()


def make_bronze_row(**overrides) -> dict:
    """A minimal valid bronze-layer row (raw string values, as ingestion would produce)."""
    base = dict(
        application_id="APP-C-00000001",
        application_date="2024-03-15T00:00:00",
        applicant_id="APPL-0000001",
        applicant_income="85000.0",
        loan_amount="250000.0",
        property_value="310000.0",
        loan_type="Conventional",
        interest_rate="6.25",
        loan_term_months="360",
        debt_to_income_ratio="0.32",
        loan_to_value_ratio="0.81",
        property_state="TX",
        property_county="Travis County",
        lender="Meridian Home Lending",
        application_status="Approved",
        denial_reason=None,
        credit_score_range="700-739",
        data_source_system="LOS-CORE",
        created_timestamp="2024-03-15T00:00:00",
        updated_timestamp="2024-03-20T00:00:00",
        _source_file="test_source.csv",
        _source_name="LOS-CORE",
        _ingestion_timestamp=pd.Timestamp("2024-03-21"),
    )
    base.update(overrides)
    return base


@pytest.fixture
def bronze_df_factory():
    def _factory(rows: list[dict]) -> pd.DataFrame:
        return pd.DataFrame([make_bronze_row(**r) for r in rows])
    return _factory


def make_silver_row(**overrides) -> dict:
    """A minimal, fully-typed gold-ready silver row (matches SILVER_COLUMNS shape)."""
    base = dict(
        application_id="APP-C-00000001",
        application_date=pd.Timestamp("2024-03-15"),
        applicant_id="APPL-0000001",
        applicant_income=85000.0,
        loan_amount=250000.0,
        property_value=310000.0,
        loan_type="Conventional",
        interest_rate=6.25,
        loan_term_months=360,
        debt_to_income_ratio=0.32,
        loan_to_value_ratio=0.81,
        property_state="TX",
        property_county="Travis County",
        lender="Meridian Home Lending",
        application_status="Approved",
        denial_reason=None,
        credit_score_range="700-739",
        data_source_system="LOS-CORE",
        created_timestamp=pd.Timestamp("2024-03-15"),
        updated_timestamp=pd.Timestamp("2024-03-20"),
        income_band="50K-100K",
        loan_amount_band="250K-500K",
        dti_band="30-36%",
        ltv_band="80-90%",
        application_processing_days=5.0,
        approval_indicator=1,
        high_risk_indicator=0,
        data_quality_status="clean",
        source_file="test_source.csv",
    )
    base.update(overrides)
    return base


@pytest.fixture
def silver_df_factory():
    def _factory(rows: list[dict]) -> pd.DataFrame:
        return pd.DataFrame([make_silver_row(**r) for r in rows])
    return _factory
