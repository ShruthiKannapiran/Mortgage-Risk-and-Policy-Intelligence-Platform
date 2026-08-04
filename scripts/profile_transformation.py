import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.common.config import load_config
from src.common.db import get_connection
from src.ingestion.pipeline import BRONZE_TABLE
from src.transformation.cleansing import (
    apply_validation_rules, blank_strings_to_null, deduplicate,
    handle_missing_values, normalize_categoricals, parse_types,
)
from src.transformation.derive import add_derived_fields


def timed(label, fn, *a, **kw):
    start = time.perf_counter()
    result = fn(*a, **kw)
    print(f"{label:<30} {time.perf_counter() - start:6.3f}s")
    return result


cfg = load_config()
con = get_connection()
df = con.execute(f"SELECT * FROM {BRONZE_TABLE}").df()
con.close()

df = timed("blank_strings_to_null", blank_strings_to_null, df)
df = timed("parse_types", parse_types, df)
df = timed("normalize_categoricals", normalize_categoricals, df, cfg["data_quality"]["valid_application_statuses"])

reject_log = []
df, keep_mask, range_flags = timed("apply_validation_rules", apply_validation_rules, df, reject_log, cfg)
df["_flagged_range"] = range_flags
df = df.loc[keep_mask].copy()

df, missing_flags = timed("handle_missing_values", handle_missing_values, df)
df["_flagged_missing"] = missing_flags
was_flagged = df["_flagged_range"].fillna(False) | df["_flagged_missing"].fillna(False)
df = df.drop(columns=["_flagged_range", "_flagged_missing"])

df["_was_flagged_tmp"] = was_flagged
df = timed("deduplicate", deduplicate, df)
was_flagged = df["_was_flagged_tmp"]
df = df.drop(columns=["_was_flagged_tmp"])

df = timed("add_derived_fields", add_derived_fields, df, cfg, was_flagged)
