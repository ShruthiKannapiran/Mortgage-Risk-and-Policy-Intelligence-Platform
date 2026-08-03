-- Q7: What percentage of applications have high debt-to-income or loan-to-value ratios?
SELECT
    COUNT(*)                                                                      AS total_applications,
    SUM(CASE WHEN debt_to_income_ratio >= 0.43 THEN 1 ELSE 0 END)                 AS high_dti_count,
    ROUND(100.0 * SUM(CASE WHEN debt_to_income_ratio >= 0.43 THEN 1 ELSE 0 END) / COUNT(*), 2) AS high_dti_pct,
    SUM(CASE WHEN loan_to_value_ratio >= 0.95 THEN 1 ELSE 0 END)                  AS high_ltv_count,
    ROUND(100.0 * SUM(CASE WHEN loan_to_value_ratio >= 0.95 THEN 1 ELSE 0 END) / COUNT(*), 2)  AS high_ltv_pct,
    SUM(CASE WHEN debt_to_income_ratio >= 0.43 OR loan_to_value_ratio >= 0.95 THEN 1 ELSE 0 END) AS high_dti_or_ltv_count,
    ROUND(100.0 * SUM(CASE WHEN debt_to_income_ratio >= 0.43 OR loan_to_value_ratio >= 0.95 THEN 1 ELSE 0 END) / COUNT(*), 2) AS high_dti_or_ltv_pct
FROM fact_loan_application;
