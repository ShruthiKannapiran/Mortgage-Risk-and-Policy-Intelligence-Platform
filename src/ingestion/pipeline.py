import datetime as dt

from src.common.config import get_paths, load_config
from src.common.db import get_connection
from src.common.logging_setup import get_logger
from src.ingestion.readers import READERS
from src.ingestion.schema import validate_schema

logger = get_logger("ingestion")

BRONZE_TABLE = "bronze_loan_application"

# Loads valid source records into Bronze layer and saves rejected rows.

def run_ingestion():
    cfg = load_config()
    paths = get_paths()
    raw_dir = paths["raw_dir"]
    rejected_dir = paths["rejected_dir"]
    rejected_dir.mkdir(parents=True, exist_ok=True)
    required_columns = cfg["ingestion"]["required_columns"]

    con = get_connection()
    total_loaded = 0
    total_rejected = 0

    for source in cfg["ingestion"]["sources"]:
        files = sorted(raw_dir.glob(source["pattern"]))
        if not files:
            logger.warning("No files found for source '%s'", source["name"])
            continue

        reader = READERS[source["format"]]

        for path in files:
            logger.info("Reading %s (source=%s)", path.name, source["name"])
            df = reader(path)

            validation = validate_schema(df, required_columns)
            if not validation["is_valid"]:
                logger.error("%s failed schema validation, missing: %s", path.name, validation["missing_columns"])
                continue

            missing_id_mask = df["application_id"].astype(str).str.strip() == ""
            malformed = df.loc[missing_id_mask]
            valid = df.loc[~missing_id_mask].copy()

            if not malformed.empty:
                reject_path = rejected_dir / f"ingestion_rejected_{path.stem}.csv"
                malformed.to_csv(reject_path, index=False)
                logger.warning("Quarantined %s malformed row(s) from %s", len(malformed), path.name)
                total_rejected += len(malformed)

            valid["_source_file"] = path.name
            valid["_ingestion_timestamp"] = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

            con.register("valid_df", valid)
            con.execute(f"CREATE TABLE IF NOT EXISTS {BRONZE_TABLE} AS SELECT * FROM valid_df LIMIT 0")
            con.execute(f"DELETE FROM {BRONZE_TABLE} WHERE _source_file = ?", [path.name])
            con.execute(f"INSERT INTO {BRONZE_TABLE} SELECT * FROM valid_df")
            con.unregister("valid_df")


            logger.info("Loaded %s row(s) from %s into %s", len(valid), path.name, BRONZE_TABLE)
            total_loaded += len(valid)

    con.close()
    logger.info("Ingestion complete: %s row(s) loaded, %s row(s) rejected", total_loaded, total_rejected)


if __name__ == "__main__":
    run_ingestion()