import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QKeyEvent
from PySide6.QtCore import Qt, QEvent, QObject, QAbstractAnimation, Signal

from pie_menu import PieMenu, HIDDEN, OPEN, PROMPTING

PROMPT_WEDGE = 3  # the one WEDGE_CONFIG gives a placeholder


def key(code, text=""):
    return QKeyEvent(QEvent.KeyPress, code, Qt.NoModifier, text)


class StubAction(QObject):
    """Stands in for a wedge's action, recording its calls. Carries the
    chunk/finished signals a wedge with a placeholder has to expose, since
    that's what a result card wires itself to."""

    chunk = Signal(str)
    finished = Signal()

    def __init__(self, index, calls):
        super().__init__()
        self.index = index
        self.calls = calls

    def __call__(self, *args):
        self.calls.append((self.index, args))


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
            wedge.action = StubAction(index, self.calls)

    def tearDown(self):
        for card in list(self.menu.cards.cards):
            card.close()
        self.menu.cards.cards.clear()
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

    def test_submitting_opens_a_card_born_as_the_prompt_bar(self):
        self.openMenu()
        self.menu.setHovered(PROMPT_WEDGE)
        self.menu.activateHoveredWedge()
        born = self.menu.prompt_bar.screenRect()
        self.menu.prompt_bar.field.setText("what is on my plate today")
        self.menu.prompt_bar.submit()

        self.assertEqual(len(self.menu.cards.cards), 1)
        card = self.menu.cards.cards[0]
        self.assertEqual(card.prompt, "what is on my plate today")
        self.assertEqual(card.born, born)
        self.assertEqual(card.dock.size().toSize().width(), 340)

    def test_a_card_docks_against_the_top_right_of_the_work_area(self):
        screen = QApplication.primaryScreen()
        area = screen.availableGeometry()
        dock = self.menu.cards.dockRect(0, screen)
        self.assertEqual(dock.top(), area.y() + 24)
        self.assertEqual(dock.right(), area.x() + area.width() - 24)

    def test_stacked_cards_sit_below_the_newest(self):
        screen = QApplication.primaryScreen()
        first = self.menu.cards.dockRect(0, screen)
        second = self.menu.cards.dockRect(1, screen)
        self.assertEqual(second.top() - first.top(), 352)
        self.assertEqual(second.left(), first.left())

    def test_chunks_arriving_mid_flight_wait_for_the_card_to_land(self):
        self.openMenu()
        self.menu.setHovered(PROMPT_WEDGE)
        self.menu.activateHoveredWedge()
        self.menu.prompt_bar.field.setText("hello")
        self.menu.prompt_bar.submit()

        card = self.menu.cards.cards[0]
        self.menu.wedges[PROMPT_WEDGE].action.chunk.emit("in flight")
        self.assertEqual(card.body.toPlainText(), "")
        card.flight.stop()
        card.onLanded()
        self.assertEqual(card.body.toPlainText(), "in flight")

    def test_a_finished_request_stops_feeding_its_card(self):
        self.openMenu()
        self.menu.setHovered(PROMPT_WEDGE)
        self.menu.activateHoveredWedge()
        self.menu.prompt_bar.field.setText("hello")
        self.menu.prompt_bar.submit()

        card = self.menu.cards.cards[0]
        card.flight.stop()
        card.onLanded()
        action = self.menu.wedges[PROMPT_WEDGE].action
        action.chunk.emit("first answer")
        action.finished.emit()
        action.chunk.emit("second question's answer")
        self.assertEqual(card.body.toPlainText(), "first answer")

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
