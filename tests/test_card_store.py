import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import card_store


class CardStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_path = card_store.STORE_PATH
        card_store.STORE_PATH = Path(self.tmp.name) / "cards.json"

    def tearDown(self):
        card_store.STORE_PATH = self.original_path
        self.tmp.cleanup()

    def test_missing_file_returns_default(self):
        self.assertEqual(card_store.load("todo", {"items": []}), {"items": []})

    def test_save_then_load_round_trips(self):
        card_store.save("todo", {"items": [{"text": "milk", "done": False}]})
        self.assertEqual(card_store.load("todo", None), {"items": [{"text": "milk", "done": False}]})

    def test_saving_one_key_does_not_disturb_another(self):
        card_store.save("todo", {"items": []})
        card_store.save("note", {"text": "hi"})
        self.assertEqual(card_store.load("todo", None), {"items": []})
        self.assertEqual(card_store.load("note", None), {"text": "hi"})

    def test_corrupt_file_falls_back_to_default(self):
        card_store.STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        card_store.STORE_PATH.write_text("not json")
        self.assertEqual(card_store.load("todo", "fallback"), "fallback")


if __name__ == "__main__":
    unittest.main()
