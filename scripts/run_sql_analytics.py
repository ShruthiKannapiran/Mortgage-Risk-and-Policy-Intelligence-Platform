import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common.db import get_connection

ANALYTICS_DIR = Path(__file__).resolve().parents[1] / "sql" / "analytics"


def main():
    con = get_connection()
    for path in sorted(ANALYTICS_DIR.glob("*.sql")):
        print(f"\n=== {path.name} ===")
        sql = path.read_text(encoding="utf-8")
        try:
            df = con.execute(sql).df()
            print(df.head(8).to_string(index=False))
            print(f"... ({len(df)} row(s) total)")
        except Exception as exc:
            print(f"ERROR: {exc}")
    con.close()


if __name__ == "__main__":
    main()
