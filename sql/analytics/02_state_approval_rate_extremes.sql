-- Q2: Which states have the highest and lowest approval rates?
WITH state_stats AS (
    SELECT
        p.property_state,
        COUNT(*)                                                AS total_applications,
        SUM(f.approval_indicator)                               AS approved_applications,
        ROUND(100.0 * SUM(f.approval_indicator) / COUNT(*), 2)  AS approval_rate_pct
    FROM fact_loan_application f
    JOIN dim_property p ON f.property_key = p.property_key
    GROUP BY p.property_state
    HAVING COUNT(*) >= 100
),
ranked AS (
    SELECT *,
        RANK() OVER (ORDER BY approval_rate_pct DESC) AS rank_highest,
        RANK() OVER (ORDER BY approval_rate_pct ASC)  AS rank_lowest
    FROM state_stats
)
SELECT property_state, total_applications, approved_applications, approval_rate_pct,
       CASE WHEN rank_highest <= 5 THEN 'Top 5 highest' ELSE 'Bottom 5 lowest' END AS category
FROM ranked
WHERE rank_highest <= 5 OR rank_lowest <= 5
ORDER BY approval_rate_pct DESC;
