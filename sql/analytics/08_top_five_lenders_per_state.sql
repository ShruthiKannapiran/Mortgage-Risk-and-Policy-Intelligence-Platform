-- Q8: What are the top five lenders in each state (by application volume)?
WITH lender_state_volume AS (
    SELECT p.property_state, l.lender_name, COUNT(*) AS applications
    FROM fact_loan_application f
    JOIN dim_property p ON f.property_key = p.property_key
    JOIN dim_lender l ON f.lender_key = l.lender_key
    GROUP BY p.property_state, l.lender_name
),
ranked AS (
    SELECT *, DENSE_RANK() OVER (PARTITION BY property_state ORDER BY applications DESC) AS lender_rank
    FROM lender_state_volume
)
SELECT property_state, lender_rank, lender_name, applications
FROM ranked
WHERE lender_rank <= 5
ORDER BY property_state, lender_rank;
