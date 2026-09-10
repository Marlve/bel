import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QKeyEvent
from PySide6.QtCore import Qt, QEvent, QAbstractAnimation

from pie_menu import PieMenu, HIDDEN, OPEN, PROMPTING

PROMPT_WEDGE = 3  # the one WEDGE_CONFIG gives a placeholder


def key(code, text=""):
    return QKeyEvent(QEvent.KeyPress, code, Qt.NoModifier, text)


class PieMenuFlowTests(unittest.TestCase):
    """Drives the phase machine with animation turned off, so every clock
    lands on its final frame the moment it starts and a whole open -> pick ->
    close runs synchronously."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.menu = PieMenu()
        self.menu.motion = False
        self.calls = []
        for index, wedge in enumerate(self.menu.wedges):
            wedge.action = lambda *args, index=index: self.calls.append((index, args))

    def tearDown(self):
        self.menu.close()
        self.menu.deleteLater()

    def openMenu(self):
        self.menu.openAtCursor()
        self.assertEqual(self.menu.phase, OPEN)

    def test_picking_a_plain_wedge_runs_it_once_and_closes(self):
        self.openMenu()
        self.menu.setHovered(0)
        self.menu.activateHoveredWedge()
        self.assertEqual(self.calls, [(0, ())])
        self.assertEqual(self.menu.phase, HIDDEN)

    def test_picking_a_wedge_never_runs_it_twice(self):
        # A select clock left running past its own phase used to re-enter
        # beginClose and fire the action a second time.
        self.openMenu()
        self.menu.setHovered(1)
        self.menu.activateHoveredWedge()
        self.openMenu()
        self.menu.setHovered(1)
        self.menu.activateHoveredWedge()
        self.assertEqual(self.calls, [(1, ()), (1, ())])

    def test_reopening_leaves_no_clock_running(self):
        self.openMenu()
        self.menu.setHovered(0)
        self.menu.activateHoveredWedge()
        self.openMenu()
        running = [clock for clock in self.menu.clocks[1:] if clock.state() != QAbstractAnimation.Stopped]
        self.assertEqual(running, [])

    def test_picking_mid_open_stops_the_open_animation(self):
        # Left running, it would finish later and flip the phase back to
        # OPEN in the middle of the select, re-enabling input.
        self.menu.motion = True
        self.menu.openAtCursor()
        self.menu.setHovered(0)
        self.menu.activateHoveredWedge()
        self.assertEqual(self.menu.open_clock.state(), QAbstractAnimation.Stopped)

    def test_a_prompt_wedge_waits_for_text_instead_of_running(self):
        self.openMenu()
        self.menu.setHovered(PROMPT_WEDGE)
        self.menu.activateHoveredWedge()
        self.assertEqual(self.menu.phase, PROMPTING)
        self.assertEqual(self.calls, [])

    def test_submitting_the_prompt_runs_the_wedge_with_the_text(self):
        self.openMenu()
        self.menu.setHovered(PROMPT_WEDGE)
        self.menu.activateHoveredWedge()
        self.menu.prompt_bar.field.setText("what is on my plate today")
        self.menu.prompt_bar.submit()
        self.assertEqual(self.calls, [(PROMPT_WEDGE, ("what is on my plate today",))])
        self.assertEqual(self.menu.phase, HIDDEN)

    def test_an_empty_prompt_is_rejected_rather_than_sent(self):
        self.openMenu()
        self.menu.setHovered(PROMPT_WEDGE)
        self.menu.activateHoveredWedge()
        self.menu.prompt_bar.field.setText("   ")
        self.menu.prompt_bar.submit()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.menu.phase, PROMPTING)

    def test_escape_from_the_prompt_steps_back_to_the_ring(self):
        self.openMenu()
        self.menu.setHovered(PROMPT_WEDGE)
        self.menu.activateHoveredWedge()
        self.menu.returnToRing()
        self.assertEqual(self.menu.phase, OPEN)
        self.assertEqual(self.calls, [])
        self.assertIsNone(self.menu.chosen_wedge)

    def test_the_hotkey_closes_the_prompt_without_running_it(self):
        self.openMenu()
        self.menu.setHovered(PROMPT_WEDGE)
        self.menu.activateHoveredWedge()
        self.menu.onKeyPress()
        self.assertEqual(self.menu.phase, HIDDEN)
        self.assertEqual(self.calls, [])

    def test_typing_over_the_ring_jumps_into_the_prompt(self):
        self.openMenu()
        self.menu.keyPressEvent(key(Qt.Key_W, "w"))
        self.assertEqual(self.menu.phase, PROMPTING)
        self.assertEqual(self.menu.prompt_bar.field.text(), "w")

    def test_arrow_keys_still_cycle_rather_than_jumping_into_the_prompt(self):
        self.openMenu()
        self.menu.keyPressEvent(key(Qt.Key_Right))
        self.assertEqual(self.menu.phase, OPEN)
        self.assertEqual(self.menu.hovered_wedge, 0)

    def test_a_cursor_past_the_ring_selects_nothing(self):
        from pie_menu import HIT_RADIUS, wedge_index

        self.assertIsNone(wedge_index(0, -(HIT_RADIUS + 1), 4, radius=HIT_RADIUS))


if __name__ == "__main__":
    unittest.main()
