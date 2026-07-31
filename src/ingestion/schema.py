def validate_schema(df, required_columns):
    missing = [col for col in required_columns if col not in df.columns]
    return {"is_valid": len(missing) == 0, "missing_columns": missing}
