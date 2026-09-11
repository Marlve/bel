import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QApplication, QWidget

import style
from claudeEdgeDockState import EdgeDock, OPEN, HIDDEN, TAB
from claudeEdgeDockAnimation import EdgeDockDriver


class EdgeDockTests(unittest.TestCase):
    def test_a_fresh_card_starts_open(self):
        dock = EdgeDock()
        self.assertEqual(dock.state, OPEN)

    def test_minimize_hides_the_card(self):
        dock = EdgeDock()
        dock.minimize()
        self.assertEqual(dock.state, HIDDEN)

    def test_minimize_is_a_no_op_unless_open(self):
        dock = EdgeDock()
        dock.minimize()
        dock.minimize()
        self.assertEqual(dock.state, HIDDEN)

    def test_cursor_arms_the_tab_from_hidden(self):
        dock = EdgeDock()
        dock.minimize()
        dock.cursor_distance(style.DOCK_ARM_PX)
        self.assertEqual(dock.state, TAB)

    def test_cursor_short_of_the_arm_threshold_stays_hidden(self):
        dock = EdgeDock()
        dock.minimize()
        dock.cursor_distance(style.DOCK_ARM_PX + 1)
        self.assertEqual(dock.state, HIDDEN)

    def test_hysteresis_keeps_the_tab_out_between_the_two_thresholds(self):
        dock = EdgeDock()
        dock.minimize()
        dock.cursor_distance(style.DOCK_ARM_PX)
        self.assertEqual(dock.state, TAB)
        midpoint = (style.DOCK_ARM_PX + style.DOCK_DISARM_PX) // 2
        dock.cursor_distance(midpoint)
        self.assertEqual(dock.state, TAB)

    def test_cursor_past_the_disarm_threshold_retracts_the_tab(self):
        dock = EdgeDock()
        dock.minimize()
        dock.cursor_distance(style.DOCK_ARM_PX)
        dock.cursor_distance(style.DOCK_DISARM_PX)
        self.assertEqual(dock.state, HIDDEN)

    def test_hover_never_opens_the_tab(self):
        # There's no hover tracking left on EdgeDock at all - cursor_distance
        # is the only input, and being "at" the tab isn't the same as a
        # click on it.
        dock = EdgeDock()
        dock.minimize()
        dock.cursor_distance(style.DOCK_ARM_PX)
        self.assertEqual(dock.state, TAB)

    def test_clicking_the_tab_opens_the_card(self):
        dock = EdgeDock()
        dock.minimize()
        dock.cursor_distance(style.DOCK_ARM_PX)
        dock.click_tab()
        self.assertEqual(dock.state, OPEN)

    def test_click_tab_is_a_no_op_unless_tabbed(self):
        dock = EdgeDock()
        dock.click_tab()
        self.assertEqual(dock.state, OPEN)

    def test_reveal_reopens_a_minimized_card(self):
        dock = EdgeDock()
        dock.minimize()
        dock.reveal()
        self.assertEqual(dock.state, OPEN)

    def test_reveal_reopens_from_the_tab(self):
        dock = EdgeDock()
        dock.minimize()
        dock.cursor_distance(style.DOCK_ARM_PX)
        dock.reveal()
        self.assertEqual(dock.state, OPEN)

    def test_reveal_is_a_no_op_when_already_open(self):
        dock = EdgeDock()
        dock.reveal()
        self.assertEqual(dock.state, OPEN)


class EdgeDockDriverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.owner = QWidget()
        self.moved = []
        # motion=False lands each move in one step (this repo's usual
        # deterministic-test pattern, e.g. ChatCard.motion in
        # test_chat_card.py) rather than depending on a real QVariantAnimation
        # tick, which needs an event loop actually running to fire.
        self.driver = EdgeDockDriver(self.owner, self.geometryFor, self.moved.append, motion=False)

    def tearDown(self):
        self.owner.deleteLater()

    def geometryFor(self, state):
        return {
            OPEN: QRectF(0, 0, 340, 340),
            HIDDEN: QRectF(340, 0, 64, 64),
            TAB: QRectF(300, 0, 74, 74),
        }[state]

    def test_minimize_moves_the_card_to_hidden_geometry(self):
        self.driver.minimize()
        self.assertEqual(self.driver.dock.state, HIDDEN)
        self.assertEqual(self.driver.current_rect, self.geometryFor(HIDDEN))

    def test_reveal_after_minimize_moves_back_to_open_geometry(self):
        self.driver.minimize()
        self.driver.reveal()
        self.assertEqual(self.driver.dock.state, OPEN)
        self.assertEqual(self.driver.current_rect, self.geometryFor(OPEN))

    def test_a_no_op_event_does_not_retarget_the_animation(self):
        # EdgeTrigger calls cursorDistance() on every 50ms poll regardless of
        # where the cursor is - most of those must not touch the tween.
        self.driver.minimize()
        with patch.object(self.driver, "_moveTo") as moveTo:
            for _ in range(20):
                self.driver.cursorDistance(style.DOCK_DISARM_PX + 1)  # already HIDDEN, still past disarm
            moveTo.assert_not_called()


if __name__ == "__main__":
    unittest.main()
