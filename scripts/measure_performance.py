#!/usr/bin/env python3
"""Times each pipeline stage against the full dataset and prints a breakdown."""
from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.common.db import get_connection
from src.database.incremental import load_gold
from src.database.schema_setup import run_ddl
from src.ingestion.pipeline import run_ingestion
from src.quality.checks import run_data_quality_checks
from src.quality.profiling import profile_bronze, write_report
from src.transformation.pipeline import run_transformation


def timed(label, fn, *args, **kwargs):
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed = time.perf_counter() - start
    print(f"{label:<20} {elapsed:8.3f}s")
    return result, elapsed


def profiling_stage():
    report = profile_bronze()
    write_report(report)


def main() -> None:
    timings = {}

    con = get_connection()
    run_ddl(con)
    con.close()

    _, timings["ingestion"] = timed("ingestion", run_ingestion)
    _, timings["profiling"] = timed("profiling", profiling_stage)
    _, timings["transformation"] = timed("transformation", run_transformation)

    con = get_connection()
    silver_df = con.execute("SELECT * FROM silver_loan_application").df()
    _, timings["gold_load"] = timed("gold_load", load_gold, con, silver_df, str(uuid.uuid4()))
    con.close()

    _, timings["data_quality"] = timed("data_quality", run_data_quality_checks)

    print("\nTotal:", f"{sum(timings.values()):.3f}s")
    slowest = max(timings, key=timings.get)
    print(f"Slowest stage: {slowest} ({timings[slowest]:.3f}s)")


if __name__ == "__main__":
    main()