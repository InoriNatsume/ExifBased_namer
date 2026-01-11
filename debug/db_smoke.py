import sqlite3
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 3:
        print("사용법: python debug\\db_smoke.py <db_path> <schema.sql>")
        return

    db_path = Path(sys.argv[1]).expanduser().resolve()
    schema_path = Path(sys.argv[2]).expanduser().resolve()

    if not schema_path.exists():
        print(f"스키마 파일 없음: {schema_path}")
        return

    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        schema_sql = schema_path.read_text(encoding="utf-8")
        conn.executescript(schema_sql)
        cursor = conn.execute("SELECT schema_version FROM meta")
        version = cursor.fetchone()[0]
        print(f"DB OK: {db_path} (schema_version={version})")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
