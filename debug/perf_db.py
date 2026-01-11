import argparse
import os
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import sqlite3

from core.db.query import count_images, count_matches, count_tags, search_by_tags
from core.normalize.novelai import split_novelai_tags


def parse_args(argv: list[str]) -> argparse.Namespace:
    default_db = os.environ.get("NAI_DB_PATH", str(ROOT_DIR / "data" / "app.sqlite"))
    parser = argparse.ArgumentParser(description="Perf: DB stats and search timing")
    parser.add_argument("--db", default=default_db, help="SQLite path (default: env NAI_DB_PATH)")
    parser.add_argument("--tags", default="", help="Required tags, comma separated")
    parser.add_argument("--limit", type=int, default=2000, help="Search limit")
    parser.add_argument("--offset", type=int, default=0, help="Search offset")
    parser.add_argument("--repeat", type=int, default=5, help="Repeat count for timing")
    parser.add_argument("--verbose", action="store_true", help="Print per-run timings")
    parser.add_argument("--explain", action="store_true", help="Print query plan")
    parser.add_argument("--selectivity", action="store_true", help="Print tag selectivity stats")
    return parser.parse_args(argv)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if pct <= 0:
        return min(values)
    if pct >= 100:
        return max(values)
    ordered = sorted(values)
    k = (len(ordered) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return ordered[f]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def build_query(required: list[str]) -> tuple[str, list]:
    placeholders = ", ".join("?" for _ in required)
    query = f"""
        SELECT images.path
        FROM images
        JOIN tags ON tags.image_id = images.id
        WHERE tags.tag IN ({placeholders})
        GROUP BY images.id
        HAVING COUNT(DISTINCT tags.tag) = ?
        ORDER BY images.path
        LIMIT ? OFFSET ?
    """
    params = [*required, len(required)]
    return query, params


def count_by_tags(conn: sqlite3.Connection, required: list[str]) -> int:
    placeholders = ", ".join("?" for _ in required)
    query = f"""
        SELECT COUNT(*) FROM (
            SELECT images.id
            FROM images
            JOIN tags ON tags.image_id = images.id
            WHERE tags.tag IN ({placeholders})
            GROUP BY images.id
            HAVING COUNT(DISTINCT tags.tag) = ?
        ) AS matched
    """
    params = [*required, len(required)]
    row = conn.execute(query, params).fetchone()
    return int(row[0]) if row else 0


def main() -> None:
    args = parse_args(sys.argv[1:])
    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        print(f"db not found: {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        images = count_images(conn)
        tags = count_tags(conn)
        matches = count_matches(conn)
    finally:
        conn.close()

    print(f"db: {db_path}")
    print(f"images: {images}, tags: {tags}, matches: {matches}")

    required = split_novelai_tags(args.tags)
    if not required:
        return

    if args.explain:
        conn = sqlite3.connect(str(db_path))
        try:
            query, params = build_query(required)
            plan_rows = conn.execute(
                "EXPLAIN QUERY PLAN " + query,
                [*params, args.limit, args.offset],
            ).fetchall()
        finally:
            conn.close()
        print("query plan:")
        for row in plan_rows:
            detail = row[3] if len(row) > 3 else row[-1]
            print(f"  - {detail}")

    if args.selectivity:
        conn = sqlite3.connect(str(db_path))
        try:
            total = count_images(conn)
            per_tag = {}
            for tag in required:
                row = conn.execute(
                    "SELECT COUNT(DISTINCT image_id) FROM tags WHERE tag = ?",
                    (tag,),
                ).fetchone()
                per_tag[tag] = int(row[0]) if row else 0
            intersection = count_by_tags(conn, required)
        finally:
            conn.close()
        print("selectivity:")
        for tag, cnt in per_tag.items():
            ratio = (cnt / total * 100.0) if total else 0.0
            print(f"  - {tag}: {cnt} ({ratio:.2f}%)")
        ratio = (intersection / total * 100.0) if total else 0.0
        print(f"  - AND(all): {intersection} ({ratio:.2f}%)")

    times: list[float] = []
    total_results = 0

    wall_start = time.perf_counter()
    for idx in range(args.repeat):
        conn = sqlite3.connect(str(db_path))
        try:
            t0 = time.perf_counter()
            results = search_by_tags(conn, required, limit=args.limit, offset=args.offset)
            t1 = time.perf_counter()
        finally:
            conn.close()
        elapsed = (t1 - t0) * 1000.0
        times.append(elapsed)
        total_results = len(results)
        if args.verbose:
            print(f"run {idx + 1}: {elapsed:.2f} ms, results={len(results)}")

    wall_elapsed = time.perf_counter() - wall_start
    qps = args.repeat / wall_elapsed if wall_elapsed > 0 else 0.0
    avg = sum(times) / len(times)
    print(f"required tags: {required}")
    print(f"results: {total_results}")
    print(f"avg: {avg:.2f} ms, min: {min(times):.2f} ms, max: {max(times):.2f} ms")
    print(f"p50: {percentile(times, 50):.2f} ms, p95: {percentile(times, 95):.2f} ms")
    print(f"throughput: {qps:.2f} queries/sec")


if __name__ == "__main__":
    main()
