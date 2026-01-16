from tests import _bootstrap  # noqa: F401

import sqlite3
import unittest

from core.db.query import (
    count_images,
    count_matches,
    count_tags,
    get_image_meta,
    get_tags_for_path,
    get_template,
    get_preset,
    list_presets,
    list_templates,
    search_by_tags,
)
from core.db.schema import ensure_schema
from core.db.storage import (
    delete_preset,
    delete_template,
    replace_tags,
    save_preset,
    upsert_image,
    upsert_template,
)


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
        image_id = upsert_image(
            self.conn,
            "a.png",
            10,
            20,
            None,
            tags_pos=["t1", "t2"],
            tags_neg=[],
            tags_char=[],
        )
        self.assertIsInstance(image_id, int)
        self.assertEqual(count_images(self.conn), 1)
        self.assertEqual(get_image_meta(self.conn, "a.png"), (10, 20))

    def test_get_tags_fallback_to_table(self) -> None:
        image_id = upsert_image(
            self.conn,
            "b.png",
            1,
            2,
            None,
            tags_pos=[],
            tags_neg=[],
            tags_char=[],
        )
        replace_tags(self.conn, image_id, [("t1", "pos", None)])
        self.conn.execute(
            "UPDATE images SET tags_json = ? WHERE id = ?",
            ("invalid", image_id),
        )
        tags = get_tags_for_path(self.conn, "b.png")
        self.assertEqual(tags, ["t1"])

    def test_search_by_tags(self) -> None:
        image_id = upsert_image(
            self.conn,
            "c.png",
            1,
            2,
            None,
            tags_pos=["t1", "t2"],
            tags_neg=[],
            tags_char=[],
        )
        replace_tags(self.conn, image_id, [("t1", "pos", None), ("t2", "pos", None)])
        other_id = upsert_image(
            self.conn,
            "d.png",
            1,
            2,
            None,
            tags_pos=["t1"],
            tags_neg=[],
            tags_char=[],
        )
        replace_tags(self.conn, other_id, [("t1", "pos", None)])
        results = search_by_tags(self.conn, ["t1", "t2"])
        self.assertEqual(results, ["c.png"])

    def test_template_roundtrip(self) -> None:
        template_id = upsert_template(
            self.conn,
            "main",
            {"name": "main", "variables": []},
        )
        self.assertIsInstance(template_id, int)
        listed = list_templates(self.conn)
        self.assertTrue(any(item["name"] == "main" for item in listed))
        fetched = get_template(self.conn, name="main")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["name"], "main")
        self.assertEqual(fetched["payload"]["name"], "main")
        self.assertTrue(delete_template(self.conn, "main"))

    def test_preset_roundtrip(self) -> None:
        preset_id = save_preset(
            self.conn,
            name="emo-pack",
            source_kind="nais",
            variable_name="emotion",
            payload={
                "name": "emo-pack",
                "source_kind": "nais",
                "variable_name": "emotion",
                "values": [{"name": "angry", "tags": ["tag1"]}],
            },
        )
        self.assertIsInstance(preset_id, int)
        listed = list_presets(self.conn)
        self.assertTrue(any(item["id"] == preset_id for item in listed))
        fetched = get_preset(self.conn, preset_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["name"], "emo-pack")
        self.assertTrue(delete_preset(self.conn, preset_id))


if __name__ == "__main__":
    unittest.main()
