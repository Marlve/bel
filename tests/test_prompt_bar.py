# Characterization safety net for PromptBar ahead of ticket 07's split -
# pins down current behavior, no behavior changes here.

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt, QVariantAnimation
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

import style
from promptBar import PromptBar
from promptBarState import EMPTY, TYPING, SENDING, REJECTED


def key(code):
    return QKeyEvent(QEvent.KeyPress, code, Qt.NoModifier)


class PromptBarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.bar = PromptBar()
        self.bar.motion = False  # deterministic: reject()'s shake lands in one step

    def tearDown(self):
        self.bar.close()
        self.bar.deleteLater()
        QApplication.processEvents()

    # --- launching ---

    def test_launch_with_no_seed_starts_empty(self):
        self.bar.launch("Ask Bel anything…")
        self.assertEqual(self.bar.state, EMPTY)
        self.assertEqual(self.bar.field.text(), "")
        self.assertEqual(self.bar.field.placeholderText(), "Ask Bel anything…")
        self.assertFalse(self.bar.field.isVisible())  # place() hasn't landed it yet

    def test_launch_with_a_seed_starts_typing(self):
        self.bar.launch("Ask Bel anything…", seed="w")
        self.assertEqual(self.bar.state, TYPING)
        self.assertEqual(self.bar.field.text(), "w")

    def test_launch_resets_a_previous_sessions_leftovers(self):
        self.bar.launch("first")
        self.bar.field.setText("some text")
        self.bar.submit()
        self.assertEqual(self.bar.state, SENDING)

        self.bar.launch("second")
        self.assertEqual(self.bar.state, EMPTY)
        self.assertEqual(self.bar.field.text(), "")
        self.assertFalse(self.bar.field.isReadOnly())
        self.assertEqual(self.bar.rect_opacity, 0.0)
        self.assertEqual(self.bar.chrome_opacity, 0.0)

    # --- field states ---

    def test_typing_non_blank_text_sets_state_typing(self):
        self.bar.launch("placeholder")
        self.bar.field.setText("hi")
        self.assertEqual(self.bar.state, TYPING)

    def test_clearing_the_text_sets_state_empty(self):
        self.bar.launch("placeholder")
        self.bar.field.setText("hi")
        self.bar.field.clear()
        self.assertEqual(self.bar.state, EMPTY)

    def test_whitespace_only_text_counts_as_empty(self):
        self.bar.launch("placeholder")
        self.bar.field.setText("   ")
        self.assertEqual(self.bar.state, EMPTY)

    def test_editing_after_a_rejection_clears_it(self):
        self.bar.launch("placeholder")
        self.bar.submit()  # blank submit -> rejected
        self.assertEqual(self.bar.state, REJECTED)
        self.bar.field.setText("now typing")
        self.assertEqual(self.bar.state, TYPING)

    def test_text_changes_while_sending_are_ignored(self):
        self.bar.launch("placeholder")
        self.bar.field.setText("hello")
        self.bar.submit()
        self.assertEqual(self.bar.state, SENDING)
        self.bar.field.setText("more text")  # programmatic, bypasses read-only
        self.assertEqual(self.bar.state, SENDING)

    # --- submit/reject ---

    def test_submit_with_text_emits_submitted_and_enters_sending(self):
        self.bar.launch("placeholder")
        self.bar.field.setText("  hello  ")
        seen = []
        self.bar.submitted.connect(seen.append)
        self.bar.submit()
        self.assertEqual(seen, ["hello"])  # stripped
        self.assertEqual(self.bar.state, SENDING)
        self.assertTrue(self.bar.field.isReadOnly())

    def test_submit_with_blank_text_rejects_instead_of_submitting(self):
        self.bar.launch("placeholder")
        seen = []
        self.bar.submitted.connect(seen.append)
        self.bar.submit()
        self.assertEqual(seen, [])
        self.assertEqual(self.bar.state, REJECTED)

    def test_rejecting_does_not_animate_when_motion_is_off(self):
        self.bar.launch("placeholder")
        self.bar.submit()
        self.assertNotEqual(self.bar.shake.state(), QVariantAnimation.Running)

    def test_rejecting_shakes_when_motion_is_on(self):
        self.bar.motion = True
        self.bar.launch("placeholder")
        self.bar.submit()
        self.assertEqual(self.bar.state, REJECTED)
        self.assertEqual(self.bar.shake.state(), QVariantAnimation.Running)

    # --- escape handling ---

    def test_escape_on_the_field_emits_cancelled(self):
        self.bar.launch("placeholder")
        seen = []
        self.bar.cancelled.connect(lambda: seen.append(True))
        handled = self.bar.eventFilter(self.bar.field, key(Qt.Key_Escape))
        self.assertTrue(handled)
        self.assertEqual(len(seen), 1)

    def test_other_keys_on_the_field_pass_through_unhandled(self):
        self.bar.launch("placeholder")
        handled = self.bar.eventFilter(self.bar.field, key(Qt.Key_A))
        self.assertFalse(handled)

    # --- flight/placement ---

    def test_set_flight_updates_the_opacities(self):
        self.bar.setFlight(0.5, 0.25)
        self.assertEqual(self.bar.rect_opacity, 0.5)
        self.assertEqual(self.bar.chrome_opacity, 0.25)

    def test_place_lays_the_field_out_inside_the_insets_and_reveals_it(self):
        self.bar.launch("placeholder")
        self.bar.resize(200, 44)
        self.bar.place()
        self.assertTrue(self.bar.field.isVisible())
        geometry = self.bar.field.geometry()
        self.assertEqual(
            (geometry.x(), geometry.y(), geometry.width(), geometry.height()),
            (style.FIELD_INSET_LEFT, 0, 200 - style.FIELD_INSET_LEFT - style.FIELD_INSET_RIGHT, 44),
        )

    def test_place_is_a_no_op_once_the_field_is_already_visible(self):
        self.bar.launch("placeholder")
        self.bar.place()
        rest_x = self.bar.rest_x
        self.bar.move(999, self.bar.y())
        self.bar.place()  # field already visible - must not re-capture rest_x
        self.assertEqual(self.bar.rest_x, rest_x)

    def test_take_focus_places_the_caret_after_seeded_text(self):
        self.bar.launch("placeholder", seed="hello")
        self.bar.place()
        self.bar.takeFocus()
        self.assertEqual(self.bar.field.cursorPosition(), len("hello"))

    def test_append_seed_appends_to_the_existing_text(self):
        self.bar.launch("placeholder", seed="he")
        self.bar.appendSeed("llo")
        self.assertEqual(self.bar.field.text(), "hello")

    def test_screen_rect_reflects_size(self):
        self.bar.resize(200, 44)
        rect = self.bar.screenRect()
        self.assertEqual((rect.width(), rect.height()), (200, 44))

    # --- mouse handling ---

    def test_pressing_the_frame_before_placement_does_nothing(self):
        self.bar.launch("placeholder")
        self.bar.mousePressEvent(None)
        self.assertFalse(self.bar.field.hasFocus())

    def test_pressing_the_frame_once_placed_focuses_the_field(self):
        self.bar.launch("placeholder")
        self.bar.place()
        self.bar.activateWindow()
        QApplication.processEvents()
        self.bar.mousePressEvent(None)
        self.assertTrue(self.bar.field.hasFocus())


if __name__ == "__main__":
    unittest.main()
