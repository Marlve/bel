import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QKeyEvent
from PySide6.QtCore import Qt, QEvent, QObject, QAbstractAnimation, Signal

import cardStore
import wedgeConfig
from pieMenu import PieMenu
from pieMenuState import HIDDEN, OPEN, PROMPTING

PROMPT_WEDGE = 3  # the one wedgeConfig's defaults give a placeholder (Claude)
SETTINGS_WEDGE = 2  # wedgeConfig.bottom_pin_index(4) - where Settings lands by default


def key(code, text=""):
    return QKeyEvent(QEvent.KeyPress, code, Qt.NoModifier, text)


class StubRequest(QObject):
    """One call's worth of signals - what a chat card follows."""

    chunk = Signal(str)
    finished = Signal()
    session_started = Signal(str)


class StubAction(QObject):
    """Stands in for a wedge's action, recording its calls and handing back a
    fresh request each time, the way an action for a wedge with a placeholder
    has to."""

    def __init__(self, index, calls):
        super().__init__()
        self.index = index
        self.calls = calls
        self.requests = []

    def __call__(self, *args, **kwargs):
        self.calls.append((self.index, args))
        request = StubRequest()
        self.requests.append(request)
        return request


class PieMenuFlowTests(unittest.TestCase):
    """Drives the phase machine with animation turned off, so every clock
    lands on its final frame the moment it starts and a whole open -> pick ->
    close runs synchronously."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_path = cardStore.STORE_PATH
        cardStore.STORE_PATH = Path(self.tmp.name) / "cards.json"
        self.menu = PieMenu()
        self.menu.motion = False
        self.calls = []
        for index, wedge in enumerate(self.menu.wedges):
            wedge.action = StubAction(index, self.calls)

    def tearDown(self):
        if self.menu.chat.card is not None:
            self.menu.chat.card.close()
        for card in list(self.menu.chat.closing):
            card.close()
        self.menu.close()
        self.menu.deleteLater()
        cardStore.STORE_PATH = self.original_path
        self.tmp.cleanup()

    def openMenu(self):
        self.menu.openAtCursor()
        self.assertEqual(self.menu.phase, OPEN)

    def test_picking_a_plain_wedge_runs_it_once_and_closes(self):
        self.openMenu()
        self.menu.setHovered(0)
        self.menu.activateHoveredWedge()
        self.assertEqual(self.calls, [(0, ())])
        self.assertEqual(self.menu.phase, HIDDEN)

    def test_a_plain_wedge_runs_before_the_select_animation_finishes(self):
        # The card shouldn't wait on the ring's own select/close animation to
        # play out before it appears.
        self.openMenu()
        self.menu.motion = True  # only turned on now - openMenu() needs the instant version to land on OPEN
        self.menu.setHovered(0)
        self.menu.activateHoveredWedge()
        self.assertEqual(self.calls, [(0, ())])
        self.assertNotEqual(self.menu.phase, HIDDEN)  # animation is still playing out

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

        card = self.menu.chat.card
        self.assertIsNotNone(card)
        self.assertEqual(card.turns[0]["text"], "what is on my plate today")
        self.assertEqual(card.born, born)
        self.assertEqual(card.dock_rect.size().toSize().width(), 340)

    def test_a_card_docks_against_the_top_right_of_the_work_area(self):
        screen = QApplication.primaryScreen()
        area = screen.availableGeometry()
        dock = self.menu.chat.dockRect(screen)
        self.assertEqual(dock.top(), area.y() + 24)
        self.assertEqual(dock.right(), area.x() + area.width() - 24)

    def ask(self, prompt):
        """Open the ring and send `prompt` through the prompt bar - only
        valid when no session is open yet for that wedge, since one already
        open is reopened instead (see reopenClaude())."""
        self.openMenu()
        self.menu.setHovered(PROMPT_WEDGE)
        self.menu.activateHoveredWedge()
        self.assertEqual(self.menu.phase, PROMPTING)
        self.menu.prompt_bar.field.setText(prompt)
        self.menu.prompt_bar.submit()
        card = self.menu.chat.card
        card.flight.stop()
        card.onLanded()
        return card

    def reopenClaude(self):
        """Re-pick the Claude wedge while its card is already open."""
        self.openMenu()
        self.menu.setHovered(PROMPT_WEDGE)
        self.menu.activateHoveredWedge()

    def test_chunks_arriving_mid_flight_wait_for_the_card_to_land(self):
        self.openMenu()
        self.menu.setHovered(PROMPT_WEDGE)
        self.menu.activateHoveredWedge()
        self.menu.prompt_bar.field.setText("hello")
        self.menu.prompt_bar.submit()

        card = self.menu.chat.card
        card.request.chunk.emit("in flight")
        self.assertEqual(card.turns[-1]["text"], "")
        card.flight.stop()
        card.onLanded()
        self.assertEqual(card.turns[-1]["text"], "in flight")

    def test_a_finished_request_stops_feeding_its_card(self):
        card = self.ask("hello")
        request = card.request
        request.chunk.emit("first answer")
        request.finished.emit()
        request.chunk.emit("late straggler")
        self.assertEqual(card.turns[-1]["text"], "first answer")

    def test_a_follow_up_message_never_writes_into_the_earlier_turn(self):
        # A follow-up hands back its own request, so it can't corrupt the
        # turn the previous, now-finished request was streaming into.
        card = self.ask("first question")
        first_request = card.request
        first_request.chunk.emit("first answer")
        first_request.finished.emit()

        card.send("second question")
        second_request = card.request
        self.assertIsNot(first_request, second_request)

        second_request.chunk.emit("second answer")
        first_request.chunk.emit("late straggler")
        self.assertEqual(card.turns[-1]["text"], "second answer")

    def test_repicking_claude_while_open_reopens_the_same_card_without_asking(self):
        first = self.ask("first question")
        self.reopenClaude()
        self.assertEqual(self.menu.phase, HIDDEN)
        self.assertIs(self.menu.chat.card, first)
        self.assertEqual(self.calls, [(PROMPT_WEDGE, ("first question",))])  # no second send

    def test_dismissing_then_repicking_claude_starts_a_fresh_session(self):
        first = self.ask("first question")
        first.dismiss()
        first.fade.stop()
        first.onFaded()
        self.assertIsNone(self.menu.chat.card)

        self.openMenu()
        self.menu.setHovered(PROMPT_WEDGE)
        self.menu.activateHoveredWedge()
        self.assertEqual(self.menu.phase, PROMPTING)  # the old card is gone, so it asks again

    def test_the_session_resets_once_the_context_cap_is_reached(self):
        cap = wedgeConfig.DEFAULT_CHAT_CONTEXT_LIMIT
        card = self.ask("q1")
        card.request.session_started.emit("session-a")
        card.request.finished.emit()

        for n in range(2, cap + 1):
            card.send(f"q{n}")
            card.request.session_started.emit("session-a")
            card.request.finished.emit()
        self.assertEqual(card.turn_count, cap)
        self.assertEqual(card.session_id, "session-a")

        card.send("one more")  # the (cap + 1)th message - too much context, starts over
        self.assertEqual(card.turn_count, 1)
        self.assertIsNone(card.session_id)

    def test_a_lower_context_cap_resets_sooner(self):
        wedgeConfig.save_chat_context_limit(1)
        card = self.ask("q1")
        card.request.session_started.emit("session-a")
        card.request.finished.emit()

        card.send("q2")
        self.assertIsNone(card.session_id)

    # ChatSlot itself is exercised directly below, bypassing the ring - only
    # one wedge can ever hold Claude at a time, but this drives the slot with
    # two distinct wedge ids to confirm it never keeps more than one card
    # live regardless of which wedge opened it.
    def test_opening_a_different_wedges_card_replaces_the_current_one(self):
        rect = self.menu.prompt_bar.screenRect()
        action = self.menu.wedges[PROMPT_WEDGE].action
        first = self.menu.chat.open(rect, "first", "wedge-a", action)
        second = self.menu.chat.open(rect, "second", "wedge-b", action)
        self.assertIsNot(first, second)
        self.assertIs(self.menu.chat.card, second)

    def test_dismissing_the_open_card_clears_the_slot(self):
        rect = self.menu.prompt_bar.screenRect()
        action = self.menu.wedges[PROMPT_WEDGE].action
        card = self.menu.chat.open(rect, "first", "wedge-a", action)
        card.dismiss()
        card.fade.stop()
        card.onFaded()
        self.assertIsNone(self.menu.chat.card)
        self.assertIsNone(card.request)

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

    def test_up_key_jumps_straight_to_the_top_wedge(self):
        self.openMenu()
        self.menu.setHovered(2)
        self.menu.keyPressEvent(key(Qt.Key_Up))
        self.assertEqual(self.menu.hovered_wedge, 0)

    def test_down_key_jumps_straight_to_the_bottom_wedge(self):
        self.openMenu()
        self.menu.keyPressEvent(key(Qt.Key_Down))
        self.assertEqual(self.menu.hovered_wedge, SETTINGS_WEDGE)

    def test_a_cursor_past_the_ring_selects_nothing(self):
        from pieMenuState import HIT_RADIUS, wedge_index

        self.assertIsNone(wedge_index(0, -(HIT_RADIUS + 1), 4, radius=HIT_RADIUS))


if __name__ == "__main__":
    unittest.main()
