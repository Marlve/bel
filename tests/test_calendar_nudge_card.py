import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from calendarNudgeCard import CalendarNudgeCard
from calendarNudgeState import QUIET, NUDGE, EXPANDED

ITEMS = [{"title": "Essay draft", "due": "Fri"}]


class CalendarNudgeCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.card = CalendarNudgeCard(motion=False)
        self.addCleanup(self.card.deleteLater)

    def test_starts_quiet_at_rail_width(self):
        self.assertEqual(self.card.driver.state.state, QUIET)
        self.assertEqual(self.card.width(), style_rail_size())

    def test_show_nudge_builds_the_default_tone_sentence_and_widens(self):
        self.card.showNudge(ITEMS, "Friday")
        self.assertEqual(self.card.driver.state.state, NUDGE)
        self.assertEqual(self.card.driver.state.sentence, "One assignment is due before Friday.")
        self.assertEqual(self.card.driver.state.source, "from calendar · 1 item")
        self.assertGreater(self.card.width(), 5)

    def test_hover_expands_and_grows_taller(self):
        self.card.showNudge(ITEMS, "Friday")
        nudge_height = self.card.height()
        self.card.enterEvent(None)
        self.assertEqual(self.card.driver.state.state, EXPANDED)
        self.assertGreater(self.card.height(), nudge_height)

    def test_leave_after_hover_collapses_back_to_quiet(self):
        self.card.showNudge(ITEMS, "Friday")
        self.card.enterEvent(None)
        self.card.leaveEvent(None)
        self.assertEqual(self.card.driver.state.state, QUIET)


def style_rail_size():
    import style
    return style.NUDGE_RAIL_SIZE


if __name__ == "__main__":
    unittest.main()
