-- Q6: Which lenders experienced the largest month-over-month change (in application volume)?
WITH monthly_lender_volume AS (
    SELECT l.lender_name, d.year_month, COUNT(*) AS applications
    FROM fact_loan_application f
    JOIN dim_lender l ON f.lender_key = l.lender_key
    JOIN dim_date d ON f.date_key = d.date_key
    GROUP BY l.lender_name, d.year_month
),
with_change AS (
    SELECT lender_name, year_month, applications,
        LAG(applications) OVER (PARTITION BY lender_name ORDER BY year_month) AS prior_month_applications
    FROM monthly_lender_volume
)
SELECT lender_name, year_month, applications, prior_month_applications,
    applications - prior_month_applications AS change_in_applications,
    ROUND(100.0 * (applications - prior_month_applications) / NULLIF(prior_month_applications, 0), 2) AS pct_change
FROM with_change
WHERE prior_month_applications IS NOT NULL
ORDER BY ABS(applications - prior_month_applications) DESC
LIMIT 20;
