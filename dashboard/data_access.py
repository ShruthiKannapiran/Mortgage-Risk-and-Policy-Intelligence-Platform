"""Cached data access layer for the Streamlit dashboard.

Loads the joined fact + dimension view once per process (Streamlit's cache), then all
filtering happens in-memory over the resulting Pandas DataFrame — the dataset is modest
enough (~250k rows) that this is simpler and just as responsive as re-querying DuckDB on
every filter change.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.common.db import get_connection

JOINED_VIEW_SQL = """
SELECT
    f.application_id,
    d.full_date AS application_date,
    d.year_month,
    p.property_state,
    p.property_county,
    l.lender_name,
    lp.loan_type,
    lp.loan_term_months,
    f.applicant_income,
    f.loan_amount,
    f.property_value,
    f.interest_rate,
    f.debt_to_income_ratio,
    f.loan_to_value_ratio,
    f.application_status,
    f.denial_reason,
    f.income_band,
    f.loan_amount_band,
    f.dti_band,
    f.ltv_band,
    f.approval_indicator,
    f.high_risk_indicator,
    f.data_quality_status
FROM fact_loan_application f
JOIN dim_date d ON f.date_key = d.date_key
JOIN dim_property p ON f.property_key = p.property_key
JOIN dim_lender l ON f.lender_key = l.lender_key
JOIN dim_loan_product lp ON f.loan_product_key = lp.loan_product_key
"""


@st.cache_data(ttl=300)
def load_portfolio() -> pd.DataFrame:
    con = get_connection(read_only=True)
    df = con.execute(JOINED_VIEW_SQL).df()
    con.close()
    df["application_date"] = pd.to_datetime(df["application_date"])
    df["risk_category"] = df["high_risk_indicator"].map({1: "High risk", 0: "Standard"})
    return df
