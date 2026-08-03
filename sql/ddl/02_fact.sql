-- Star schema: fact table
-- Grain: one row per mortgage application (application_id), current state
-- (the silver layer already collapses multi-batch updates to the latest version).

CREATE TABLE IF NOT EXISTS fact_loan_application (
    application_id              VARCHAR PRIMARY KEY,
    date_key                    INTEGER NOT NULL REFERENCES dim_date(date_key),
    applicant_key               INTEGER NOT NULL REFERENCES dim_applicant(applicant_key),
    property_key                INTEGER NOT NULL REFERENCES dim_property(property_key),
    lender_key                  INTEGER NOT NULL REFERENCES dim_lender(lender_key),
    loan_product_key            INTEGER NOT NULL REFERENCES dim_loan_product(loan_product_key),

    applicant_income            DOUBLE,
    loan_amount                 DOUBLE,
    property_value              DOUBLE,
    interest_rate                DOUBLE,
    debt_to_income_ratio         DOUBLE,
    loan_to_value_ratio          DOUBLE,
    application_processing_days  DOUBLE,

    application_status           VARCHAR,
    denial_reason                 VARCHAR,
    income_band                   VARCHAR,
    loan_amount_band              VARCHAR,
    dti_band                       VARCHAR,
    ltv_band                       VARCHAR,
    approval_indicator             INTEGER,
    high_risk_indicator             INTEGER,
    data_quality_status             VARCHAR,
    data_source_system               VARCHAR,

    application_date                  TIMESTAMP,
    created_timestamp                  TIMESTAMP,
    updated_timestamp                   TIMESTAMP,
    source_file                          VARCHAR,
    row_hash                              VARCHAR NOT NULL,
    loaded_at                             TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fact_date_key ON fact_loan_application(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_lender_key ON fact_loan_application(lender_key);
CREATE INDEX IF NOT EXISTS idx_fact_property_key ON fact_loan_application(property_key);
