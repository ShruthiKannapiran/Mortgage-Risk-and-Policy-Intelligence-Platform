"""Pipeline execution / audit log helpers (pipeline_execution_log table)."""
from __future__ import annotations

import datetime as dt

import duckdb


def start_stage(con: duckdb.DuckDBPyConnection, run_id: str, stage: str) -> None:
    con.execute(
        """
        INSERT INTO pipeline_execution_log (run_id, stage, started_at, status)
        VALUES (?, ?, ?, 'RUNNING')
        """,
        [run_id, stage, dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)],
    )


def finish_stage(
    con: duckdb.DuckDBPyConnection,
    run_id: str,
    stage: str,
    status: str,
    rows_read: int = 0,
    rows_new: int = 0,
    rows_updated: int = 0,
    rows_unchanged: int = 0,
    rows_rejected: int = 0,
    error_message: str | None = None,
) -> None:
    con.execute(
        """
        UPDATE pipeline_execution_log SET
            ended_at = ?, status = ?, rows_read = ?, rows_new = ?, rows_updated = ?,
            rows_unchanged = ?, rows_rejected = ?, error_message = ?
        WHERE run_id = ? AND stage = ?
        """,
        [
            dt.datetime.now(dt.timezone.utc).replace(tzinfo=None), status, rows_read, rows_new,
            rows_updated, rows_unchanged, rows_rejected, error_message, run_id, stage,
        ],
    )
