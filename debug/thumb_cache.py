import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.cache import cache_stats, ensure_thumbnail, prune_cache, resolve_cache_dir, thumbnail_path
from core.utils import iter_image_files


def _resolve_images(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return [Path(p) for p in iter_image_files(str(input_path))]
    return []


def build_thumbs(
    input_path: Path,
    cache_dir: Path,
    size: int,
    quality: int,
    force: bool,
    limit: int | None,
) -> None:
    images = _resolve_images(input_path)
    if not images:
        print(f"image path not found: {input_path}")
        return

    cache_dir = resolve_cache_dir(cache_dir)
    created = 0
    skipped = 0
    failed = 0

    for idx, path in enumerate(images):
        if limit is not None and idx >= limit:
            break
        thumb_path = thumbnail_path(path, cache_dir)
        if thumb_path.exists() and not force:
            skipped += 1
            continue
        result = ensure_thumbnail(path, cache_dir, size=size, quality=quality, force=force)
        if result is None:
            failed += 1
            print(f"failed: {path}")
        else:
            created += 1

    print(f"done: created={created}, skipped={skipped}, failed={failed}")


def clear_cache(cache_dir: Path) -> None:
    removed = prune_cache(cache_dir, max_files=0)
    print(f"removed: {removed}")


def show_stats(cache_dir: Path) -> None:
    count, total_size = cache_stats(cache_dir)
    print(f"files: {count}")
    print(f"bytes: {total_size} ({total_size / (1024 * 1024):.2f} MB)")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Thumbnail cache debug tool")
    subparsers = parser.add_subparsers(dest="command")

    build_parser = subparsers.add_parser("build", help="Build thumbnails")
    build_parser.add_argument("input", help="Image file or folder")
    build_parser.add_argument("cache", help="Cache folder")
    build_parser.add_argument("--size", type=int, default=256, help="Thumbnail size")
    build_parser.add_argument("--quality", type=int, default=85, help="JPEG quality")
    build_parser.add_argument("--force", action="store_true", help="Overwrite existing")
    build_parser.add_argument("--limit", type=int, default=None, help="Limit count")

    clear_parser = subparsers.add_parser("clear", help="Clear cache")
    clear_parser.add_argument("cache", help="Cache folder")

    stats_parser = subparsers.add_parser("stats", help="Cache stats")
    stats_parser.add_argument("cache", help="Cache folder")

    if len(argv) == 2 and argv[0] not in {"build", "clear", "stats"}:
        return argparse.Namespace(
            command="build",
            input=argv[0],
            cache=argv[1],
            size=256,
            quality=85,
            force=False,
            limit=None,
        )

    return parser.parse_args(argv)


def main() -> None:
    args = parse_args(sys.argv[1:])
    if args.command == "build":
        build_thumbs(
            Path(args.input).expanduser().resolve(),
            Path(args.cache).expanduser().resolve(),
            args.size,
            args.quality,
            args.force,
            args.limit,
        )
        return
    if args.command == "clear":
        clear_cache(Path(args.cache).expanduser().resolve())
        return
    if args.command == "stats":
        show_stats(Path(args.cache).expanduser().resolve())
        return

    print("usage: python debug\\thumb_cache.py build <input> <cache>")


if __name__ == "__main__":
    main()
