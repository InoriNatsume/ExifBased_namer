import argparse
import json
from pathlib import Path
import sys

def _find_root(start: Path) -> Path:
    for parent in [start, *start.parents]:
        if (parent / "core").is_dir():
            return parent
    return start


ROOT_DIR = _find_root(Path(__file__).resolve().parent)
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.extract import extract_payloads_from_image
from core.normalize import merge_prompt_tags, normalize_novelai_payload


def _dedupe(tags: list[str]) -> list[str]:
    seen = set()
    output = []
    for tag in tags:
        cleaned = " ".join(tag.split()).strip()
        if not cleaned or cleaned in seen:
            continue
        output.append(cleaned)
        seen.add(cleaned)
    return output


def inspect_image(path: str, include_negative: bool, show_keys: bool, dump_payload: bool) -> None:
    payloads = extract_payloads_from_image(path)
    if not payloads:
        print(f"{path} -> NO_PAYLOAD")
        return

    combined: list[str] = []
    for index, payload in enumerate(payloads, start=1):
        if show_keys:
            keys = ", ".join(sorted(payload.keys()))
            print(f"{path} -> payload[{index}] keys: {keys}")
        if dump_payload:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        normalized = normalize_novelai_payload(payload)
        combined.extend(merge_prompt_tags(normalized, include_negative=include_negative))

    tags = _dedupe(combined)
    if not tags:
        print(f"{path} -> payloads={len(payloads)} NO_TAGS")
        return

    print(f"{path} -> payloads={len(payloads)} tags={len(tags)}")
    for tag in tags:
        print(f"  - {tag}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect normalized NAI tags from images.")
    parser.add_argument("paths", nargs="+", help="Image file paths")
    parser.add_argument("--include-negative", action="store_true")
    parser.add_argument("--show-payload-keys", action="store_true")
    parser.add_argument("--dump-payload", action="store_true")
    args = parser.parse_args()

    for raw in args.paths:
        inspect_image(
            str(Path(raw)),
            include_negative=args.include_negative,
            show_keys=args.show_payload_keys,
            dump_payload=args.dump_payload,
        )


if __name__ == "__main__":
    main()
