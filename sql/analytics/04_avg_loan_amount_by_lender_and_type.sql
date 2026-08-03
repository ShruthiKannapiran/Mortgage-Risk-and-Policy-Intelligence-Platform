-- Q4: What is the average loan amount by lender and loan type?
SELECT
    l.lender_name,
    lp.loan_type,
    COUNT(*)                              AS applications,
    ROUND(AVG(f.loan_amount), 2)          AS avg_loan_amount,
    ROUND(MEDIAN(f.loan_amount), 2)       AS median_loan_amount
FROM fact_loan_application f
JOIN dim_lender l ON f.lender_key = l.lender_key
JOIN dim_loan_product lp ON f.loan_product_key = lp.loan_product_key
GROUP BY l.lender_name, lp.loan_type
ORDER BY l.lender_name, lp.loan_type;
