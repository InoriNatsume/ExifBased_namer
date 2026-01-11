import hashlib
import sys
from pathlib import Path

from PIL import Image


def _thumb_name(path: Path) -> str:
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()
    return f"{digest}.jpg"


def main() -> None:
    if len(sys.argv) < 3:
        print("사용법: python debug\\thumb_cache.py <이미지 경로> <캐시 폴더>")
        return

    image_path = Path(sys.argv[1]).expanduser().resolve()
    cache_dir = Path(sys.argv[2]).expanduser().resolve()
    if not image_path.exists():
        print(f"이미지 없음: {image_path}")
        return

    cache_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = cache_dir / _thumb_name(image_path)

    try:
        img = Image.open(image_path)
        img.thumbnail((256, 256))
        img.save(thumb_path, "JPEG", quality=85)
        print(f"생성됨: {thumb_path}")
    except Exception as exc:
        print(f"실패: {exc}")


if __name__ == "__main__":
    main()
