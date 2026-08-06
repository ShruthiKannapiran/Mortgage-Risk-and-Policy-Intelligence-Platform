import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "config.yaml"

load_dotenv(REPO_ROOT / ".env", override=False)


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def get_paths():
    cfg = load_config()
    paths = {key: REPO_ROOT / value for key, value in cfg["paths"].items()}
    warehouse_override = os.getenv("MORTGAGE_WAREHOUSE_PATH")
    if warehouse_override:
        paths["warehouse_file"] = REPO_ROOT / warehouse_override
    return paths


def get_env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)
