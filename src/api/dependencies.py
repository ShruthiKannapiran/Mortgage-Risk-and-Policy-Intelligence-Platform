"""Shared FastAPI dependencies: a per-request read-only DuckDB connection."""
from __future__ import annotations

from collections.abc import Iterator

import duckdb

from src.common.db import get_connection


def get_db() -> Iterator[duckdb.DuckDBPyConnection]:
    con = get_connection(read_only=True)
    try:
        yield con
    finally:
        con.close()
