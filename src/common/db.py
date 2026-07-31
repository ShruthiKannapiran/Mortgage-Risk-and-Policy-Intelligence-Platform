import duckdb
from src.common.config import get_paths


def get_connection():
    paths = get_paths()
    warehouse_path = paths["warehouse_file"]
    warehouse_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(warehouse_path))