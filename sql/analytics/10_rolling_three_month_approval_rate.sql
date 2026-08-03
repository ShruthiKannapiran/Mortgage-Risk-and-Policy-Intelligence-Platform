-- Q10: What is the rolling three-month approval rate?
WITH monthly AS (
    SELECT d.year_month, COUNT(*) AS total_applications, SUM(f.approval_indicator) AS approved_applications
    FROM fact_loan_application f
    JOIN dim_date d ON f.date_key = d.date_key
    GROUP BY d.year_month
)
SELECT
    year_month, total_applications, approved_applications,
    SUM(total_applications) OVER (ORDER BY year_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS rolling_3mo_total_applications,
    SUM(approved_applications) OVER (ORDER BY year_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS rolling_3mo_approved_applications,
    ROUND(100.0 * SUM(approved_applications) OVER (ORDER BY year_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
        / NULLIF(SUM(total_applications) OVER (ORDER BY year_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 0), 2) AS rolling_3mo_approval_rate_pct
FROM monthly
ORDER BY year_month;
