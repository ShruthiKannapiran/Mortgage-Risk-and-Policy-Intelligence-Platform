"""Builds/refreshes the dimension tables and resolves surrogate keys for the fact load.

All dimensions use a Type-1 (overwrite) slowly-changing-dimension approach: attributes
such as lender name or property state/county are treated as stable descriptors rather
than history-tracked facts for this exercise. dim_applicant is the dimension most likely
to become Type 2 in a real system (to track a borrower's income/credit tier changing
over time across multiple applications) — documented as a future improvement.
"""
from __future__ import annotations

import duckdb
import pandas as pd

from src.common.logging_setup import get_logger

logger = get_logger("database.dimensions")


def _upsert_simple_dim(
    con: duckdb.DuckDBPyConnection,
    table: str,
    key_col: str,
    natural_key_cols: list[str],
    values_df: pd.DataFrame,
) -> None:
    """Insert any natural-key combinations from values_df that aren't already present."""
    if values_df.empty:
        return
    con.register("incoming_dim", values_df)
    existing_max = con.execute(f"SELECT COALESCE(MAX({key_col}), 0) FROM {table}").fetchone()[0]
    join_cond = " AND ".join(f"t.{c} = i.{c}" for c in natural_key_cols)
    new_rows = con.execute(
        f"""
        SELECT DISTINCT {', '.join(f'i.{c}' for c in natural_key_cols)}
        FROM incoming_dim i
        LEFT JOIN {table} t ON {join_cond}
        WHERE t.{key_col} IS NULL
        """
    ).df()
    if not new_rows.empty:
        new_rows[key_col] = range(existing_max + 1, existing_max + 1 + len(new_rows))
        con.register("new_dim_rows", new_rows)
        cols = [key_col] + natural_key_cols
        con.execute(f"INSERT INTO {table} ({', '.join(cols)}) SELECT {', '.join(cols)} FROM new_dim_rows")
        con.unregister("new_dim_rows")
        logger.info("Inserted %s new row(s) into %s", len(new_rows), table)
    con.unregister("incoming_dim")


def refresh_dim_date(con: duckdb.DuckDBPyConnection, min_date: str = "2018-01-01", max_date: str = "2026-12-31") -> None:
    count = con.execute("SELECT COUNT(*) FROM dim_date").fetchone()[0]
    if count > 0:
        return
    con.execute(
        f"""
        INSERT INTO dim_date
        SELECT
            CAST(strftime(d, '%Y%m%d') AS INTEGER) AS date_key,
            d AS full_date,
            EXTRACT(year FROM d) AS year,
            EXTRACT(quarter FROM d) AS quarter,
            EXTRACT(month FROM d) AS month,
            strftime(d, '%B') AS month_name,
            strftime(d, '%Y-%m') AS year_month,
            EXTRACT(day FROM d) AS day_of_month,
            EXTRACT(dow FROM d) AS day_of_week,
            strftime(d, '%A') AS day_name
        FROM range(DATE '{min_date}', DATE '{max_date}', INTERVAL 1 DAY) AS t(d)
        """
    )
    logger.info("Populated dim_date from %s to %s", min_date, max_date)


def refresh_dims_from_silver(con: duckdb.DuckDBPyConnection, silver_df: pd.DataFrame) -> None:
    applicants = silver_df[["applicant_id", "income_band", "credit_score_range"]].drop_duplicates(
        subset=["applicant_id"], keep="last"
    )
    _upsert_simple_dim(con, "dim_applicant", "applicant_key", ["applicant_id"], applicants[["applicant_id"]])
    con.register("applicant_attrs", applicants)
    con.execute(
        """
        UPDATE dim_applicant d SET
            income_band = a.income_band,
            credit_score_range = a.credit_score_range
        FROM applicant_attrs a
        WHERE d.applicant_id = a.applicant_id
        """
    )
    con.unregister("applicant_attrs")

    properties = silver_df[["property_state", "property_county"]].drop_duplicates()
    _upsert_simple_dim(con, "dim_property", "property_key", ["property_state", "property_county"], properties)

    lenders = silver_df[["lender"]].drop_duplicates().rename(columns={"lender": "lender_name"})
    _upsert_simple_dim(con, "dim_lender", "lender_key", ["lender_name"], lenders)

    products = silver_df[["loan_type", "loan_term_months"]].drop_duplicates()
    _upsert_simple_dim(con, "dim_loan_product", "loan_product_key", ["loan_type", "loan_term_months"], products)


def resolve_surrogate_keys(con: duckdb.DuckDBPyConnection, silver_df: pd.DataFrame) -> pd.DataFrame:
    con.register("silver_stage", silver_df)
    resolved = con.execute(
        """
        SELECT
            s.*,
            CAST(strftime(s.application_date, '%Y%m%d') AS INTEGER) AS date_key,
            a.applicant_key,
            p.property_key,
            l.lender_key,
            lp.loan_product_key
        FROM silver_stage s
        JOIN dim_applicant a ON a.applicant_id = s.applicant_id
        JOIN dim_property p ON p.property_state = s.property_state AND p.property_county = s.property_county
        JOIN dim_lender l ON l.lender_name = s.lender
        JOIN dim_loan_product lp ON lp.loan_type = s.loan_type AND lp.loan_term_months = s.loan_term_months
        """
    ).df()
    con.unregister("silver_stage")
    return resolved