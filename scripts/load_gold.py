import datetime as dt
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common.db import get_connection
from src.common.logging_setup import get_logger
from src.database.schema_setup import run_ddl
from src.database.dimensions import refresh_dim_date, refresh_dims_from_silver, resolve_surrogate_keys

logger = get_logger("load_gold")

FACT_COLUMNS = [
    "application_id", "date_key", "applicant_key", "property_key", "lender_key",
    "loan_product_key", "applicant_income", "loan_amount", "property_value",
    "interest_rate", "debt_to_income_ratio", "loan_to_value_ratio",
    "application_processing_days", "application_status", "denial_reason", "income_band",
    "loan_amount_band", "dti_band", "ltv_band", "approval_indicator", "high_risk_indicator",
    "data_quality_status", "data_source_system", "application_date", "created_timestamp",
    "updated_timestamp", "source_file", "row_hash", "loaded_at",
]


def main():
    con = get_connection()
    run_ddl(con)

    silver_df = con.execute("SELECT * FROM silver_loan_application").df()

    refresh_dim_date(con)
    refresh_dims_from_silver(con, silver_df)
    resolved = resolve_surrogate_keys(con, silver_df)

    hash_source_cols = [c for c in FACT_COLUMNS if c not in ("application_id", "row_hash", "loaded_at")]
    resolved["row_hash"] = pd.util.hash_pandas_object(resolved[hash_source_cols], index=False).astype(str)
    resolved["loaded_at"] = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

    con.execute("DELETE FROM fact_loan_application")
    con.register("fact_stage", resolved[FACT_COLUMNS])
    con.execute(f"INSERT INTO fact_loan_application ({', '.join(FACT_COLUMNS)}) SELECT {', '.join(FACT_COLUMNS)} FROM fact_stage")
    con.unregister("fact_stage")

    count = con.execute("SELECT COUNT(*) FROM fact_loan_application").fetchone()[0]
    con.close()
    logger.info(f"Gold load complete: {count} rows in fact_loan_application")


if __name__ == "__main__":
    main()