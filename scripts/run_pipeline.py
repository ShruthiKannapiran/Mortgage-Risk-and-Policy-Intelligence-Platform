#!/usr/bin/env python3
"""End-to-end pipeline orchestrator: ingest -> profile -> transform -> load gold -> data quality."""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.common.db import get_connection
from src.common.logging_setup import get_logger
from src.database.incremental import load_gold
from src.database.schema_setup import run_ddl
from src.ingestion.pipeline import run_ingestion
from src.quality.checks import run_data_quality_checks
from src.quality.profiling import profile_bronze, write_report
from src.transformation.pipeline import run_transformation

logger = get_logger("run_pipeline")


def main() -> None:
    run_id = str(uuid.uuid4())
    logger.info("=== Pipeline run %s starting ===", run_id)

    con = get_connection()
    run_ddl(con)
    con.close()

    run_ingestion()
    report = profile_bronze()
    write_report(report)

    run_transformation()

    con = get_connection()
    silver_df = con.execute("SELECT * FROM silver_loan_application").df()
    load_result = load_gold(con, silver_df, run_id=run_id)
    con.close()
    logger.info(
        "Gold load: %s new, %s updated, %s unchanged",
        load_result.rows_new, load_result.rows_updated, load_result.rows_unchanged,
    )

    dq_report = run_data_quality_checks()
    logger.info(
        "Data quality: overall_status=%s, %s/%s checks passed",
        dq_report["overall_status"], dq_report["checks_passed"], dq_report["checks_total"],
    )

    logger.info("=== Pipeline run %s complete ===", run_id)


if __name__ == "__main__":
    main()
