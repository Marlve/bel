import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import calendarNudgeCopy as copy


class ToneTests(unittest.TestCase):
    def test_casual_pluralizes_multiple_items(self):
        self.assertEqual(
            copy.casual(2, "Friday"),
            "hey — two things due before Friday. want them in your list?",
        )

    def test_casual_singular(self):
        self.assertEqual(
            copy.casual(1, "Friday"),
            "hey — one thing due before Friday. want them in your list?",
        )

    def test_plain_pluralizes_multiple_items(self):
        self.assertEqual(copy.plain(2, "Friday"), "Two assignments are due before Friday.")

    def test_plain_singular(self):
        self.assertEqual(copy.plain(1, "Friday"), "One assignment is due before Friday.")

    def test_terse(self):
        self.assertEqual(copy.terse(2, "Fri"), "2 due · by Fri")

    def test_default_tone_is_plain(self):
        self.assertEqual(copy.sentence(2, "Friday"), copy.plain(2, "Friday"))


class SourceLineTests(unittest.TestCase):
    def test_singular_item(self):
        self.assertEqual(copy.source_line(1), "from calendar · 1 item")

    def test_plural_items(self):
        self.assertEqual(copy.source_line(2), "from calendar · 2 items")


if __name__ == "__main__":
    unittest.main()
