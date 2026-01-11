import argparse
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.extract.payload import extract_payloads_from_image
from core.normalize.novelai import merge_prompt_tags, normalize_novelai_payload
from core.utils import iter_image_files


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Perf: extract/normalize timings")
    parser.add_argument("input", help="Image file or folder")
    parser.add_argument("--limit", type=int, default=None, help="Limit image count")
    parser.add_argument("--include-negative", action="store_true", help="Include negative tags")
    parser.add_argument("--verbose", action="store_true", help="Print per-image stats")
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


def resolve_images(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return [Path(p) for p in iter_image_files(str(input_path))]
    return []


def main() -> None:
    args = parse_args(sys.argv[1:])
    input_path = Path(args.input).expanduser().resolve()
    images = resolve_images(input_path)
    if args.limit is not None:
        images = images[: args.limit]
    if not images:
        print(f"no images: {input_path}")
        return

    total_payload_time = 0.0
    total_norm_time = 0.0
    total_merge_time = 0.0
    total_time = 0.0
    payload_times: list[float] = []
    norm_times: list[float] = []
    merge_times: list[float] = []
    total_times: list[float] = []
    total_payloads = 0
    total_tags = 0
    errors = 0

    wall_start = time.perf_counter()

    for idx, path in enumerate(images):
        t0 = time.perf_counter()
        try:
            payloads = extract_payloads_from_image(str(path))
        except Exception as exc:
            errors += 1
            if args.verbose:
                print(f"error: {path} ({exc})")
            continue
        t1 = time.perf_counter()

        norm_time = 0.0
        merge_time = 0.0
        tags_count = 0
        for payload in payloads:
            n0 = time.perf_counter()
            normalized = normalize_novelai_payload(payload)
            n1 = time.perf_counter()
            tags = merge_prompt_tags(normalized, include_negative=args.include_negative)
            n2 = time.perf_counter()
            norm_time += n1 - n0
            merge_time += n2 - n1
            tags_count += len(tags)

        t2 = time.perf_counter()

        payload_time = t1 - t0
        total_payload_time += payload_time
        total_norm_time += norm_time
        total_merge_time += merge_time
        total_time += t2 - t0
        payload_times.append(payload_time * 1000.0)
        norm_times.append(norm_time * 1000.0)
        merge_times.append(merge_time * 1000.0)
        total_times.append((t2 - t0) * 1000.0)
        total_payloads += len(payloads)
        total_tags += tags_count

        if args.verbose:
            print(
                f"[{idx+1}/{len(images)}] {path} "
                f"payloads={len(payloads)} tags={tags_count} "
                f"payload={payload_time*1000:.2f}ms norm={norm_time*1000:.2f}ms "
                f"merge={merge_time*1000:.2f}ms total={(t2-t0)*1000:.2f}ms"
            )

    count = len(images) - errors
    if count <= 0:
        print("no successful images")
        return

    wall_elapsed = time.perf_counter() - wall_start
    img_per_sec = count / wall_elapsed if wall_elapsed > 0 else 0.0
    tags_per_sec = total_tags / wall_elapsed if wall_elapsed > 0 else 0.0

    print(f"images: {count}, errors: {errors}")
    print(f"avg payloads: {total_payloads / count:.2f}")
    print(f"avg tags: {total_tags / count:.2f}")
    print(f"avg payload: {(total_payload_time / count) * 1000:.2f} ms")
    print(f"avg normalize: {(total_norm_time / count) * 1000:.2f} ms")
    print(f"avg merge: {(total_merge_time / count) * 1000:.2f} ms")
    print(f"avg total: {(total_time / count) * 1000:.2f} ms")
    print(f"p50 payload: {percentile(payload_times, 50):.2f} ms")
    print(f"p95 payload: {percentile(payload_times, 95):.2f} ms")
    print(f"p50 normalize: {percentile(norm_times, 50):.2f} ms")
    print(f"p95 normalize: {percentile(norm_times, 95):.2f} ms")
    print(f"p50 merge: {percentile(merge_times, 50):.2f} ms")
    print(f"p95 merge: {percentile(merge_times, 95):.2f} ms")
    print(f"p50 total: {percentile(total_times, 50):.2f} ms")
    print(f"p95 total: {percentile(total_times, 95):.2f} ms")
    print(f"throughput: {img_per_sec:.2f} images/sec, {tags_per_sec:.2f} tags/sec")


if __name__ == "__main__":
    main()
