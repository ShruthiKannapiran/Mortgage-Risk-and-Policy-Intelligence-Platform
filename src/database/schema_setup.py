"""Executes the star-schema DDL scripts against the DuckDB warehouse."""
from __future__ import annotations

from pathlib import Path

import duckdb

from src.common.logging_setup import get_logger

logger = get_logger("database.schema_setup")

DDL_DIR = Path(__file__).resolve().parents[2] / "sql" / "ddl"
DDL_FILES = ["01_dimensions.sql", "02_fact.sql", "03_audit.sql"]


def run_ddl(con: duckdb.DuckDBPyConnection) -> None:
    for filename in DDL_FILES:
        path = DDL_DIR / filename
        sql = path.read_text(encoding="utf-8")
        for statement in filter(None, (s.strip() for s in sql.split(";"))):
            con.execute(statement)
        logger.info("Applied DDL: %s", filename)
