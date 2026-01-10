from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from nais_builder.builder import build_nais_from_folder, save_nais


def _progress(processed: int, total: int) -> None:
    print(f"진행 {processed}/{total}")


def main() -> None:
    if len(sys.argv) < 2:
        print("사용법: 폴더를 이 파일로 드래그 앤 드롭하거나,")
        print('python tests\\build_nais_dragdrop.py "C:\\경로\\폴더"')
        return

    folder = Path(sys.argv[1]).expanduser().resolve()
    if not folder.is_dir():
        print(f"폴더가 아닙니다: {folder}")
        return

    output = None
    if len(sys.argv) >= 3:
        output = Path(sys.argv[2]).expanduser().resolve()
    else:
        output = folder / f"NAIS_{folder.name}.json"

    try:
        payload, stats = build_nais_from_folder(
            folder,
            include_negative=False,
            progress_step=200,
            progress_cb=_progress,
        )
    except Exception as exc:
        print(f"실패: {exc}")
        return

    save_nais(output, payload)

    print(f"완료: {output}")
    print(f"이미지 수: {stats['total']}")
    print(f"공통 태그 수: {stats['common_count']}")
    print(f"빈 고유 태그: {stats['empty_unique']}")
    if stats["common_tags"]:
        sample = ", ".join(stats["common_tags"][:30])
        print(f"공통 태그 샘플(최대 30개): {sample}")


if __name__ == "__main__":
    main()
