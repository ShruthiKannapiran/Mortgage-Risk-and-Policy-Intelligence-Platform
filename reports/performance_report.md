# Performance Report

## Baseline Measurement

Performance was measured using:

```bash
python scripts/measure_performance.py
```

### Baseline Results

| Stage          |        Time |
| -------------- | ----------: |
| Ingestion      |     2.069 s |
| Profiling      |     1.818 s |
| Transformation |     3.171 s |
| Gold load      |     0.836 s |
| Data quality   |     0.240 s |
| **Total**      | **8.134 s** |

The transformation stage was the slowest part of the pipeline, so it was selected for further investigation.

---

## Optimization: Vectorized Blank-String Detection

The `blank_strings_to_null` function in `src/transformation/cleansing.py` originally used the following logic:

```python
df[col].apply(
    lambda value: isinstance(value, str) and value.strip() == ""
)
```

This operation was applied to every string-typed column.

Because the bronze table stores nearly all 20 columns as strings, the function executed a Python lambda on approximately 5 million individual cells:

```text
20 columns x 253,794 rows = approximately 5.1 million cells
```

The row-by-row Python operation was replaced with a vectorized pandas comparison:

```python
is_blank = (
    df[col].notna()
    & (df[col].astype(str).str.strip() == "")
)
```

### Before and After

The full transformation stage was measured again using `scripts/measure_performance.py`.

| Measurement         | Transformation Time |
| ------------------- | ------------------: |
| Before optimization |             3.171 s |
| After optimization  |             3.084 s |
| Improvement         |  Approximately 2.7% |

The optimization produced a measurable improvement, but the gain was smaller than expected.

---

## Transformation Sub-Step Profiling

To identify the remaining bottlenecks, each transformation function was measured separately using:

```bash
python scripts/profile_transformation.py
```

### Sub-Step Results

| Transformation Step                   |                    Time |
| ------------------------------------- | ----------------------: |
| `blank_strings_to_null`               |                 0.514 s |
| `parse_types`                         |                 0.650 s |
| `normalize_categoricals`              |                 0.083 s |
| `apply_validation_rules`              |                 0.018 s |
| `handle_missing_values`               |                 0.117 s |
| `deduplicate`                         |                 0.322 s |
| `add_derived_fields`                  |                 0.277 s |
| **Measured transformation functions** |             **1.981 s** |
| DuckDB read and write operations      | **Approximately 1.1 s** |
| **Full transformation stage**         |             **3.084 s** |

The seven cleansing and derivation functions account for approximately `1.981 seconds` of the total `3.084-second` transformation stage.

The remaining `~1.1 seconds` occurs outside these functions, primarily during:

1. Reading the bronze table from DuckDB into a pandas DataFrame:

   ```sql
   SELECT *
   FROM bronze_loan_application;
   ```

2. Writing the transformed pandas DataFrame back into the `silver_loan_application` table.

---

## Findings

At the current dataset size of 253,794 rows, the cost of transferring data between DuckDB and pandas is comparable to, or greater than, several parts of the transformation logic itself.

The vectorized blank-string detection reduces Python-level per-cell processing and provides a real performance improvement. However, further optimization of individual pandas functions is likely to produce diminishing returns while the full dataset continues to move between DuckDB and pandas.

---

## Conclusion

The blank-string optimization reduced transformation time from `3.171 seconds` to `3.084 seconds`, an improvement of approximately `2.7%`.

The profiling results show that the larger performance opportunity is reducing DuckDB-to-pandas and pandas-to-DuckDB data transfers.

Future optimization work should focus on:

* Performing more transformations directly in DuckDB using SQL.
* Reading only the columns required for each transformation.
* Avoiding unnecessary DataFrame copies.
* Combining transformation steps where possible.
* Reducing the number of times data moves between DuckDB and pandas.
* Comparing the current pandas pipeline with a DuckDB-native transformation approach.

The main finding is that Python-level vectorization helps, but reducing data serialization and round-trip overhead is likely to provide the largest future performance improvement.
