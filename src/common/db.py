"""DuckDB connection helper."""
from __future__ import annotations

from pathlib import Path

import duckdb

from src.common.config import get_paths


def get_connection(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    paths = get_paths()
    warehouse_path: Path = paths["warehouse_file"]
    warehouse_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(warehouse_path), read_only=read_only)
