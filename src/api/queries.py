"""Parameterized SQL for the API's analytics endpoints.

Filters are always applied via bound parameters (`?` placeholders), never by string-
interpolating request input into SQL, to avoid SQL injection from the state/lender/
loan_type/status query parameters.
"""
from __future__ import annotations

import duckdb

BASE_JOIN = """
FROM fact_loan_application f
JOIN dim_property p ON f.property_key = p.property_key
JOIN dim_lender l ON f.lender_key = l.lender_key
JOIN dim_loan_product lp ON f.loan_product_key = lp.loan_product_key
JOIN dim_date d ON f.date_key = d.date_key
"""


def _build_filters(state: str | None, lender: str | None, loan_type: str | None, status: str | None) -> tuple[str, list]:
    conditions = []
    params: list = []
    if state:
        conditions.append("p.property_state = ?")
        params.append(state.strip().upper())
    if lender:
        conditions.append("l.lender_name = ?")
        params.append(lender)
    if loan_type:
        conditions.append("lp.loan_type = ?")
        params.append(loan_type)
    if status:
        conditions.append("f.application_status = ?")
        params.append(status)
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return where_clause, params


def portfolio_summary(
    con: duckdb.DuckDBPyConnection, state: str | None, lender: str | None, loan_type: str | None, status: str | None
) -> dict:
    where_clause, params = _build_filters(state, lender, loan_type, status)
    sql = f"""
        SELECT
            COUNT(*) AS total_applications,
            COALESCE(SUM(f.loan_amount), 0) AS total_requested_loan_amount,
            COALESCE(100.0 * SUM(f.approval_indicator) / NULLIF(COUNT(*), 0), 0) AS approval_rate_pct,
            COALESCE(100.0 * SUM(CASE WHEN f.application_status = 'Denied' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 0) AS denial_rate_pct,
            COALESCE(AVG(f.loan_amount), 0) AS average_loan_amount,
            COALESCE(AVG(f.applicant_income), 0) AS average_applicant_income,
            COALESCE(SUM(f.high_risk_indicator), 0) AS high_risk_application_count
        {BASE_JOIN}
        {where_clause}
    """
    row = con.execute(sql, params).fetchone()
    columns = [
        "total_applications", "total_requested_loan_amount", "approval_rate_pct", "denial_rate_pct",
        "average_loan_amount", "average_applicant_income", "high_risk_application_count",
    ]
    return dict(zip(columns, row))


def portfolio_trends(
    con: duckdb.DuckDBPyConnection, state: str | None, lender: str | None, loan_type: str | None, status: str | None
) -> list[dict]:
    where_clause, params = _build_filters(state, lender, loan_type, status)
    sql = f"""
        SELECT
            d.year_month,
            COUNT(*) AS total_applications,
            SUM(f.approval_indicator) AS approved_applications,
            COALESCE(100.0 * SUM(f.approval_indicator) / NULLIF(COUNT(*), 0), 0) AS approval_rate_pct,
            COALESCE(SUM(f.loan_amount), 0) AS total_loan_amount
        {BASE_JOIN}
        {where_clause}
        GROUP BY d.year_month
        ORDER BY d.year_month
    """
    df = con.execute(sql, params).df()
    return df.to_dict(orient="records")


def latest_pipeline_stages(con: duckdb.DuckDBPyConnection) -> tuple[str | None, list[dict]]:
    latest_run = con.execute(
        "SELECT run_id FROM pipeline_execution_log ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    if latest_run is None:
        return None, []
    run_id = latest_run[0]
    df = con.execute(
        """
        SELECT run_id, stage, started_at, ended_at, status, rows_read, rows_new,
               rows_updated, rows_unchanged, rows_rejected, error_message
        FROM pipeline_execution_log
        WHERE run_id = ?
        ORDER BY started_at
        """,
        [run_id],
    ).df()
    return run_id, df.to_dict(orient="records")
