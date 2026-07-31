# Data Profiling Report

- Record count: 253,794
- Duplicate rows: 2,846

| Column | Null % | Distinct | Invalid | Min | Max |
|---|---|---|---|---|---|
| application_id | 0.0% | 250000 | 0 | None | None |
| application_date | 0.28% | 247192 | 1911 | 2022-01-01 00:00:54 | 2025-06-29 23:48:29 |
| applicant_id | 0.0% | 147145 | 0 | None | None |
| applicant_income | 2.98% | 239549 | 0 | -416868.81 | 658009.24 |
| property_value | 0.0% | 249507 | 0 | -1292354.09 | 3544017.4 |
| loan_to_value_ratio | 0.0% | 7175 | 0 | 0.35 | 1.1 |
| loan_amount | 0.0% | 249515 | 0 | -1645091.66 | 2668686.7 |
| loan_type | 0.0% | 4 | 0 | None | None |
| application_status | 0.0% | 8 | 0 | None | None |
| interest_rate | 3.08% | 6845 | 0 | 2.5 | 999.0 |
| loan_term_months | 0.0% | 3 | 0 | 180.0 | 360.0 |
| property_state | 0.0% | 102 | 0 | None | None |
| property_county | 2.98% | 11 | 0 | None | None |
| lender | 0.0% | 10 | 0 | None | None |
| debt_to_income_ratio | 0.0% | 6710 | 0 | 0.051 | 0.7781 |
| credit_score_range | 2.98% | 8 | 0 | None | None |
| denial_reason | 75.84% | 6 | 0 | None | None |
| data_source_system | 0.0% | 2 | 0 | None | None |
| created_timestamp | 0.0% | 249733 | 0 | 2022-01-01 00:00:54 | 2025-06-29 23:48:29 |
| updated_timestamp | 0.0% | 249711 | 0 | 2022-01-02 13:06:12 | 2025-08-27 18:42:27 |

## Data-Quality Concerns

- 2846 exact duplicate row(s) found.
- Column 'application_date' has 1911 value(s) that fail type validation.
- Column 'applicant_income' has 2.98% missing values.
- Column 'interest_rate' has 3.08% missing values.
- Column 'property_county' has 2.98% missing values.
- Column 'credit_score_range' has 2.98% missing values.
- Column 'denial_reason' has 75.84% missing values.
