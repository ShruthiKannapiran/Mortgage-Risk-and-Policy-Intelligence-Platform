"""Mortgage Risk and Policy Intelligence Platform — Streamlit dashboard.

Run with: streamlit run dashboard/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard.data_access import load_portfolio

st.set_page_config(page_title="Mortgage Risk & Policy Intelligence", layout="wide")

st.title("Mortgage Risk and Policy Intelligence Platform")
st.caption("Portfolio analytics over the gold-layer star schema (DuckDB).")

df = load_portfolio()

# --- Sidebar filters ---------------------------------------------------------
st.sidebar.header("Filters")

min_date, max_date = df["application_date"].min(), df["application_date"].max()
date_range = st.sidebar.date_input(
    "Application date range", value=(min_date.date(), max_date.date()),
    min_value=min_date.date(), max_value=max_date.date(),
)
states = st.sidebar.multiselect("State", sorted(df["property_state"].unique()))
lenders = st.sidebar.multiselect("Lender", sorted(df["lender_name"].unique()))
loan_types = st.sidebar.multiselect("Loan type", sorted(df["loan_type"].unique()))
statuses = st.sidebar.multiselect("Application status", sorted(df["application_status"].unique()))
risk_categories = st.sidebar.multiselect("Risk category", sorted(df["risk_category"].unique()))

filtered = df.copy()
if isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = date_range
    filtered = filtered[
        (filtered["application_date"] >= pd.Timestamp(start))
        & (filtered["application_date"] <= pd.Timestamp(end))
    ]
if states:
    filtered = filtered[filtered["property_state"].isin(states)]
if lenders:
    filtered = filtered[filtered["lender_name"].isin(lenders)]
if loan_types:
    filtered = filtered[filtered["loan_type"].isin(loan_types)]
if statuses:
    filtered = filtered[filtered["application_status"].isin(statuses)]
if risk_categories:
    filtered = filtered[filtered["risk_category"].isin(risk_categories)]

st.sidebar.markdown(f"**{len(filtered):,}** of {len(df):,} applications match the current filters.")

if filtered.empty:
    st.warning("No applications match the selected filters.")
    st.stop()

# --- Executive Summary --------------------------------------------------------
st.header("Executive Summary")
total_applications = len(filtered)
total_loan_amount = filtered["loan_amount"].sum()
approval_rate = 100 * filtered["approval_indicator"].mean()
denial_rate = 100 * (filtered["application_status"] == "Denied").mean()
avg_loan_amount = filtered["loan_amount"].mean()
avg_income = filtered["applicant_income"].mean()
high_risk_count = int(filtered["high_risk_indicator"].sum())

cols = st.columns(4)
cols[0].metric("Total Applications", f"{total_applications:,}")
cols[1].metric("Total Requested Loan Amount", f"${total_loan_amount:,.0f}")
cols[2].metric("Approval Rate", f"{approval_rate:.1f}%")
cols[3].metric("Denial Rate", f"{denial_rate:.1f}%")

cols2 = st.columns(3)
cols2[0].metric("Average Loan Amount", f"${avg_loan_amount:,.0f}")
cols2[1].metric("Average Applicant Income", f"${avg_income:,.0f}")
cols2[2].metric("High-Risk Applications", f"{high_risk_count:,}")

# --- Trend Analysis ------------------------------------------------------------
st.header("Trend Analysis")
monthly = (
    filtered.groupby("year_month")
    .agg(
        total_applications=("application_id", "count"),
        approved_applications=("approval_indicator", "sum"),
        total_loan_amount=("loan_amount", "sum"),
    )
    .reset_index()
    .sort_values("year_month")
)
monthly["approval_rate_pct"] = 100 * monthly["approved_applications"] / monthly["total_applications"]

c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(
        px.line(monthly, x="year_month", y="total_applications", title="Monthly Application Volume"),
        use_container_width=True,
    )
with c2:
    st.plotly_chart(
        px.line(monthly, x="year_month", y="approval_rate_pct", title="Approval Rate Over Time (%)"),
        use_container_width=True,
    )
st.plotly_chart(
    px.bar(monthly, x="year_month", y="total_loan_amount", title="Monthly Loan Volume ($)"),
    use_container_width=True,
)

# --- Geographic Analysis --------------------------------------------------------
st.header("Geographic Analysis")
by_state = (
    filtered.groupby("property_state")
    .agg(
        applications=("application_id", "count"),
        approved=("approval_indicator", "sum"),
        avg_loan_amount=("loan_amount", "mean"),
    )
    .reset_index()
)
by_state["approval_rate_pct"] = 100 * by_state["approved"] / by_state["applications"]

top_denial_by_state = (
    filtered[filtered["application_status"] == "Denied"]
    .groupby(["property_state", "denial_reason"])
    .size()
    .reset_index(name="count")
    .sort_values("count", ascending=False)
    .drop_duplicates(subset="property_state")
    .sort_values("property_state")
)

g1, g2 = st.columns(2)
with g1:
    st.plotly_chart(
        px.bar(by_state.sort_values("applications", ascending=False).head(20), x="property_state", y="applications",
               title="Applications by State (Top 20)"),
        use_container_width=True,
    )
with g2:
    st.plotly_chart(
        px.bar(by_state.sort_values("approval_rate_pct", ascending=False).head(20), x="property_state",
               y="approval_rate_pct", title="Approval Rate by State (Top 20)"),
        use_container_width=True,
    )
st.plotly_chart(
    px.bar(by_state.sort_values("avg_loan_amount", ascending=False).head(20), x="property_state",
           y="avg_loan_amount", title="Average Loan Amount by State (Top 20)"),
    use_container_width=True,
)
with st.expander("Top denial reason by state"):
    st.dataframe(top_denial_by_state[["property_state", "denial_reason", "count"]], use_container_width=True)

# --- Lender and Product Analysis -------------------------------------------------
st.header("Lender and Product Analysis")
by_lender = (
    filtered.groupby("lender_name")
    .agg(applications=("application_id", "count"), approved=("approval_indicator", "sum"))
    .reset_index()
)
by_lender["approval_rate_pct"] = 100 * by_lender["approved"] / by_lender["applications"]
by_product = filtered.groupby("loan_type").agg(loan_volume=("loan_amount", "sum"), applications=("application_id", "count")).reset_index()

l1, l2 = st.columns(2)
with l1:
    st.plotly_chart(
        px.bar(by_lender.sort_values("applications", ascending=False).head(15), x="lender_name", y="applications",
               title="Top Lenders by Application Volume"),
        use_container_width=True,
    )
with l2:
    st.plotly_chart(
        px.bar(by_lender.sort_values("approval_rate_pct", ascending=False), x="lender_name", y="approval_rate_pct",
               title="Approval Rate by Lender"),
        use_container_width=True,
    )
st.plotly_chart(px.pie(by_product, names="loan_type", values="loan_volume", title="Loan Volume by Product"), use_container_width=True)

d1, d2 = st.columns(2)
with d1:
    st.plotly_chart(px.histogram(filtered, x="dti_band", title="Debt-to-Income Distribution",
                                  category_orders={"dti_band": ["<20%", "20-30%", "30-36%", "36-43%", "43%+"]}),
                     use_container_width=True)
with d2:
    st.plotly_chart(px.histogram(filtered, x="ltv_band", title="Loan-to-Value Distribution",
                                  category_orders={"ltv_band": ["<60%", "60-80%", "80-90%", "90-95%", "95%+"]}),
                     use_container_width=True)

st.caption("Data source: DuckDB gold layer (fact_loan_application + dimensions), refreshed by scripts/run_pipeline.py.")
