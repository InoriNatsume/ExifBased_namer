import json
import sys


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            error = {"type": "error", "message": f"invalid json: {exc}"}
            print(json.dumps(error, ensure_ascii=False), flush=True)
            continue
        print(json.dumps({"type": "echo", "payload": payload}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
