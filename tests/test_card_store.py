import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import cardStore


class CardStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_path = cardStore.STORE_PATH
        cardStore.STORE_PATH = Path(self.tmp.name) / "cards.json"

    def tearDown(self):
        cardStore.STORE_PATH = self.original_path
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
        cardStore.STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        cardStore.STORE_PATH.write_text("not json")
        self.assertEqual(cardStore.load("todo", "fallback"), "fallback")


if __name__ == "__main__":
    unittest.main()
