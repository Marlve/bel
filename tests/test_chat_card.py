# Characterization safety net for ChatCard/ChatSlot ahead of ticket 06's
# split - pins down current behavior, no behavior changes here.

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QObject, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

import cardStore
import style
from claudeChatCard import ChatCard, ChatSlot
from claudeEdgeDockState import OPEN, COMPACT, HIDDEN, TAB


def key(code):
    return QKeyEvent(QEvent.KeyPress, code, Qt.NoModifier)


class FakeRequest(QObject):
    """Stands in for actions.claudeAction.ClaudeRequest's three signals,
    fired by hand instead of a real CLI subprocess."""

    chunk = Signal(str)
    finished = Signal()
    session_started = Signal(str)


def teardownCard(card):
    """Mirrors ChatSlot.retire(): stop the real QTimers a landed card owns
    (EdgeDockDriver's countdown, EdgeTrigger's 50ms cursor poll) before the
    widget goes away, or they keep firing into a torn-down test."""
    card.unwire()
    if card.edge_driver:
        card.edge_driver.timer.stop()
    if card.edge_trigger:
        card.edge_trigger.stop()
    card.close()
    card.deleteLater()
    QApplication.processEvents()


class ChatCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_path = cardStore.STORE_PATH
        cardStore.STORE_PATH = Path(self.tmp.name) / "cards.json"
        self.requests = []
        self.born = QRectF(100, 700, 64, 64)
        self.dock_rect = QRectF(1600, 24, style.CHAT_SIZE, style.CHAT_SIZE)
        self.card = ChatCard(self.born, self.dock_rect, QApplication.primaryScreen())
        self.card.motion = False  # deterministic: fly()/dismiss() land in one step
        self.card.action = self.fakeAction

    def tearDown(self):
        teardownCard(self.card)
        cardStore.STORE_PATH = self.original_path
        self.tmp.cleanup()

    def fakeAction(self, prompt, session_id=None):
        request = FakeRequest()
        self.requests.append(request)
        return request

    # --- opening ---

    def test_fly_lands_on_the_dock_rect_and_reveals_content(self):
        self.card.fly()
        self.assertEqual(self.card.geometry(), self.dock_rect.toRect())
        self.assertEqual(self.card.radius, style.CHAT_RADIUS)
        self.assertTrue(self.card.header_label.isVisible())
        self.assertIsNotNone(self.card.edge_driver)
        self.assertIsNotNone(self.card.edge_trigger)

    def test_flight_tick_interpolates_between_born_and_dock_rect(self):
        self.card.onFlightTick(0)
        self.assertEqual(self.card.geometry(), self.born.toRect())
        self.card.onFlightTick(style.CHAT_FLIGHT_MS)
        self.assertEqual(self.card.geometry(), self.dock_rect.toRect())

    # --- dismissing ---

    def test_dismiss_hides_the_card_and_emits_dismissed(self):
        self.card.fly()
        seen = []
        self.card.dismissed.connect(seen.append)
        self.card.dismiss()
        self.assertFalse(self.card.isVisible())
        self.assertEqual(seen, [self.card])

    def test_escape_dismisses(self):
        self.card.fly()
        self.card.keyPressEvent(key(Qt.Key_Escape))
        self.assertFalse(self.card.isVisible())

    def test_dismiss_is_a_no_op_while_a_fade_is_already_running(self):
        self.card.motion = True
        self.card.dismiss()
        self.assertEqual(self.card.fade.state(), QVariantAnimation.Running)
        seen = []
        self.card.dismissed.connect(seen.append)
        self.card.dismiss()
        self.assertEqual(seen, [])

    # --- edge-dock states ---

    def test_dock_state_changes_toggle_compact_visuals_and_tilt(self):
        self.card.fly()

        self.card.onDockStateChanged(COMPACT)
        self.assertFalse(self.card.header_label.isVisible())
        self.assertEqual(self.card.tilt, 0.0)

        self.card.onDockStateChanged(TAB)
        self.assertFalse(self.card.header_label.isVisible())
        self.assertEqual(self.card.tilt, style.DOCK_TAB_ROTATION_DEG)

        self.card.onDockStateChanged(HIDDEN)
        self.assertFalse(self.card.header_label.isVisible())
        self.assertEqual(self.card.tilt, 0.0)

        self.card.onDockStateChanged(OPEN)
        self.assertTrue(self.card.header_label.isVisible())
        self.assertEqual(self.card.tilt, 0.0)

    # --- the conversation ---

    def test_send_streams_a_reply_into_the_transcript(self):
        self.card.fly()
        self.card.send("hello")
        self.assertEqual(len(self.requests), 1)
        self.assertEqual([turn["role"] for turn in self.card.turns], ["user", "claude"])
        self.assertTrue(self.card.composer.isReadOnly())

        label = self.card.streaming_label
        self.requests[0].chunk.emit("Hi there")
        self.assertEqual(self.card.turns[-1]["text"], "Hi there")
        self.assertIn("Hi there", label.text())

        self.requests[0].finished.emit()
        self.assertFalse(self.card.composer.isReadOnly())
        self.assertIsNone(self.card.request)
        self.assertIsNone(self.card.streaming_label)


class ChatSlotTests(unittest.TestCase):
    """The dedupe rule: reopening the same wedge's card reveals it instead
    of spawning another - the fix ticket 04 exists to pin down."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_path = cardStore.STORE_PATH
        cardStore.STORE_PATH = Path(self.tmp.name) / "cards.json"
        motion_patch = patch("claudeChatCard.reduced_motion", return_value=True)
        motion_patch.start()
        self.addCleanup(motion_patch.stop)
        self.requests = []
        self.slot = ChatSlot()
        self.born = QRectF(100, 700, 64, 64)

    def tearDown(self):
        if self.slot.card:
            teardownCard(self.slot.card)
        QApplication.processEvents()  # flush any pending ChatSlot.dropRetired()
        cardStore.STORE_PATH = self.original_path
        self.tmp.cleanup()

    def fakeAction(self, prompt, session_id=None):
        request = FakeRequest()
        self.requests.append(request)
        return request

    def test_open_lands_a_card_and_sends_the_prompt(self):
        card = self.slot.open(self.born, "hi", "wedge-1", self.fakeAction)
        self.assertIs(self.slot.card, card)
        self.assertEqual(card.wedge_id, "wedge-1")
        self.assertEqual(len(self.requests), 1)

    def test_reopening_the_same_wedge_reveals_the_existing_card_instead_of_spawning_another(self):
        first = self.slot.open(self.born, "hi", "wedge-1", self.fakeAction)
        second = self.slot.open(self.born, "hi again", "wedge-1", self.fakeAction)
        self.assertIs(second, first)
        self.assertEqual(len(self.requests), 1)

    def test_opening_a_different_wedge_retires_the_old_card(self):
        first = self.slot.open(self.born, "hi", "wedge-1", self.fakeAction)
        second = self.slot.open(self.born, "hi", "wedge-2", self.fakeAction)
        self.assertIsNot(second, first)
        self.assertIs(self.slot.card, second)
        self.assertIn(first, self.slot.closing)

    def test_dismissing_the_card_forgets_it_from_the_slot(self):
        self.slot.open(self.born, "hi", "wedge-1", self.fakeAction)
        self.slot.card.dismiss()
        self.assertIsNone(self.slot.card)


if __name__ == "__main__":
    unittest.main()
