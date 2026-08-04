"""Automated data-quality framework, run against the gold layer after each pipeline run."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.common.config import get_paths, load_config
from src.common.db import get_connection
from src.common.logging_setup import get_logger
from src.ingestion.pipeline import BRONZE_TABLE

logger = get_logger("quality.checks")

FACT_TABLE = "fact_loan_application"
SILVER_TABLE = "silver_loan_application"

REQUIRED_NON_NULL_COLUMNS = [
    "application_id", "application_date", "loan_amount", "applicant_income",
    "property_value", "loan_product_key", "application_status",
]


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str


@dataclass
class DataQualityReport:
    generated_at: str
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def checks_passed(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def checks_total(self) -> int:
        return len(self.checks)

    @property
    def overall_status(self) -> str:
        return "PASS" if all(c.passed for c in self.checks) else "FAIL"

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "overall_status": self.overall_status,
            "checks_passed": self.checks_passed,
            "checks_total": self.checks_total,
            "checks": [c.__dict__ for c in self.checks],
        }


def _check_required_columns(fact_df: pd.DataFrame) -> CheckResult:
    missing = [c for c in REQUIRED_NON_NULL_COLUMNS if c not in fact_df.columns]
    return CheckResult(
        "required_columns_present", passed=not missing,
        details="all required columns present" if not missing else f"missing columns: {missing}",
    )


def _check_nulls(fact_df: pd.DataFrame) -> CheckResult:
    null_counts = {c: int(fact_df[c].isna().sum()) for c in REQUIRED_NON_NULL_COLUMNS if c in fact_df.columns}
    bad = {c: n for c, n in null_counts.items() if n > 0}
    return CheckResult(
        "no_nulls_in_required_columns", passed=not bad,
        details="no nulls found" if not bad else f"null counts: {bad}",
    )


def _check_duplicate_application_ids(fact_df: pd.DataFrame) -> CheckResult:
    dup_count = int(fact_df["application_id"].duplicated().sum())
    return CheckResult(
        "no_duplicate_application_ids", passed=dup_count == 0,
        details="no duplicates" if dup_count == 0 else f"{dup_count} duplicate application_id(s) found",
    )


def _check_date_ranges(fact_df: pd.DataFrame, cfg: dict) -> CheckResult:
    min_date = pd.Timestamp(cfg["data_quality"]["min_application_date"])
    max_date = pd.Timestamp.now() + pd.Timedelta(days=cfg["data_quality"]["max_future_days"])
    dates = pd.to_datetime(fact_df["application_date"])
    out_of_range = int(((dates < min_date) | (dates > max_date)).sum())
    return CheckResult(
        "valid_date_ranges", passed=out_of_range == 0,
        details="all dates in range" if out_of_range == 0 else f"{out_of_range} row(s) outside [{min_date.date()}, {max_date.date()}]",
    )


def _check_accepted_status_values(fact_df: pd.DataFrame, cfg: dict) -> CheckResult:
    valid = set(cfg["data_quality"]["valid_application_statuses"])
    invalid_count = int((~fact_df["application_status"].isin(valid)).sum())
    return CheckResult(
        "accepted_status_values", passed=invalid_count == 0,
        details="all statuses valid" if invalid_count == 0 else f"{invalid_count} row(s) with unrecognized status",
    )


def _check_positive_financials(fact_df: pd.DataFrame) -> CheckResult:
    bad = int(((fact_df["loan_amount"] <= 0) | (fact_df["applicant_income"] <= 0) | (fact_df["property_value"] <= 0)).sum())
    return CheckResult(
        "positive_loan_and_income_values", passed=bad == 0,
        details="all positive" if bad == 0 else f"{bad} row(s) with non-positive financial values",
    )


def _check_dti_ltv_ranges(fact_df: pd.DataFrame, cfg: dict) -> CheckResult:
    dq = cfg["data_quality"]
    bad = int(
        (
            (fact_df["debt_to_income_ratio"] < dq["min_dti"]) | (fact_df["debt_to_income_ratio"] > dq["max_dti"])
            | (fact_df["loan_to_value_ratio"] < dq["min_ltv"]) | (fact_df["loan_to_value_ratio"] > dq["max_ltv"])
        ).sum()
    )
    return CheckResult(
        "dti_ltv_within_range", passed=bad == 0,
        details="all within range" if bad == 0 else f"{bad} row(s) with out-of-range DTI/LTV",
    )


def _check_referential_integrity(con) -> CheckResult:
    orphans = con.execute(
        f"""
        SELECT
            (SELECT COUNT(*) FROM {FACT_TABLE} f LEFT JOIN dim_applicant a ON f.applicant_key = a.applicant_key WHERE a.applicant_key IS NULL)
            + (SELECT COUNT(*) FROM {FACT_TABLE} f LEFT JOIN dim_property p ON f.property_key = p.property_key WHERE p.property_key IS NULL)
            + (SELECT COUNT(*) FROM {FACT_TABLE} f LEFT JOIN dim_lender l ON f.lender_key = l.lender_key WHERE l.lender_key IS NULL)
            + (SELECT COUNT(*) FROM {FACT_TABLE} f LEFT JOIN dim_loan_product lp ON f.loan_product_key = lp.loan_product_key WHERE lp.loan_product_key IS NULL)
            + (SELECT COUNT(*) FROM {FACT_TABLE} f LEFT JOIN dim_date d ON f.date_key = d.date_key WHERE d.date_key IS NULL)
        """
    ).fetchone()[0]
    return CheckResult(
        "referential_integrity", passed=orphans == 0,
        details="all foreign keys resolve" if orphans == 0 else f"{orphans} orphaned fact row reference(s)",
    )


def _check_row_count_reconciliation(con) -> CheckResult:
    silver_count = con.execute(f"SELECT COUNT(DISTINCT application_id) FROM {SILVER_TABLE}").fetchone()[0]
    fact_count = con.execute(f"SELECT COUNT(*) FROM {FACT_TABLE}").fetchone()[0]
    return CheckResult(
        "source_to_target_row_reconciliation", passed=silver_count == fact_count,
        details=(
            f"silver={silver_count}, fact={fact_count} (match)" if silver_count == fact_count
            else f"MISMATCH: silver={silver_count}, fact={fact_count}"
        ),
    )


def _check_rejected_record_threshold(cfg: dict) -> CheckResult:
    paths = get_paths()
    rejected_dir: Path = paths["rejected_dir"]
    transform_reject_path = rejected_dir / "transformation_rejected.csv"
    con = get_connection(read_only=True)
    bronze_count = con.execute(f"SELECT COUNT(*) FROM {BRONZE_TABLE}").fetchone()[0]
    con.close()

    rejected_count = 0
    if transform_reject_path.exists():
        rejected_count = len(pd.read_csv(transform_reject_path))

    rate = rejected_count / bronze_count if bronze_count else 0.0
    threshold = cfg["data_quality"]["max_rejected_rate"]
    return CheckResult(
        "rejected_record_rate_within_threshold", passed=rate <= threshold,
        details=f"rejected {rejected_count}/{bronze_count} ({rate:.2%}), threshold {threshold:.0%}",
    )


def run_data_quality_checks() -> dict:
    cfg = load_config()
    con = get_connection(read_only=True)
    fact_df = con.execute(f"SELECT * FROM {FACT_TABLE}").df()

    report = DataQualityReport(generated_at=datetime.now(timezone.utc).isoformat())
    report.checks.append(_check_required_columns(fact_df))
    report.checks.append(_check_nulls(fact_df))
    report.checks.append(_check_duplicate_application_ids(fact_df))
    report.checks.append(_check_date_ranges(fact_df, cfg))
    report.checks.append(_check_accepted_status_values(fact_df, cfg))
    report.checks.append(_check_positive_financials(fact_df))
    report.checks.append(_check_dti_ltv_ranges(fact_df, cfg))
    report.checks.append(_check_referential_integrity(con))
    report.checks.append(_check_row_count_reconciliation(con))
    con.close()
    report.checks.append(_check_rejected_record_threshold(cfg))

    _write_report(report)
    return report.to_dict()


def _write_report(report: DataQualityReport) -> None:
    paths = get_paths()
    reports_dir: Path = paths["reports_dir"]
    reports_dir.mkdir(parents=True, exist_ok=True)

    report_dict = report.to_dict()
    with open(reports_dir / "data_quality_report.json", "w", encoding="utf-8") as fh:
        json.dump(report_dict, fh, indent=2)

    lines = [
        "# Data Quality Report",
        "",
        f"Generated at: {report.generated_at}",
        f"Overall status: **{report.overall_status}** ({report.checks_passed}/{report.checks_total} checks passed)",
        "",
        "| Check | Status | Details |",
        "|---|---|---|",
    ]
    for check in report.checks:
        status = "PASS" if check.passed else "FAIL"
        lines.append(f"| {check.name} | {status} | {check.details} |")

    with open(reports_dir / "data_quality_report.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    logger.info("Data quality report written to %s (%s)", reports_dir, report.overall_status)


if __name__ == "__main__":
    run_data_quality_checks()
