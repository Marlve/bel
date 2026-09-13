# Pure logic behind the Settings wedge: where it pins in the ring, and how
# the editable (other) wedges round-trip through cardStore.

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cardStore
import wedgeConfig


class BottomPinIndexTests(unittest.TestCase):
    def test_exact_at_even_counts(self):
        # wedge_index() in pieMenu.py: 0 = up, going clockwise. For an even
        # count, compass-down (180°) always lands exactly on one wedge.
        self.assertEqual(wedgeConfig.bottom_pin_index(2), 1)
        self.assertEqual(wedgeConfig.bottom_pin_index(4), 2)
        self.assertEqual(wedgeConfig.bottom_pin_index(6), 3)

    def test_nearest_at_odd_counts(self):
        # No wedge sits exactly at 180° for an odd count - this just has to
        # be deterministic, not exact.
        self.assertEqual(wedgeConfig.bottom_pin_index(3), 2)
        self.assertEqual(wedgeConfig.bottom_pin_index(5), 2)


class FullConfigTests(unittest.TestCase):
    def test_settings_lands_at_the_bottom_index_among_the_others(self):
        others = [{"id": "todo", "label": "Todo"}, {"id": "note", "label": "Note"}, {"id": "claude", "label": "Claude"}]
        config = wedgeConfig.full_config(others)
        self.assertEqual([entry["id"] for entry in config], ["todo", "note", "settings", "claude"])

    def test_settings_still_pins_near_the_bottom_with_fewer_others(self):
        others = [{"id": "todo", "label": "Todo"}]
        config = wedgeConfig.full_config(others)
        self.assertEqual([entry["id"] for entry in config], ["todo", "settings"])

    def test_does_not_mutate_the_shared_settings_entry(self):
        others = [{"id": "todo", "label": "Todo"}]
        config = wedgeConfig.full_config(others)
        settings_entry = next(entry for entry in config if entry["id"] == "settings")
        settings_entry["label"] = "Mutated"
        self.assertEqual(wedgeConfig.SETTINGS_ENTRY["label"], "Settings")


class ResolveTests(unittest.TestCase):
    def test_merges_each_action_own_extra_config(self):
        resolved = wedgeConfig.resolve([{"id": "claude", "label": "Claude"}, {"id": "todo", "label": "Todo"}])
        self.assertEqual(resolved[0]["placeholder"], "Ask Bel anything…")
        self.assertNotIn("placeholder", resolved[1])

    def test_does_not_mutate_the_input_entry(self):
        entry = {"id": "claude", "label": "Claude"}
        wedgeConfig.resolve([entry])
        self.assertNotIn("placeholder", entry)


class PersistenceTests(unittest.TestCase):
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

    def test_loading_with_nothing_saved_returns_the_defaults(self):
        self.assertEqual(wedgeConfig.load_other_wedges(), wedgeConfig.DEFAULT_OTHER_WEDGES)

    def test_defaults_are_copied_not_shared(self):
        loaded = wedgeConfig.load_other_wedges()
        loaded[0]["label"] = "Mutated"
        self.assertEqual(wedgeConfig.DEFAULT_OTHER_WEDGES[0]["label"], "Todo")

    def test_save_then_load_round_trips(self):
        entries = [{"id": "note", "label": "Notes"}, {"id": "todo", "label": "Todo"}, {"id": "claude", "label": "AI"}]
        wedgeConfig.save_other_wedges(entries)
        self.assertEqual(wedgeConfig.load_other_wedges(), entries)


if __name__ == "__main__":
    unittest.main()
