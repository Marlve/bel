import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QApplication, QWidget

from calendarNudgeAnimation import CalendarNudgeDriver
from calendarNudgeState import QUIET, NUDGE, EXPANDED

ITEMS = [{"title": "Essay draft", "due": "Fri"}]


class CalendarNudgeDriverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.owner = QWidget()
        self.moved = []
        self.states = []
        # motion=False lands each move in one step - this repo's usual
        # deterministic-test pattern (see test_claude_edge_dock.py) rather
        # than depending on a real QVariantAnimation tick.
        self.driver = CalendarNudgeDriver(
            self.owner, self.geometryFor, self.moved.append, self.states.append, motion=False
        )

    def tearDown(self):
        self.owner.deleteLater()

    def geometryFor(self, state):
        return {
            QUIET: QRectF(0, 0, 5, 56),
            NUDGE: QRectF(0, 0, 260, 56),
            EXPANDED: QRectF(0, 0, 260, 78),
        }[state]

    def test_show_moves_to_nudge_geometry_and_notifies(self):
        self.driver.show(ITEMS, "sentence", "source")
        self.assertEqual(self.driver.current_rect, self.geometryFor(NUDGE))
        self.assertEqual(self.states, [NUDGE])

    def test_hover_moves_to_expanded_geometry_and_stops_the_retire_timer(self):
        self.driver.show(ITEMS, "sentence", "source")
        self.assertTrue(self.driver.retire_timer.isActive())
        self.driver.hover()
        self.assertEqual(self.driver.current_rect, self.geometryFor(EXPANDED))
        self.assertFalse(self.driver.retire_timer.isActive())

    def test_leave_moves_back_to_quiet_geometry(self):
        self.driver.show(ITEMS, "sentence", "source")
        self.driver.hover()
        self.driver.leave()
        self.assertEqual(self.driver.current_rect, self.geometryFor(QUIET))
        self.assertEqual(self.driver.state.items, [])

    def test_retire_timeout_moves_back_to_quiet_geometry(self):
        self.driver.show(ITEMS, "sentence", "source")
        self.driver.retire_timer.timeout.emit()
        self.assertEqual(self.driver.current_rect, self.geometryFor(QUIET))

    def test_a_second_show_while_already_showing_does_not_retarget(self):
        self.driver.show(ITEMS, "sentence", "source")
        before = self.driver.current_rect
        self.driver.show([{"title": "Other", "due": "Mon"}], "other", "other")
        self.assertEqual(self.driver.current_rect, before)
        self.assertEqual(self.states, [NUDGE])  # no second notification


if __name__ == "__main__":
    unittest.main()
