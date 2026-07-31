import pandas as pd

from src.common.config import get_paths
from src.common.db import get_connection
from src.common.logging_setup import get_logger

logger = get_logger("profiling")

# These lists tell the profiler which columns to treat as numbers or dates when
# checking for invalid values - everything else is profiled as plain categorical/text.

NUMERIC_COLUMNS = [
    "applicant_income", "loan_amount", "property_value", "interest_rate",
    "loan_term_months", "debt_to_income_ratio", "loan_to_value_ratio",
]
DATE_COLUMNS = ["application_date", "created_timestamp", "updated_timestamp"]


def profile_bronze():
    """Reads the bronze table and builds a profiling report covering record and
    duplicate counts, null percentages, distinct-value counts, min/max values, and
    invalid-value counts for every column."""
    con = get_connection()
    df = con.execute("SELECT * FROM bronze_loan_application").df()
    con.close()

    record_count = len(df)
    duplicate_count = int(df.duplicated().sum())

    column_reports = {}
    for col in df.columns:
        if col.startswith("_"):
            continue  # skip our own tracking columns, _source_file and _ingestion_timestamp

        series = df[col]
        null_count = int((series.isna() | (series.astype(str).str.strip() == "")).sum())
        distinct_count = int(series.nunique())

        report = {
            "null_count": null_count,
            "null_pct": round(100 * null_count / record_count, 2),
            "distinct_count": distinct_count,
        }

        if col in NUMERIC_COLUMNS:
            # We convert to numbers here so we can compute a min/max and, importantly,
            # catch values that look numeric but are not - such as the "$231,649.84"
            # style strings we deliberately injected into the broker JSON file.
            cleaned = series.astype(str).str.replace(r"[,$]", "", regex=True)
            numeric = pd.to_numeric(cleaned, errors="coerce")
            invalid_count = int(numeric.isna().sum() - null_count)
            report.update({
                "invalid_value_count": max(invalid_count, 0),
                "min": float(numeric.min()) if numeric.notna().any() else None,
                "max": float(numeric.max()) if numeric.notna().any() else None,
                "mean": float(numeric.mean()) if numeric.notna().any() else None,
            })
        elif col in DATE_COLUMNS:
            parsed = pd.to_datetime(series, errors="coerce")
            invalid_count = int(parsed.isna().sum() - null_count)
            report.update({
                "invalid_value_count": max(invalid_count, 0),
                "min": str(parsed.min()) if parsed.notna().any() else None,
                "max": str(parsed.max()) if parsed.notna().any() else None,
            })
        else:
            report.update({"invalid_value_count": 0, "min": None, "max": None})

        column_reports[col] = report

    concerns = []
    if duplicate_count:
        concerns.append(f"{duplicate_count} exact duplicate row(s) found.")
    for col, stats in column_reports.items():
        if stats["null_pct"] > 2:
            concerns.append(f"Column '{col}' has {stats['null_pct']}% missing values.")
        if stats.get("invalid_value_count", 0) > 0:
            concerns.append(f"Column '{col}' has {stats['invalid_value_count']} value(s) that fail type validation.")

    return {
        "record_count": record_count,
        "duplicate_count": duplicate_count,
        "columns": column_reports,
        "concerns": concerns,
    }


def write_report(report):
    """Writes the profiling results to reports/data_profiling_report.md as a
    human-readable table."""
    paths = get_paths()
    reports_dir = paths["reports_dir"]
    reports_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Data Profiling Report",
        "",
        f"- Record count: {report['record_count']:,}",
        f"- Duplicate rows: {report['duplicate_count']:,}",
        "",
        "| Column | Null % | Distinct | Invalid | Min | Max |",
        "|---|---|---|---|---|---|",
    ]
    for col, stats in report["columns"].items():
        lines.append(
            f"| {col} | {stats['null_pct']}% | {stats['distinct_count']} | "
            f"{stats['invalid_value_count']} | {stats['min']} | {stats['max']} |"
        )

    lines += ["", "## Data-Quality Concerns", ""]
    lines += [f"- {c}" for c in report["concerns"]] or ["- None identified."]

    with open(reports_dir / "data_profiling_report.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    logger.info("Wrote profiling report to %s", reports_dir / "data_profiling_report.md")


if __name__ == "__main__":
    report = profile_bronze()
    write_report(report)
