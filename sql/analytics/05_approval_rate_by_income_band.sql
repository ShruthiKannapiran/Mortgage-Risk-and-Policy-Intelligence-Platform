-- Q5: How does approval rate vary across income bands?
SELECT
    a.income_band,
    COUNT(*)                                                  AS total_applications,
    SUM(f.approval_indicator)                                 AS approved_applications,
    ROUND(100.0 * SUM(f.approval_indicator) / COUNT(*), 2)    AS approval_rate_pct
FROM fact_loan_application f
JOIN dim_applicant a ON f.applicant_key = a.applicant_key
GROUP BY a.income_band
ORDER BY
    CASE a.income_band
        WHEN '<50K' THEN 1 WHEN '50K-100K' THEN 2 WHEN '100K-150K' THEN 3
        WHEN '150K-250K' THEN 4 WHEN '250K+' THEN 5 ELSE 6
    END;
