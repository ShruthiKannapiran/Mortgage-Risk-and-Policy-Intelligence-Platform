"""Generating sample mortgage application data from two source systems.

Source 1: Core LOS system in CSV format
Source 2: Broker portal system in JSON format

The generated data also contains data quality issues for testing the pipeline.
"""

import json
import numpy as np
import pandas as pd


# Fixed seed to generate the same data every time
SEED = 42
rng = np.random.default_rng(SEED)


def generate_fields(rng, n, source_prefix, data_source_system):
    """Generate clean mortgage application records for one source system."""

    application_ids = [f"APP-{source_prefix}-{i:07d}" for i in range(1, n + 1)]

    start = pd.Timestamp("2022-01-01").value // 10**9
    end = pd.Timestamp("2025-06-30").value // 10**9
    application_dates = pd.to_datetime(rng.integers(start, end, size=n), unit="s")

    # Lognormal: income is right-skewed in reality and must stay positive
    incomes = np.clip(rng.lognormal(mean=11.15, sigma=0.45, size=n), 18_000, 1_500_000)

    # Property value derived from income (not independent) so the two stay correlated
    property_values = incomes * rng.uniform(2.2, 6.5, size=n)
    ltv = np.clip(rng.normal(0.80, 0.14, size=n), 0.35, 1.10)
    loan_amounts = property_values * ltv

    # Weighted, not uniform - real loan-type/status mixes aren't an even split
    loan_types = ["Conventional", "FHA", "VA", "USDA"]
    loan_type = rng.choice(loan_types, size=n, p=[0.60, 0.22, 0.11, 0.07])

    statuses = ["Approved", "Denied", "Withdrawn", "Incomplete"]
    application_status = rng.choice(statuses, size=n, p=[0.55, 0.25, 0.12, 0.08])

    interest_rate = np.clip(rng.normal(6.2, 1.1, size=n), 2.5, 12.0)
    loan_term_months = rng.choice([180, 240, 360], size=n, p=[0.10, 0.10, 0.80])

    states = [
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN",
        "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV",
        "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN",
        "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
    ]

    # Default every state to equal weight, then override only the high-volume ones
    state_weights = np.ones(len(states))
    for state, weight in [("CA", 8.0), ("TX", 6.0), ("FL", 5.0), ("NY", 5.0)]:
        state_weights[states.index(state)] = weight
    state_weights = state_weights / state_weights.sum()
    property_state = rng.choice(states, size=n, p=state_weights)

    county_names = [
        "Washington", "Jefferson", "Franklin", "Lincoln", "Madison",
        "Jackson", "Monroe", "Adams", "Clay", "Union",
    ]
    property_county = [f"{county} County" for county in rng.choice(county_names, size=n)]

    lenders = [
        "Meridian Home Lending", "Crestpoint Mortgage", "Harborview Financial",
        "Summit National Bank", "Bluegrass Mortgage Co", "Riverstone Lending",
        "Northgate Home Loans", "Pinnacle Federal Credit Union", "Cascade Mortgage Group",
        "Ashford Trust Bank",
    ]
    lender = rng.choice(lenders, size=n)

    # Beta distribution: naturally bounded [0, 1], shaped toward realistic DTI levels
    dti = np.clip(rng.beta(2.2, 4.0, size=n) * 0.75 + 0.05, 0.03, 0.85)
    credit_buckets = ["<580", "580-619", "620-659", "660-699", "700-739", "740-779", "780+"]
    credit_score_range = rng.choice(credit_buckets, size=n)

    # denial_reason only applies where status == "Denied"; np.where leaves None elsewhere
    denial_reasons = [
        "Debt-to-income ratio too high", "Credit history", "Collateral",
        "Insufficient income", "Incomplete application",
    ]
    denial_reason = np.where(
        application_status == "Denied",
        rng.choice(denial_reasons, size=n),
        None,
    )

    # Pool smaller than n, sampled with replacement: some applicants apply more than once
    applicant_pool_size = max(1, int(n * 0.85))
    chosen_applicants = rng.choice(np.arange(1, applicant_pool_size + 1), size=n, replace=True)
    applicant_id = [f"APPL-{source_prefix}-{i:07d}" for i in chosen_applicants]

    created_timestamp = application_dates
    processing_days = rng.integers(1, 60, size=n)
    updated_timestamp = created_timestamp + pd.to_timedelta(processing_days, unit="D")

    return pd.DataFrame({
        "application_id": application_ids,
        "application_date": application_dates,
        "applicant_id": applicant_id,
        "applicant_income": np.round(incomes, 2),
        "property_value": np.round(property_values, 2),
        "loan_to_value_ratio": np.round(ltv, 4),
        "loan_amount": np.round(loan_amounts, 2),
        "loan_type": loan_type,
        "application_status": application_status,
        "interest_rate": np.round(interest_rate, 3),
        "loan_term_months": loan_term_months,
        "property_state": property_state,
        "property_county": property_county,
        "lender": lender,
        "debt_to_income_ratio": np.round(dti, 4),
        "credit_score_range": credit_score_range,
        "denial_reason": denial_reason,
        "data_source_system": data_source_system,
        "created_timestamp": created_timestamp,
        "updated_timestamp": updated_timestamp,
    })


def inject_quality_issues(df, rng, is_json_source):
    """Add data quality issues to the generated records."""

    # Creating a copy to avoid changing the original DataFrame
    df = df.copy()
    n = len(df)

    # 1. Missing values
    for col in ["applicant_income", "credit_score_range", "denial_reason", "property_county", "interest_rate"]:
        mask = rng.random(n) < 0.03
        df.loc[mask, col] = None

    # 2. Duplicate records
    duplicate_mask = rng.random(n) < 0.015
    df = pd.concat([df, df.loc[duplicate_mask]], ignore_index=True)
    n = len(df)

    # 3. Invalid dates - convert to object type first to allow invalid string values
    df["application_date"] = df["application_date"].astype(object)
    invalid_dates = ["2023-02-30", "13/45/2024", "not-a-date", ""]
    invalid_date_rows = np.flatnonzero(rng.random(n) < 0.01)
    for row_index in invalid_date_rows:
        df.at[row_index, "application_date"] = rng.choice(invalid_dates)

    # 4. Negative / unrealistic financial values
    for col in ["applicant_income", "loan_amount", "property_value"]:
        mask = rng.random(n) < 0.01
        df.loc[mask, col] = -df.loc[mask, col].abs()

    extreme_rate_mask = rng.random(n) < 0.005
    df.loc[extreme_rate_mask, "interest_rate"] = 999.0

    # 5. Inconsistent casing / whitespace on categorical values
    df["property_state"] = df["property_state"].astype(object)
    state_mask = rng.random(n) < 0.04
    df.loc[state_mask, "property_state"] = df.loc[state_mask, "property_state"].apply(
        lambda value: f" {value.lower()} " if isinstance(value, str) else value
    )

    df["application_status"] = df["application_status"].astype(object)
    status_mask = rng.random(n) < 0.04
    df.loc[status_mask, "application_status"] = df.loc[status_mask, "application_status"].apply(
        lambda value: value.upper() if isinstance(value, str) else value
    )

    # 6. Incorrect data types (JSON source only) - simulates numbers exported as currency strings
    if is_json_source:
        df["loan_amount"] = df["loan_amount"].astype(object)
        string_mask = rng.random(n) < 0.05
        df.loc[string_mask, "loan_amount"] = df.loc[string_mask, "loan_amount"].apply(
            lambda value: f"${value:,.2f}" if pd.notnull(value) else value
        )

    # Shuffling records after adding data quality issues so duplicates aren't clustered
    random_state = int(rng.integers(0, 1_000_000))
    return df.sample(frac=1.0, random_state=random_state).reset_index(drop=True)


def write_csv(df, path):
    """Write the DataFrame to a CSV file."""

    # Creating a copy before formatting timestamps
    output_df = df.copy()

    # Converting timestamp values into ISO format
    for col in ["application_date", "created_timestamp", "updated_timestamp"]:
        output_df[col] = output_df[col].apply(
            lambda value: value.isoformat() if isinstance(value, pd.Timestamp) else value
        )

    output_df.to_csv(path, index=False)
    print(f"Wrote {len(output_df)} rows to {path}")


def write_json(df, path):
    """Write the DataFrame to a JSON file."""

    # Creating a copy before formatting timestamps
    output_df = df.copy()

    # Converting timestamp values into ISO format
    for col in ["application_date", "created_timestamp", "updated_timestamp"]:
        output_df[col] = output_df[col].apply(
            lambda value: value.isoformat() if isinstance(value, pd.Timestamp) else value
        )

    # Converting DataFrame records into JSON-compatible objects
    records = json.loads(output_df.to_json(orient="records"))
    with open(path, "w", encoding="utf-8") as file:
        json.dump(records, file, indent=2)

    print(f"Wrote {len(output_df)} rows to {path}")


if __name__ == "__main__":
    # Number of records required from each source system
    n_core = 150_000
    n_broker = 100_000

    # Generating core LOS records
    core_df = generate_fields(rng, n_core, source_prefix="C", data_source_system="LOS-CORE")
    core_df = inject_quality_issues(core_df, rng, is_json_source=False)
    write_csv(core_df, "data/raw/mortgage_applications_core.csv")

    # Generating broker portal records
    broker_df = generate_fields(rng, n_broker, source_prefix="B", data_source_system="BROKER-PORTAL")
    broker_df = inject_quality_issues(broker_df, rng, is_json_source=True)
    write_json(broker_df, "data/raw/mortgage_applications_broker.json")

    # Calculating duplicate and total record counts
    core_duplicates = len(core_df) - n_core
    broker_duplicates = len(broker_df) - n_broker
    duplicates_total = core_duplicates + broker_duplicates
    unique_total = n_core + n_broker
    combined_total = len(core_df) + len(broker_df)

    print(f"\nUnique applications: {unique_total:,}")
    print(f"Duplicate rows injected: {duplicates_total:,} (core: {core_duplicates:,}, broker: {broker_duplicates:,})")
    print(f"Combined total rows written: {combined_total:,}")