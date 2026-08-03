# Dimensional Model — Star Schema

```mermaid
erDiagram
    fact_loan_application }o--|| dim_date : "date_key"
    fact_loan_application }o--|| dim_applicant : "applicant_key"
    fact_loan_application }o--|| dim_property : "property_key"
    fact_loan_application }o--|| dim_lender : "lender_key"
    fact_loan_application }o--|| dim_loan_product : "loan_product_key"

    fact_loan_application {
        varchar application_id PK
        int date_key FK
        int applicant_key FK
        int property_key FK
        int lender_key FK
        int loan_product_key FK
    }mkdir -p sql/analytics
    dim_date { int date_key PK }
    dim_applicant { int applicant_key PK varchar applicant_id }
    dim_property { int property_key PK varchar property_state varchar property_county }
    dim_lender { int lender_key PK varchar lender_name }
    dim_loan_product { int loan_product_key PK varchar loan_type int loan_term_months }
