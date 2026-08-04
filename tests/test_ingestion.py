"""Tests for schema validation, file readers, and ingestion idempotency."""
from __future__ import annotations

import json

import duckdb
import pandas as pd

from src.ingestion import pipeline as ingestion_pipeline
from src.ingestion.readers import read_csv_source, read_json_source
from src.ingestion.schema import validate_schema

REQUIRED_COLUMNS = [
    "application_id", "application_date", "applicant_id", "applicant_income", "loan_amount",
    "property_value", "loan_type", "interest_rate", "loan_term_months",
    "debt_to_income_ratio", "loan_to_value_ratio", "property_state", "property_county",
    "lender", "application_status", "denial_reason", "credit_score_range",
    "data_source_system", "created_timestamp", "updated_timestamp",
]

SAMPLE_CSV_HEADER = ",".join(REQUIRED_COLUMNS)
SAMPLE_CSV_ROW = (
    "APP-1,2024-01-01,APPL-1,85000,250000,310000,Conventional,6.25,360,0.32,0.81,"
    "TX,Travis County,Meridian Home Lending,Approved,,700-739,LOS-CORE,2024-01-01,2024-01-05"
)


def test_validate_schema_passes_with_all_required_columns():
    df = pd.DataFrame(columns=REQUIRED_COLUMNS)
    result = validate_schema(df, REQUIRED_COLUMNS)
    assert result["is_valid"]
    assert result["missing_columns"] == []


def test_validate_schema_fails_with_missing_columns():
    df = pd.DataFrame(columns=[c for c in REQUIRED_COLUMNS if c not in ("loan_amount", "interest_rate")])
    result = validate_schema(df, REQUIRED_COLUMNS)
    assert not result["is_valid"]
    assert set(result["missing_columns"]) == {"loan_amount", "interest_rate"}


def test_read_csv_source_preserves_malformed_values_as_strings(tmp_path):
    path = tmp_path / "sample.csv"
    path.write_text("application_id,loan_amount\nAPP-1,\"$231,649.84\"\n", encoding="utf-8")
    df = read_csv_source(path)
    assert df.loc[0, "loan_amount"] == "$231,649.84"


def test_read_json_source_preserves_mixed_types(tmp_path):
    path = tmp_path / "sample.json"
    records = [{"application_id": "APP-1", "loan_amount": 250000.0}, {"application_id": "APP-2", "loan_amount": "$99,000.00"}]
    path.write_text(json.dumps(records), encoding="utf-8")
    df = read_json_source(path)
    assert df.loc[0, "loan_amount"] == 250000.0
    assert df.loc[1, "loan_amount"] == "$99,000.00"


def test_run_ingestion_quarantines_rows_missing_application_id(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    rejected_dir = tmp_path / "rejected"
    raw_dir.mkdir()
    warehouse_path = tmp_path / "test.duckdb"

    blank_id_row = SAMPLE_CSV_ROW.replace("APP-1", "", 1)
    (raw_dir / "mortgage_applications_core.csv").write_text(
        f"{SAMPLE_CSV_HEADER}\n{SAMPLE_CSV_ROW}\n{blank_id_row}\n", encoding="utf-8"
    )

    monkeypatch.setattr(ingestion_pipeline, "get_paths", lambda: {"raw_dir": raw_dir, "rejected_dir": rejected_dir})
    monkeypatch.setattr(
        ingestion_pipeline, "get_connection",
        lambda read_only=False: duckdb.connect(str(warehouse_path), read_only=read_only),
    )

    ingestion_pipeline.run_ingestion()

    check_con = duckdb.connect(str(warehouse_path))
    total = check_con.execute(f"SELECT COUNT(*) FROM {ingestion_pipeline.BRONZE_TABLE}").fetchone()[0]
    check_con.close()

    assert total == 1  # the blank-application_id row was quarantined, not loaded
    assert list(rejected_dir.glob("ingestion_rejected_*.csv"))


def test_run_ingestion_is_idempotent_when_rerun_against_the_same_file(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    rejected_dir = tmp_path / "rejected"
    raw_dir.mkdir()
    warehouse_path = tmp_path / "test.duckdb"

    (raw_dir / "mortgage_applications_core.csv").write_text(
        f"{SAMPLE_CSV_HEADER}\n{SAMPLE_CSV_ROW}\n", encoding="utf-8"
    )

    monkeypatch.setattr(ingestion_pipeline, "get_paths", lambda: {"raw_dir": raw_dir, "rejected_dir": rejected_dir})
    monkeypatch.setattr(
        ingestion_pipeline, "get_connection",
        lambda read_only=False: duckdb.connect(str(warehouse_path), read_only=read_only),
    )

    ingestion_pipeline.run_ingestion()
    ingestion_pipeline.run_ingestion()  # re-process the same file

    check_con = duckdb.connect(str(warehouse_path))
    total = check_con.execute(f"SELECT COUNT(*) FROM {ingestion_pipeline.BRONZE_TABLE}").fetchone()[0]
    check_con.close()

    assert total == 1  # not doubled -- this is the exact bug you just fixed
