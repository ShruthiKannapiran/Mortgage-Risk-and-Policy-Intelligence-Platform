# Data Quality Report

Generated at: 2026-08-04T21:02:06.770784+00:00
Overall status: **PASS** (10/10 checks passed)

| Check | Status | Details |
|---|---|---|
| required_columns_present | PASS | all required columns present |
| no_nulls_in_required_columns | PASS | no nulls found |
| no_duplicate_application_ids | PASS | no duplicates |
| valid_date_ranges | PASS | all dates in range |
| accepted_status_values | PASS | all statuses valid |
| positive_loan_and_income_values | PASS | all positive |
| dti_ltv_within_range | PASS | all within range |
| referential_integrity | PASS | all foreign keys resolve |
| source_to_target_row_reconciliation | PASS | silver=238952, fact=238952 (match) |
| rejected_record_rate_within_threshold | PASS | rejected 11356/253794 (4.47%), threshold 15% |
