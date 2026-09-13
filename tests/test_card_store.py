import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import cardStore


class CardStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_dir = cardStore.STORE_DIR
        self.original_legacy_path = cardStore.LEGACY_STORE_PATH
        cardStore.STORE_DIR = Path(self.tmp.name) / "cards"
        cardStore.LEGACY_STORE_PATH = Path(self.tmp.name) / "cards.json"

    def tearDown(self):
        cardStore.STORE_DIR = self.original_dir
        cardStore.LEGACY_STORE_PATH = self.original_legacy_path
        self.tmp.cleanup()

    def test_missing_file_returns_default(self):
        self.assertEqual(cardStore.load("todo", {"items": []}), {"items": []})

    def test_save_then_load_round_trips(self):
        cardStore.save("todo", {"items": [{"text": "milk", "done": False}]})
        self.assertEqual(cardStore.load("todo", None), {"items": [{"text": "milk", "done": False}]})

    def test_saving_one_key_does_not_disturb_another(self):
        cardStore.save("todo", {"items": []})
        cardStore.save("note", {"text": "hi"})
        self.assertEqual(cardStore.load("todo", None), {"items": []})
        self.assertEqual(cardStore.load("note", None), {"text": "hi"})

    def test_corrupt_file_falls_back_to_default(self):
        cardStore.STORE_DIR.mkdir(parents=True, exist_ok=True)
        (cardStore.STORE_DIR / "todo.json").write_text("not json")
        self.assertEqual(cardStore.load("todo", "fallback"), "fallback")

    def test_migrates_legacy_shared_file(self):
        cardStore.LEGACY_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        cardStore.LEGACY_STORE_PATH.write_text(
            json.dumps({"todo": {"items": []}, "note": {"text": "hi"}})
        )
        self.assertEqual(cardStore.load("todo", None), {"items": []})
        self.assertEqual(cardStore.load("note", None), {"text": "hi"})
        self.assertFalse(cardStore.LEGACY_STORE_PATH.exists())

    def test_migration_does_not_overwrite_an_existing_new_file(self):
        cardStore.save("todo", {"items": ["fresh"]})
        cardStore.LEGACY_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        cardStore.LEGACY_STORE_PATH.write_text(json.dumps({"todo": {"items": ["stale"]}}))
        self.assertEqual(cardStore.load("todo", None), {"items": ["fresh"]})


if __name__ == "__main__":
    unittest.main()
