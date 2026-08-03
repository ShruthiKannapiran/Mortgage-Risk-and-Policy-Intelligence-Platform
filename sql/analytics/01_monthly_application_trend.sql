-- Q1: What is the monthly application and approval trend?
SELECT
    d.year_month,
    COUNT(*)                                                   AS total_applications,
    SUM(f.approval_indicator)                                  AS approved_applications,
    ROUND(100.0 * SUM(f.approval_indicator) / COUNT(*), 2)     AS approval_rate_pct
FROM fact_loan_application f
JOIN dim_date d ON f.date_key = d.date_key
GROUP BY d.year_month
ORDER BY d.year_month;
