import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QApplication, QWidget

import style
from edgeDock import EdgeDock, EdgeDockDriver, OPEN, COMPACT, HIDDEN, TAB


class EdgeDockTests(unittest.TestCase):
    def test_a_fresh_card_arms_the_idle_timer(self):
        dock = EdgeDock()
        self.assertEqual(dock.state, OPEN)
        self.assertEqual(dock.pending_timer, ("idle", style.DOCK_IDLE_MS))

    def test_hovering_cancels_the_idle_timer(self):
        dock = EdgeDock()
        dock.enter_card()
        self.assertIsNone(dock.pending_timer)

    def test_idle_timeout_folds_to_compact_and_arms_the_hide_delay(self):
        dock = EdgeDock()
        dock.idle_timeout()
        self.assertEqual(dock.state, COMPACT)
        self.assertEqual(dock.pending_timer, ("compact_hide", style.DOCK_COMPACT_TO_HIDE_DELAY_MS))

    def test_compact_hide_timeout_hides_the_card(self):
        dock = EdgeDock()
        dock.idle_timeout()
        dock.compact_hide_timeout()
        self.assertEqual(dock.state, HIDDEN)
        self.assertIsNone(dock.pending_timer)

    def test_a_plain_graze_mid_fold_pauses_but_does_not_reopen(self):
        # COMPACT sits in the same corner OPEN just vacated, so a cursor
        # leaving the card is prone to grazing it on the way past - that
        # alone shouldn't pop it back open, only TAB's rule ("hover never
        # opens, only a click does") extended to COMPACT.
        dock = EdgeDock()
        dock.idle_timeout()
        dock.enter_card()
        self.assertEqual(dock.state, COMPACT)
        self.assertIsNone(dock.pending_timer)  # hide countdown paused, not cancelled

    def test_leaving_after_a_graze_resumes_the_hide_countdown(self):
        dock = EdgeDock()
        dock.idle_timeout()
        dock.enter_card()
        dock.leave_card()
        self.assertEqual(dock.state, COMPACT)
        self.assertEqual(dock.pending_timer, ("compact_hide", style.DOCK_COMPACT_TO_HIDE_DELAY_MS))

    def test_streaming_mid_fold_pulls_the_card_back_open(self):
        # Unlike a plain graze, genuine business (a reply arriving) is worth
        # interrupting the retreat for.
        dock = EdgeDock()
        dock.idle_timeout()
        dock.enter_card()
        dock.start_streaming()
        self.assertEqual(dock.state, OPEN)
        self.assertIsNone(dock.pending_timer)

    def test_composer_focus_mid_fold_pulls_the_card_back_open(self):
        dock = EdgeDock()
        dock.idle_timeout()
        dock.enter_card()
        dock.focus_composer()
        self.assertEqual(dock.state, OPEN)
        self.assertIsNone(dock.pending_timer)

    def test_leaving_a_hovered_card_uses_the_shorter_leave_timer(self):
        dock = EdgeDock()
        dock.enter_card()
        dock.leave_card()
        self.assertEqual(dock.pending_timer, ("leave", style.DOCK_LEAVE_MS))

    def test_streaming_blocks_the_retreat_even_if_the_cursor_left(self):
        dock = EdgeDock()
        dock.enter_card()
        dock.start_streaming()
        dock.leave_card()
        self.assertIsNone(dock.pending_timer)
        dock.stop_streaming()
        self.assertEqual(dock.pending_timer, ("leave", style.DOCK_LEAVE_MS))

    def test_composer_focus_blocks_the_retreat(self):
        dock = EdgeDock()
        dock.focus_composer()
        dock.idle_timeout()  # a stray timeout firing after focus should be a no-op
        self.assertEqual(dock.state, OPEN)

    def test_cursor_arms_the_tab_from_hidden(self):
        dock = EdgeDock()
        dock.idle_timeout()
        dock.compact_hide_timeout()
        dock.cursor_distance(style.DOCK_ARM_PX)
        self.assertEqual(dock.state, TAB)

    def test_cursor_short_of_the_arm_threshold_stays_hidden(self):
        dock = EdgeDock()
        dock.idle_timeout()
        dock.compact_hide_timeout()
        dock.cursor_distance(style.DOCK_ARM_PX + 1)
        self.assertEqual(dock.state, HIDDEN)

    def test_hysteresis_keeps_the_tab_out_between_the_two_thresholds(self):
        dock = EdgeDock()
        dock.idle_timeout()
        dock.compact_hide_timeout()
        dock.cursor_distance(style.DOCK_ARM_PX)
        self.assertEqual(dock.state, TAB)
        midpoint = (style.DOCK_ARM_PX + style.DOCK_DISARM_PX) // 2
        dock.cursor_distance(midpoint)
        self.assertEqual(dock.state, TAB)

    def test_cursor_past_the_disarm_threshold_retracts_the_tab(self):
        dock = EdgeDock()
        dock.idle_timeout()
        dock.compact_hide_timeout()
        dock.cursor_distance(style.DOCK_ARM_PX)
        dock.cursor_distance(style.DOCK_DISARM_PX)
        self.assertEqual(dock.state, HIDDEN)

    def test_hover_never_opens_the_tab(self):
        dock = EdgeDock()
        dock.idle_timeout()
        dock.compact_hide_timeout()
        dock.cursor_distance(style.DOCK_ARM_PX)
        dock.enter_card()  # not a click - must not open it
        self.assertEqual(dock.state, TAB)

    def test_clicking_the_tab_opens_the_card(self):
        dock = EdgeDock()
        dock.idle_timeout()
        dock.compact_hide_timeout()
        dock.cursor_distance(style.DOCK_ARM_PX)
        dock.click_tab()
        self.assertEqual(dock.state, OPEN)
        self.assertIsNone(dock.pending_timer)  # the click puts the cursor right on the card

    def test_reopened_card_uses_the_fast_leave_timer_once_the_cursor_moves_off(self):
        dock = EdgeDock()
        dock.idle_timeout()
        dock.compact_hide_timeout()
        dock.cursor_distance(style.DOCK_ARM_PX)
        dock.click_tab()
        dock.leave_card()
        self.assertEqual(dock.pending_timer, ("leave", style.DOCK_LEAVE_MS))

    def test_reveal_reopens_from_wherever_it_folded_to(self):
        dock = EdgeDock()
        dock.idle_timeout()  # OPEN -> COMPACT
        dock.reveal()
        self.assertEqual(dock.state, OPEN)

    def test_minimize_hides_the_card_fully_like_autohide(self):
        dock = EdgeDock()
        dock.minimize()
        self.assertEqual(dock.state, HIDDEN)
        self.assertIsNone(dock.pending_timer)

    def test_minimize_hides_regardless_of_being_busy(self):
        # An explicit "get it out of my sight" isn't a passing hover - it
        # shouldn't wait for streaming/composer focus to end first.
        dock = EdgeDock()
        dock.start_streaming()
        dock.minimize()
        self.assertEqual(dock.state, HIDDEN)

    def test_cursor_can_still_arm_the_tab_after_minimizing(self):
        dock = EdgeDock()
        dock.minimize()
        dock.cursor_distance(style.DOCK_ARM_PX)
        self.assertEqual(dock.state, TAB)

    def test_reveal_reopens_a_minimized_card(self):
        dock = EdgeDock()
        dock.minimize()
        dock.reveal()
        self.assertEqual(dock.state, OPEN)

    def test_reveal_is_a_no_op_when_already_open(self):
        dock = EdgeDock()
        dock.reveal()
        self.assertEqual(dock.state, OPEN)
        self.assertEqual(dock.pending_timer, ("idle", style.DOCK_IDLE_MS))  # untouched

    def test_reveal_does_not_claim_hovering_since_the_cursor_is_at_the_ring_not_the_card(self):
        # Unlike click_tab()/click_compact(), reveal() is triggered from the
        # ring - the cursor isn't on the card, so it must still arm its
        # retreat timer rather than getting stuck "hovered" forever.
        dock = EdgeDock()
        dock.idle_timeout()  # OPEN -> COMPACT
        dock.reveal()
        self.assertFalse(dock.hovering)
        self.assertIsNotNone(dock.pending_timer)


class EdgeDockDriverTests(unittest.TestCase):
    """EdgeDockDriver owns the real QTimer - these guard against it being
    torn down and rearmed by events that don't actually change what's
    pending, since EdgeTrigger calls cursorDistance() on every cursor poll
    (every 50ms) regardless of where the cursor is."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.owner = QWidget()
        self.moved = []
        self.driver = EdgeDockDriver(self.owner, self.geometryFor, self.moved.append)

    def tearDown(self):
        self.owner.deleteLater()

    def geometryFor(self, state):
        return {
            OPEN: QRectF(0, 0, 340, 340),
            COMPACT: QRectF(276, 0, 64, 64),
            HIDDEN: QRectF(340, 0, 64, 64),
            TAB: QRectF(300, 0, 74, 74),
        }[state]

    def test_a_repeated_no_op_event_does_not_restart_the_pending_timer(self):
        # A fresh driver already has the idle timer armed and running.
        self.assertTrue(self.driver.timer.isActive())
        calls = []
        original_start = self.driver.timer.start
        self.driver.timer.start = lambda *a: (calls.append(a), original_start(*a))
        for _ in range(20):  # simulating twenty 50ms EdgeTrigger polls
            self.driver.cursorDistance(style.DOCK_DISARM_PX + 1)  # "cursor is elsewhere" - a no-op in OPEN
        self.assertEqual(calls, [])  # the countdown must never have been restarted

    def test_an_event_that_actually_changes_the_pending_timer_does_restart_it(self):
        self.driver.enterCard()  # busy - cancels the idle timer
        self.assertFalse(self.driver.timer.isActive())
        self.driver.leaveCard()  # busy clears - arms the leave timer
        self.assertTrue(self.driver.timer.isActive())


if __name__ == "__main__":
    unittest.main()
