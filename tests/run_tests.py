from __future__ import annotations

import sys
from pathlib import Path
import unittest


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def main() -> None:
    loader = unittest.TestLoader()
    suite = loader.discover(
        start_dir=str(ROOT_DIR / "tests"),
        pattern="test_*.py",
        top_level_dir=str(ROOT_DIR),
    )
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)


if __name__ == "__main__":
    main()
