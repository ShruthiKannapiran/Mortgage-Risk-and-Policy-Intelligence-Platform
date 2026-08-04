"""Tests for the incremental gold-layer load: new/updated/unchanged classification,
idempotent reruns, and the audit table."""
from __future__ import annotations

import duckdb
import pytest

from src.database.incremental import load_gold


@pytest.fixture
def con():
    connection = duckdb.connect(":memory:")
    yield connection
    connection.close()


def test_first_load_marks_all_rows_new(con, silver_df_factory):
    df = silver_df_factory([{"application_id": "APP-1"}, {"application_id": "APP-2"}])
    result = load_gold(con, df, run_id="run-1")
    assert result.rows_new == 2
    assert result.rows_updated == 0
    assert result.rows_unchanged == 0


def test_rerunning_with_identical_data_is_idempotent(con, silver_df_factory):
    df = silver_df_factory([{"application_id": "APP-1"}, {"application_id": "APP-2"}])
    load_gold(con, df, run_id="run-1")
    fact_count_after_first = con.execute("SELECT COUNT(*) FROM fact_loan_application").fetchone()[0]

    result = load_gold(con, df, run_id="run-2")

    assert result.rows_new == 0
    assert result.rows_updated == 0
    assert result.rows_unchanged == 2
    fact_count_after_second = con.execute("SELECT COUNT(*) FROM fact_loan_application").fetchone()[0]
    assert fact_count_after_second == fact_count_after_first == 2


def test_changed_row_is_detected_as_updated_not_duplicated(con, silver_df_factory):
    df_v1 = silver_df_factory([{"application_id": "APP-1", "application_status": "Incomplete", "approval_indicator": 0}])
    load_gold(con, df_v1, run_id="run-1")

    df_v2 = silver_df_factory([{"application_id": "APP-1", "application_status": "Approved", "approval_indicator": 1}])
    result = load_gold(con, df_v2, run_id="run-2")

    assert result.rows_new == 0
    assert result.rows_updated == 1
    assert result.rows_unchanged == 0

    row = con.execute("SELECT application_status FROM fact_loan_application WHERE application_id = 'APP-1'").fetchone()
    assert row[0] == "Approved"
    total = con.execute("SELECT COUNT(*) FROM fact_loan_application WHERE application_id = 'APP-1'").fetchone()[0]
    assert total == 1  # updated in place, not appended as a second row


def test_mixed_new_updated_unchanged_batch(con, silver_df_factory):
    load_gold(con, silver_df_factory([
        {"application_id": "APP-1", "application_status": "Approved"},
        {"application_id": "APP-2", "application_status": "Denied"},
    ]), run_id="run-1")

    result = load_gold(con, silver_df_factory([
        {"application_id": "APP-1", "application_status": "Approved"},   # unchanged
        {"application_id": "APP-2", "application_status": "Withdrawn"},  # updated
        {"application_id": "APP-3", "application_status": "Incomplete"}, # new
    ]), run_id="run-2")

    assert result.rows_new == 1
    assert result.rows_updated == 1
    assert result.rows_unchanged == 1


def test_pipeline_execution_log_records_the_run(con, silver_df_factory):
    df = silver_df_factory([{"application_id": "APP-1"}])
    load_gold(con, df, run_id="run-xyz")
    row = con.execute(
        "SELECT status, rows_new, rows_updated, rows_unchanged FROM pipeline_execution_log WHERE run_id = ?",
        ["run-xyz"],
    ).fetchone()
    assert row == ("SUCCESS", 1, 0, 0)
