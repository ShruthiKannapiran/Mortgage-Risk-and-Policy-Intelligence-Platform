-- Q9: Which applications have duplicate or conflicting information?
-- Run against bronze (raw), since gold already resolves each application_id to one
-- current version -- this surfaces the raw conflicts the pipeline had to reconcile.
WITH raw_versions AS (
    SELECT
        application_id,
        COUNT(*)                                       AS version_count,
        COUNT(DISTINCT application_status)              AS distinct_statuses,
        COUNT(DISTINCT loan_amount)                     AS distinct_loan_amounts,
        COUNT(DISTINCT _source_file)                     AS distinct_source_files
    FROM bronze_loan_application
    GROUP BY application_id
    HAVING COUNT(*) > 1
)
SELECT application_id, version_count, distinct_statuses, distinct_loan_amounts, distinct_source_files,
    CASE WHEN distinct_statuses > 1 OR distinct_loan_amounts > 1 THEN 'Conflicting information'
         ELSE 'Exact duplicate delivery' END AS conflict_type
FROM raw_versions
ORDER BY distinct_statuses DESC, distinct_loan_amounts DESC, version_count DESC;
