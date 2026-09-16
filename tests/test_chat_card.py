# Characterization safety net for ChatCard/ChatSlot ahead of ticket 06's
# split - pins down current behavior, no behavior changes here.

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QLabel

import cardStore
import dockCorner
import style
from claudeChatCard import ChatCard, ChatSlot
from claudeEdgeDockState import OPEN, HIDDEN, TAB


def key(code):
    return QKeyEvent(QEvent.KeyPress, code, Qt.NoModifier)


def mouseEvent(kind, global_pos):
    return QMouseEvent(kind, QPointF(0, 0), QPointF(global_pos), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)


class FakeRequest(QObject):
    """Stands in for actions.claudeAction.ClaudeRequest's three signals,
    fired by hand instead of a real CLI subprocess."""

    chunk = Signal(str)
    finished = Signal()
    session_started = Signal(str)


class FakeLookup:
    """Stands in for vaultSearch.ExplainQuery - the test calls on_result by
    hand instead of searching a real vault."""

    def __init__(self, query, on_result):
        self.query = query
        self.on_result = on_result
        self.started = False
        self.cancelled = False

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True


NOTES = [{"path": str(Path("1 Project") / "Plan.md"), "recent": True}]
CONCEPT_HIT = {"hit": True, "kind": "concept", "path": str(Path("3 Reference") / "Dijkstra.md"), "content": "Shortest path algorithm."}
CONCEPT_MISS = {"hit": False, "kind": "concept", "draft": "A drafted explanation."}


def teardownCard(card):
    """Mirrors ChatSlot.retire(): stop the real QTimer a landed card owns
    (EdgeTrigger's 50ms cursor poll) and any in-flight edge-dock tween
    before the widget goes away, or they keep firing into a torn-down
    test."""
    card.unwire()
    card.stopDynamics()
    card.close()
    card.deleteLater()
    QApplication.processEvents()


class ChatCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_dir = cardStore.STORE_DIR
        self.original_legacy_path = cardStore.LEGACY_STORE_PATH
        cardStore.STORE_DIR = Path(self.tmp.name) / "cards"
        cardStore.LEGACY_STORE_PATH = Path(self.tmp.name) / "cards.json"
        self.requests = []
        self.born = QRectF(100, 700, 64, 64)
        self.dock_rect = QRectF(1600, 24, style.CHAT_SIZE, style.CHAT_SIZE)
        self.card = ChatCard(self.born, self.dock_rect, QApplication.primaryScreen())
        self.card.motion = False  # deterministic: fly()/dismiss() land in one step
        self.card.action = self.fakeAction

    def tearDown(self):
        teardownCard(self.card)
        cardStore.STORE_DIR = self.original_dir
        cardStore.LEGACY_STORE_PATH = self.original_legacy_path
        self.tmp.cleanup()

    def fakeAction(self, prompt, session_id=None):
        request = FakeRequest()
        self.requests.append(request)
        return request

    # --- layout ---

    def test_transcript_rows_align_with_the_header_and_composer(self):
        # QVBoxLayout(self.transcript) makes transcript_layout the widget's
        # own top-level layout, which (unlike header's nested QHBoxLayout)
        # picks up the style's non-zero default margins unless zeroed -
        # previously landed Claude's turn text ~9px right of the header
        # label's and composer's own left edge.
        self.assertEqual(self.card.transcript_layout.contentsMargins().left(), 0)

    def test_transcript_row_spacing_uses_the_named_constant(self):
        # Regression for chat-bubble-polish/02: this used to be a bare
        # literal 8, invisible to apply_scale()'s per-monitor scaling - so
        # on a large enough screen CHAT_PARAGRAPH_GAP (which does scale)
        # could grow past this unscaled turn-gap, inverting the gap
        # hierarchy the ticket was built to fix.
        self.assertEqual(self.card.transcript_layout.spacing(), style.SPACE_2)

    def test_paragraph_gap_stays_smaller_than_the_turn_gap_at_4k_scale(self):
        import importlib
        try:
            style.apply_scale(1.5)  # e.g. a 3840x2160 4K primary monitor
            self.assertLess(style.CHAT_PARAGRAPH_GAP, style.SPACE_2)
        finally:
            importlib.reload(style)

    def test_composer_right_edge_matches_transcript_content_width(self):
        # Regression for chat-bubble-polish/04: the composer used to span
        # root's raw padded width, running 6px past contentWidth() - the
        # same 6px the transcript reserves for the scrollbar - so its right
        # edge sat under the scrollbar instead of stopping short of it.
        self.card.fly()
        self.assertEqual(self.card.composer.width(), self.card.contentWidth())

    def test_bel_reply_stops_short_of_the_composer_right_edge(self):
        # Regression for chat-bubble-polish/05: Bel's reply used to run the
        # full contentWidth(), flush with the composer's own right edge -
        # now it stops CHAT_REPLY_INSET short as a deliberate visual margin.
        self.card.fly()
        self.card.send("hello")
        self.assertEqual(
            self.card.streaming_label.width(),
            self.card.contentWidth() - style.CHAT_REPLY_INSET,
        )

    def test_single_word_user_bubble_is_wide_enough_not_to_clip(self):
        # Regression for chat-bubble-polish/06's real root cause: any
        # unbreakable single "word" ("idk", "hi", "ok"...) can never wrap
        # onto a second line at any width, so userBubbleWidth()'s
        # narrowest-width-without-a-second-line binary search never gets a
        # signal that a width is too narrow - it silently returned its
        # QFontMetrics-based starting guess, ~13px short of what the real
        # QLabel (with its own internal QTextDocument margin) needed,
        # clipping the last character(s). The fix measures the same
        # QLabel's own unwrapped sizeHint() instead of guessing.
        for word in ("idk", "hi", "ok", "a", "yes"):
            probe = QLabel(word)
            probe.setTextFormat(Qt.PlainText)
            probe.setStyleSheet(style.chat_bubble_stylesheet())
            probe.ensurePolished()
            probe.setWordWrap(False)
            natural_width = probe.sizeHint().width()
            self.assertGreaterEqual(self.card.userBubbleWidth(word), natural_width)

    def test_user_turn_gets_extra_gap_after_a_bel_reply(self):
        # chat-bubble-polish/02: user-to-Bel already got CHAT_BUBBLE_GAP_EXTRA
        # on top of transcript_layout's own row spacing, but Bel-to-user had
        # none - the rhythm should be symmetric.
        self.card.fly()
        self.card.send("hi")
        self.requests[0].finished.emit()
        self.card.send("again")
        second_user_row = self.card.transcript_layout.itemAt(2).layout()
        self.assertEqual(second_user_row.contentsMargins().top(), style.CHAT_BUBBLE_GAP_EXTRA)

    def test_first_user_turn_gets_no_extra_gap(self):
        # No previous turn to follow - should behave like today, no margin.
        self.card.fly()
        self.card.send("hi")
        first_user_row = self.card.transcript_layout.itemAt(0).layout()
        self.assertEqual(first_user_row.contentsMargins().top(), 0)

    def test_scrollbar_never_draws_over_content(self):
        # A visible thumb clipped bubble/composer text under it (short
        # single-word bubbles like "idk" worst-hit) - still scrollable via
        # wheel/drag, just no drawn bar.
        self.assertEqual(self.card.scroll.verticalScrollBarPolicy(), Qt.ScrollBarAlwaysOff)

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

        self.card.onDockStateChanged(TAB)
        self.assertFalse(self.card.header_label.isVisible())
        self.assertEqual(self.card.tilt, style.DOCK_TAB_ROTATION_DEG)

        self.card.onDockStateChanged(HIDDEN)
        self.assertFalse(self.card.header_label.isVisible())
        self.assertEqual(self.card.tilt, 0.0)

        self.card.onDockStateChanged(OPEN)
        self.assertTrue(self.card.header_label.isVisible())
        self.assertEqual(self.card.tilt, 0.0)

    def test_tab_tilt_is_mirrored_for_a_left_docked_corner(self):
        left_dock_rect = QRectF(24, 24, style.CHAT_SIZE, style.CHAT_SIZE)
        left_card = ChatCard(self.born, left_dock_rect, QApplication.primaryScreen(), dockCorner.TOP_LEFT)
        left_card.motion = False
        self.addCleanup(teardownCard, left_card)
        left_card.fly()

        left_card.onDockStateChanged(TAB)
        self.assertEqual(left_card.tilt, -style.DOCK_TAB_ROTATION_DEG)

    def test_hidden_and_tab_geometry_mirror_to_the_left_edge_for_a_left_docked_corner(self):
        area = QApplication.primaryScreen().availableGeometry()
        left_dock_rect = dockCorner.rect(dockCorner.TOP_LEFT, area, style.CHAT_SIZE, style.CHAT_MARGIN)
        left_card = ChatCard(self.born, left_dock_rect, QApplication.primaryScreen(), dockCorner.TOP_LEFT)
        left_card.motion = False
        self.addCleanup(teardownCard, left_card)
        left_card.fly()

        hidden = left_card.animation.geometryFor(HIDDEN)
        self.assertEqual(hidden.x(), area.x() - style.DOCK_COMPACT_SIZE)  # fully off-screen to the left

        tab = left_card.animation.geometryFor(TAB)
        self.assertGreater(tab.right(), area.x())  # the visible sliver peeks onto the screen
        self.assertLess(tab.x(), area.x())  # most of the puck sits off-screen to the left

    # --- drag-and-snap to a corner ---

    def test_a_press_and_release_under_the_threshold_is_a_click_not_a_drag(self):
        self.card.fly()
        self.card.move(300, 300)
        start_pos = self.card.pos()
        press = QPointF(310, 310)
        self.card.mousePressEvent(mouseEvent(QEvent.MouseButtonPress, press))
        self.card.mouseMoveEvent(mouseEvent(QEvent.MouseMove, press + QPointF(1, 1)))
        self.card.mouseReleaseEvent(mouseEvent(QEvent.MouseButtonRelease, press + QPointF(1, 1)))
        self.assertEqual(self.card.pos(), start_pos)
        self.assertEqual(self.card.corner, dockCorner.TOP_RIGHT)

    def test_dragging_past_the_threshold_follows_the_cursor(self):
        self.card.fly()
        self.card.move(200, 300)
        press = QPointF(210, 310)
        self.card.mousePressEvent(mouseEvent(QEvent.MouseButtonPress, press))
        self.card.mouseMoveEvent(mouseEvent(QEvent.MouseMove, press + QPointF(50, 5)))
        self.assertEqual(self.card.pos(), QPoint(250, 305))

    def test_releasing_a_drag_docks_to_the_nearest_corner_and_persists_it(self):
        self.card.fly()
        self.card.move(300, 300)
        seen = []
        self.card.corner_changed.connect(seen.append)
        press = QPointF(310, 310)
        self.card.mousePressEvent(mouseEvent(QEvent.MouseButtonPress, press))
        area = QApplication.primaryScreen().availableGeometry()
        bottom_left = QPointF(area.x() + 20, area.y() + area.height() - 20)
        self.card.mouseMoveEvent(mouseEvent(QEvent.MouseMove, bottom_left))
        self.card.mouseReleaseEvent(mouseEvent(QEvent.MouseButtonRelease, bottom_left))
        self.assertEqual(self.card.corner, dockCorner.BOTTOM_LEFT)
        self.assertEqual(seen, [dockCorner.BOTTOM_LEFT])
        expected = dockCorner.rect(dockCorner.BOTTOM_LEFT, area, style.CHAT_SIZE, style.CHAT_MARGIN)
        self.assertEqual(self.card.geometry(), expected.toRect())

    def test_docks_by_where_the_card_visually_sits_not_the_raw_cursor(self):
        # Grabbing low on the card and dragging up leaves the cursor above
        # the screen's midpoint while the card's own body - the offset
        # between grab point and window origin - is still below it. The
        # corner should follow what the card visually looks closest to, not
        # the cursor alone.
        self.card.fly()
        self.card.move(300, 550)
        press = QPointF(310, 560)
        self.card.mousePressEvent(mouseEvent(QEvent.MouseButtonPress, press))
        release = press + QPointF(0, -250)
        self.card.mouseMoveEvent(mouseEvent(QEvent.MouseMove, release))
        self.card.mouseReleaseEvent(mouseEvent(QEvent.MouseButtonRelease, release))
        self.assertEqual(self.card.corner, dockCorner.BOTTOM_RIGHT)

    def test_the_snap_animation_starts_from_the_actual_drop_point(self):
        # The live drag moves the window directly (self.parent.move()),
        # bypassing EdgeDockDriver entirely - its own current_rect bookkeeping
        # would otherwise still be wherever OPEN last was, and the tween
        # would visibly snap back there before animating out to the new
        # corner instead of starting from the drop point.
        self.card.motion = True
        self.card.fly()
        self.card.flight.stop()
        self.card.onLanded()

        self.card.move(300, 300)
        press = QPointF(310, 310)
        self.card.mousePressEvent(mouseEvent(QEvent.MouseButtonPress, press))
        area = QApplication.primaryScreen().availableGeometry()
        bottom_left = QPointF(area.x() + 20, area.y() + area.height() - 20)
        self.card.mouseMoveEvent(mouseEvent(QEvent.MouseMove, bottom_left))
        drop_rect = QRectF(self.card.geometry())

        self.card.mouseReleaseEvent(mouseEvent(QEvent.MouseButtonRelease, bottom_left))

        self.assertEqual(self.card.animation.edge_driver.tween.startValue(), drop_rect)

    def test_releasing_a_drag_on_a_different_screen_docks_there_not_the_original_one(self):
        # dragMove() already re-resolves the screen under the cursor on
        # every move to clamp correctly on whatever monitor it's over -
        # dragRelease() has to keep self.screen in step too, or a
        # cross-monitor drag would snap back to a corner of the monitor the
        # card started on instead of the one it was actually dropped on.
        self.card.fly()
        self.card.move(300, 300)
        press = QPointF(310, 310)
        self.card.mousePressEvent(mouseEvent(QEvent.MouseButtonPress, press))
        self.card.mouseMoveEvent(mouseEvent(QEvent.MouseMove, press + QPointF(50, 50)))

        other_area = QRectF(2000, 0, 1000, 800)
        other_screen = Mock()
        other_screen.availableGeometry.return_value = other_area
        release_pos = QPointF(2990, 20)  # top-right quadrant of other_area

        with patch("claudeChatCardAnimation.QApplication.screenAt", return_value=other_screen):
            self.card.mouseMoveEvent(mouseEvent(QEvent.MouseMove, release_pos))
            self.card.mouseReleaseEvent(mouseEvent(QEvent.MouseButtonRelease, release_pos))

        self.assertIs(self.card.animation.screen, other_screen)
        self.assertEqual(self.card.corner, dockCorner.TOP_RIGHT)
        expected = dockCorner.rect(dockCorner.TOP_RIGHT, other_area, style.CHAT_SIZE, style.CHAT_MARGIN)
        self.assertEqual(self.card.dock_rect, expected)

    def test_pressing_while_minimized_does_not_start_a_drag(self):
        self.card.fly()
        self.card.minimize()
        press = QPointF(self.card.x() + 10, self.card.y() + 10)
        self.card.mousePressEvent(mouseEvent(QEvent.MouseButtonPress, press))
        self.assertIsNone(self.card.animation.drag_press_pos)

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

    def test_a_typing_indicator_fills_the_gap_before_the_first_chunk(self):
        # chat-bubble-polish/01: the reply bubble used to render nothing at
        # all until the first chunk arrived - no feedback that Bel was
        # actually working during the fetch/cold-start gap.
        self.card.fly()
        self.card.send("hello")
        label = self.card.streaming_label
        self.assertNotEqual(label.text(), "")
        self.assertIsNotNone(self.card.animation.typing_label)

    def test_the_first_chunk_stops_the_typing_indicator(self):
        self.card.fly()
        self.card.send("hello")
        self.requests[0].chunk.emit("Hi")
        self.assertIsNone(self.card.animation.typing_label)
        self.assertIn("Hi", self.card.streaming_label.text())

    def test_a_reply_with_no_chunks_still_stops_the_typing_indicator(self):
        # Defensive: an empty/errored reply shouldn't leave the indicator
        # pulsing forever with nothing left listening to it.
        self.card.fly()
        self.card.send("hello")
        self.requests[0].finished.emit()
        self.assertIsNone(self.card.animation.typing_label)

    def test_reduced_motion_shows_static_typing_dots_instead_of_pulsing(self):
        # self.card.motion is already False (set in setUp) for deterministic
        # tests elsewhere - covers the same reduced_motion() path a real
        # user with motion off would hit.
        self.card.fly()
        self.card.send("hello")
        self.assertEqual(self.card.animation.typing_clock.state(), QVariantAnimation.Stopped)
        self.assertNotEqual(self.card.streaming_label.text(), "")

    # --- `?` lookups (card.md) ---

    def fakeLookup(self, query, on_result):
        lookup = FakeLookup(query, on_result)
        self.lookups.append(lookup)
        return lookup

    def startLookup(self, text="? Dijkstra"):
        self.lookups = []
        self.card.lookup_factory = self.fakeLookup
        self.card.fly()
        self.card.send(text)
        return self.lookups[0] if self.lookups else None

    def test_a_question_mark_message_starts_a_lookup_instead_of_chat(self):
        lookup = self.startLookup("? Dijkstra")

        self.assertEqual(lookup.query, "Dijkstra")
        self.assertTrue(lookup.started)
        self.assertEqual(self.requests, [])
        self.assertEqual([turn["role"] for turn in self.card.turns], ["user", "claude"])
        self.assertTrue(self.card.composer.isReadOnly())
        self.assertIsNotNone(self.card.animation.typing_label)
        self.assertEqual(self.card.turn_count, 0)  # never sent to the Claude session

    def test_chat_waits_while_a_lookup_is_running(self):
        self.startLookup()

        self.card.send("hello")

        self.assertEqual(self.requests, [])

    def test_a_concept_hit_shows_the_note_and_a_picker(self):
        lookup = self.startLookup()

        lookup.on_result({**CONCEPT_HIT, "notes": NOTES})

        self.assertIn("Shortest path algorithm.", self.card.turns[-1]["text"])
        self.assertEqual(len(self.card.picker.rows), 1)
        self.assertIsNone(self.card.animation.typing_label)
        self.assertFalse(self.card.composer.isReadOnly())
        self.assertIsNone(self.card.lookup)

    def test_a_miss_shows_the_draft_and_a_picker(self):
        lookup = self.startLookup()

        lookup.on_result({**CONCEPT_MISS, "notes": NOTES})

        self.assertIn("A drafted explanation.", self.card.turns[-1]["text"])
        self.assertEqual(len(self.card.picker.rows), 1)

    def test_picking_a_note_confirms_it_and_says_where_it_connected(self):
        lookup = self.startLookup()
        result = {**CONCEPT_MISS, "notes": NOTES}
        lookup.on_result(result)

        with patch("claudeChatCard.vaultSearch.confirm_pick", return_value=Path("C:/vault/1 Project/Plan.md")) as confirm:
            self.card.picker.picked.emit(NOTES[0]["path"])

        confirm.assert_called_once_with("Dijkstra", result, NOTES[0]["path"])
        self.assertIn("connected to <b>Plan</b>", self.card.picker.outcome_label.text())

    def test_a_pick_that_cannot_be_saved_says_so(self):
        lookup = self.startLookup()
        lookup.on_result({**CONCEPT_MISS, "notes": NOTES})

        with patch("claudeChatCard.vaultSearch.confirm_pick", side_effect=FileExistsError):
            self.card.picker.picked.emit(NOTES[0]["path"])

        self.assertEqual(self.card.picker.outcome_label.text(), "couldn't save the note")

    def test_a_pick_whose_note_is_gone_says_the_link_was_skipped(self):
        lookup = self.startLookup()
        lookup.on_result({**CONCEPT_HIT, "notes": NOTES})

        with patch("claudeChatCard.vaultSearch.confirm_pick", return_value=None):
            self.card.picker.picked.emit(NOTES[0]["path"])

        self.assertEqual(self.card.picker.outcome_label.text(), "note not found — link skipped")

    def test_a_vocab_hit_shows_the_row_without_a_picker(self):
        lookup = self.startLookup("? 안녕")

        lookup.on_result({"hit": True, "kind": "vocab", "path": "Vocab.md", "content": "...", "row": ["안녕", "hello"], "notes": NOTES})

        self.assertIn("안녕", self.card.turns[-1]["text"])
        self.assertIn("hello", self.card.turns[-1]["text"])
        self.assertIsNone(self.card.picker)

    def test_a_vocab_miss_shows_claudes_answer_without_a_picker(self):
        lookup = self.startLookup("? 감사")

        lookup.on_result({"hit": False, "kind": "vocab", "draft": "감사 means thanks.", "notes": NOTES})

        self.assertIn("감사 means thanks.", self.card.turns[-1]["text"])
        self.assertIsNone(self.card.picker)

    def test_a_vocab_miss_without_an_answer_says_so(self):
        lookup = self.startLookup("? 감사")

        lookup.on_result({"hit": False, "kind": "vocab", "draft": "", "notes": NOTES})

        self.assertEqual(self.card.turns[-1]["text"], "couldn't draft an explanation.")
        self.assertIsNone(self.card.picker)

    def test_an_empty_draft_offers_nothing_to_save(self):
        lookup = self.startLookup()

        lookup.on_result({**CONCEPT_MISS, "draft": "", "notes": NOTES})

        self.assertIsNone(self.card.picker)

    def test_a_draft_that_could_never_be_saved_offers_no_picker(self):
        # "TCP/IP" isn't a valid Windows filename, so picking would only fail.
        lookup = self.startLookup("? TCP/IP")

        lookup.on_result({**CONCEPT_MISS, "notes": NOTES})

        self.assertIn("A drafted explanation.", self.card.turns[-1]["text"])
        self.assertIsNone(self.card.picker)

    def test_no_candidate_notes_means_no_picker(self):
        lookup = self.startLookup()

        lookup.on_result({**CONCEPT_HIT, "notes": []})

        self.assertIsNone(self.card.picker)

    def test_dismissing_cancels_an_in_flight_lookup(self):
        lookup = self.startLookup()

        self.card.dismiss()

        self.assertTrue(lookup.cancelled)
        self.assertIsNone(self.card.lookup)


class ChatSlotTests(unittest.TestCase):
    """The dedupe rule: reopening the same wedge's card reveals it instead
    of spawning another - the fix ticket 04 exists to pin down."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_dir = cardStore.STORE_DIR
        self.original_legacy_path = cardStore.LEGACY_STORE_PATH
        cardStore.STORE_DIR = Path(self.tmp.name) / "cards"
        cardStore.LEGACY_STORE_PATH = Path(self.tmp.name) / "cards.json"
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
        cardStore.STORE_DIR = self.original_dir
        cardStore.LEGACY_STORE_PATH = self.original_legacy_path
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

    def test_a_fresh_slot_defaults_to_the_top_right_corner(self):
        self.assertEqual(self.slot.corner, dockCorner.TOP_RIGHT)

    def test_a_dragged_corner_persists_to_a_new_chatslot_instance(self):
        card = self.slot.open(self.born, "hi", "wedge-1", self.fakeAction)
        card.animation.dockToCorner(dockCorner.BOTTOM_RIGHT)
        self.assertEqual(self.slot.corner, dockCorner.BOTTOM_RIGHT)

        fresh_slot = ChatSlot()
        self.assertEqual(fresh_slot.corner, dockCorner.BOTTOM_RIGHT)
        screen = QApplication.primaryScreen()
        expected = dockCorner.rect(dockCorner.BOTTOM_RIGHT, screen.availableGeometry(), style.CHAT_SIZE, style.CHAT_MARGIN)
        self.assertEqual(fresh_slot.dockRect(screen), expected)

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

    def test_opening_a_different_wedge_stops_the_old_cards_still_running_tween(self):
        # ticket 04: retire() is reached directly from open() (a different
        # wedge's session replacing this one), bypassing dismiss()'s own
        # edge_driver.stop() - a tween left running past teardown can fire
        # on_landed on an already-deleted card.
        first = self.slot.open(self.born, "hi", "wedge-1", self.fakeAction)
        first.edge_driver.motion = True  # force a real tween instead of an instant snap
        first.minimize()  # OPEN -> HIDDEN, starts a real geometry tween
        self.assertEqual(first.edge_driver.tween.state(), QVariantAnimation.Running)

        self.slot.open(self.born, "hi", "wedge-2", self.fakeAction)

        self.assertEqual(first.edge_driver.tween.state(), QVariantAnimation.Stopped)

    def test_dismissing_the_card_forgets_it_from_the_slot(self):
        self.slot.open(self.born, "hi", "wedge-1", self.fakeAction)
        self.slot.card.dismiss()
        self.assertIsNone(self.slot.card)

    def test_revealing_the_same_wedge_while_open_minimizes_it_instead(self):
        card = self.slot.open(self.born, "hi", "wedge-1", self.fakeAction)
        self.assertTrue(card.isOpen())
        handled = self.slot.reveal("wedge-1")
        self.assertTrue(handled)
        self.assertIs(self.slot.card, card)  # session stays alive, just tucked away
        self.assertFalse(card.isOpen())

    def test_revealing_the_same_wedge_while_hidden_reopens_and_focuses_the_composer(self):
        card = self.slot.open(self.born, "hi", "wedge-1", self.fakeAction)
        card.minimize()
        self.assertFalse(card.isOpen())

        handled = self.slot.reveal("wedge-1")

        self.assertTrue(handled)
        self.assertIs(self.slot.card, card)
        self.assertTrue(card.isOpen())
        card.activateWindow()
        QApplication.processEvents()
        self.assertTrue(card.composer.hasFocus())

    def test_revealing_an_unknown_wedge_leaves_the_open_card_alone(self):
        card = self.slot.open(self.born, "hi", "wedge-1", self.fakeAction)
        handled = self.slot.reveal("wedge-2")
        self.assertFalse(handled)
        self.assertIs(self.slot.card, card)


if __name__ == "__main__":
    unittest.main()
