from tests import _bootstrap  # noqa: F401

import sqlite3
import unittest

from core.db.query import (
    count_images,
    count_matches,
    count_tags,
    get_image_meta,
    get_tags_for_path,
    search_by_tags,
)
from core.db.schema import ensure_schema
from core.db.storage import replace_tags, upsert_image


class DbTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        ensure_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_counts_empty(self) -> None:
        self.assertEqual(count_images(self.conn), 0)
        self.assertEqual(count_tags(self.conn), 0)
        self.assertEqual(count_matches(self.conn), 0)

    def test_upsert_and_meta(self) -> None:
        image_id = upsert_image(self.conn, "a.png", 10, 20, None, tags=["t1", "t2"])
        self.assertIsInstance(image_id, int)
        self.assertEqual(count_images(self.conn), 1)
        self.assertEqual(get_image_meta(self.conn, "a.png"), (10, 20))

    def test_get_tags_fallback_to_table(self) -> None:
        image_id = upsert_image(self.conn, "b.png", 1, 2, None, tags=["t1"])
        replace_tags(self.conn, image_id, ["t1"])
        self.conn.execute(
            "UPDATE images SET tags_json = ? WHERE id = ?",
            ("invalid", image_id),
        )
        tags = get_tags_for_path(self.conn, "b.png")
        self.assertEqual(tags, ["t1"])

    def test_search_by_tags(self) -> None:
        image_id = upsert_image(self.conn, "c.png", 1, 2, None, tags=["t1", "t2"])
        replace_tags(self.conn, image_id, ["t1", "t2"])
        other_id = upsert_image(self.conn, "d.png", 1, 2, None, tags=["t1"])
        replace_tags(self.conn, other_id, ["t1"])
        results = search_by_tags(self.conn, ["t1", "t2"])
        self.assertEqual(results, ["c.png"])


if __name__ == "__main__":
    unittest.main()
