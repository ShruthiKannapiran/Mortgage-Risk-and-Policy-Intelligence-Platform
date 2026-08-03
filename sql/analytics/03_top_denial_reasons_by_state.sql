-- Q3: What are the top denial reasons by state?
WITH denial_counts AS (
    SELECT p.property_state, f.denial_reason, COUNT(*) AS denial_count
    FROM fact_loan_application f
    JOIN dim_property p ON f.property_key = p.property_key
    WHERE f.application_status = 'Denied'
    GROUP BY p.property_state, f.denial_reason
),
ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY property_state ORDER BY denial_count DESC) AS rn
    FROM denial_counts
)
SELECT property_state, denial_reason, denial_count
FROM ranked
WHERE rn = 1
ORDER BY denial_count DESC;
