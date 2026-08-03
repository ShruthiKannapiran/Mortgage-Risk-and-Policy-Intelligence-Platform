-- Star schema: dimension tables (DuckDB dialect)

CREATE TABLE IF NOT EXISTS dim_date (
    date_key        INTEGER PRIMARY KEY,   -- YYYYMMDD
    full_date       DATE NOT NULL,
    year            INTEGER NOT NULL,
    quarter         INTEGER NOT NULL,
    month           INTEGER NOT NULL,
    month_name      VARCHAR NOT NULL,
    year_month      VARCHAR NOT NULL,      -- 'YYYY-MM', convenient for trend queries
    day_of_month    INTEGER NOT NULL,
    day_of_week     INTEGER NOT NULL,
    day_name        VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_applicant (
    applicant_key   INTEGER PRIMARY KEY,
    applicant_id    VARCHAR NOT NULL UNIQUE,
    income_band     VARCHAR,
    credit_score_range VARCHAR
);

CREATE TABLE IF NOT EXISTS dim_property (
    property_key    INTEGER PRIMARY KEY,
    property_state  VARCHAR NOT NULL,
    property_county VARCHAR NOT NULL,
    UNIQUE (property_state, property_county)
);

CREATE TABLE IF NOT EXISTS dim_lender (
    lender_key      INTEGER PRIMARY KEY,
    lender_name     VARCHAR NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dim_loan_product (
    loan_product_key INTEGER PRIMARY KEY,
    loan_type         VARCHAR NOT NULL,
    loan_term_months  INTEGER NOT NULL,
    UNIQUE (loan_type, loan_term_months)
);
