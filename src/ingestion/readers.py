
# Reads both formats as raw strings so type issues surface during validation, not silently during parsing.
import json
import pandas as pd


def read_csv_source(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[])


def read_json_source(path):
    with open(path, "r", encoding="utf-8") as fh:
        records = json.load(fh)
    return pd.DataFrame.from_records(records)


READERS = {"csv": read_csv_source, "json": read_json_source}