import math
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QEvent, QPoint
from PySide6.QtGui import QKeyEvent

import style
import cardStore
from noteCard import NoteCard, margin


def key(code):
    return QKeyEvent(QEvent.KeyPress, code, Qt.NoModifier)


class NoteCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_dir = cardStore.STORE_DIR
        self.original_legacy_path = cardStore.LEGACY_STORE_PATH
        cardStore.STORE_DIR = Path(self.tmp.name) / "cards"
        cardStore.LEGACY_STORE_PATH = Path(self.tmp.name) / "cards.json"
        self.card = NoteCard()

    def tearDown(self):
        self.card.close()
        self.card.deleteLater()
        QApplication.processEvents()  # actually run the deferred delete, or it outlives this test file
        cardStore.STORE_DIR = self.original_dir
        cardStore.LEGACY_STORE_PATH = self.original_legacy_path
        self.tmp.cleanup()

    def test_starts_empty(self):
        self.assertEqual(self.card.body.toPlainText(), "")

    def test_a_fresh_card_opens_at_the_default_width(self):
        self.assertEqual(self.card.width(), style.NOTE_DEFAULT_WIDTH + 2 * margin())

    def test_save_persists_text_and_size(self):
        self.card.body.setPlainText("pick up dry cleaning")
        self.card.resize(400, 385)
        self.card.save()

        saved = cardStore.load("note", None)
        self.assertEqual(saved["text"], "pick up dry cleaning")
        self.assertEqual(saved["size"], [400 - 2 * margin(), 385 - 2 * margin()])

    def test_a_fresh_card_picks_up_previously_saved_text_and_size(self):
        cardStore.save("note", {"text": "remember this", "size": [300, 260]})
        card = NoteCard()
        try:
            self.assertEqual(card.body.toPlainText(), "remember this")
            self.assertEqual((card.width(), card.height()), (300 + 2 * margin(), 260 + 2 * margin()))
        finally:
            card.close()
            card.deleteLater()
            QApplication.processEvents()

    def test_open_lands_the_card_near_the_given_cursor_position(self):
        # A cursor position safely away from every screen edge, so the
        # available-geometry clamp in moveNear doesn't kick in and mask
        # what's actually being tested here.
        self.card.moveNear(QPoint(100, 100))
        self.assertEqual(
            (self.card.x(), self.card.y()),
            (100 + style.CARD_SPAWN_OFFSET - margin(), 100 + style.CARD_SPAWN_OFFSET - margin()),
        )

    def test_save_persists_position(self):
        self.card.move(150, 220)
        self.card.save()
        saved = cardStore.load("note", None)
        self.assertEqual(saved["pos"], [150, 220])

    def test_a_fresh_card_picks_up_a_previously_saved_position(self):
        cardStore.save("note", {"text": "", "size": [300, 260], "pos": [150, 220]})
        card = NoteCard()
        try:
            self.assertEqual((card.x(), card.y()), (150, 220))
        finally:
            card.close()
            card.deleteLater()
            QApplication.processEvents()

    def test_a_saved_position_off_any_screen_is_clamped_back_onscreen(self):
        # e.g. a second monitor was unplugged since the position was saved.
        area = QApplication.primaryScreen().availableGeometry()
        off_screen = [area.x() + area.width() + 500, area.y() + area.height() + 500]
        cardStore.save("note", {"text": "", "size": [300, 260], "pos": off_screen})
        card = NoteCard()
        try:
            self.assertEqual(
                (card.x(), card.y()),
                (
                    area.x() + area.width() - style.CARD_EDGE_MARGIN - card.width(),
                    area.y() + area.height() - style.CARD_EDGE_MARGIN - card.height(),
                ),
            )
        finally:
            card.close()
            card.deleteLater()
            QApplication.processEvents()

    def test_open_moves_a_never_positioned_card_near_the_cursor(self):
        with patch("floatingCard.QCursor.pos", return_value=QPoint(100, 100)):
            self.card.open()
        self.assertEqual(
            (self.card.x(), self.card.y()),
            (100 + style.CARD_SPAWN_OFFSET - margin(), 100 + style.CARD_SPAWN_OFFSET - margin()),
        )

    def test_open_does_not_move_a_card_that_already_has_a_position(self):
        self.card.move(150, 220)
        self.card.positioned = True
        with patch("floatingCard.QCursor.pos", return_value=QPoint(500, 500)):
            self.card.open()
        self.assertEqual((self.card.x(), self.card.y()), (150, 220))

    def test_open_focuses_the_body(self):
        self.card.open()
        self.card.activateWindow()
        QApplication.processEvents()
        self.assertTrue(self.card.body.hasFocus())

    def test_close_button_hides_the_card(self):
        self.card.show()
        self.card.close_button.click()
        self.assertFalse(self.card.isVisible())

    def test_escape_hides_the_card(self):
        self.card.show()
        self.card.keyPressEvent(key(Qt.Key_Escape))
        self.assertFalse(self.card.isVisible())

    def test_escape_in_the_body_also_hides_the_card(self):
        self.card.show()
        handled = self.card.eventFilter(self.card.body, key(Qt.Key_Escape))
        self.assertTrue(handled)
        self.assertFalse(self.card.isVisible())

    def test_hiding_flushes_a_pending_save(self):
        self.card.show()  # hideEvent only fires when a visible widget is hidden
        self.card.body.setPlainText("last-minute note")  # schedules a debounced save
        self.card.hide()
        saved = cardStore.load("note", None)
        self.assertEqual(saved["text"], "last-minute note")

    def test_a_line_that_fits_the_body_never_scrolls_sideways(self):
        # QPlainTextDocumentLayout.blockWidth adds a hardcoded 8px (Qt's
        # default 4px margin, both sides) to a line's width, and a resize
        # reliably routes the layout through it - so a line within 8px of
        # the body's edge must still not scroll.
        self.card.show()
        self.card.body.setPlainText("a" * 20)
        QApplication.processEvents()
        layout = self.card.body.document().firstBlock().layout()
        slack = 4  # inside that 8px
        line_width = math.ceil(layout.lineAt(0).naturalTextWidth())

        self.card.resize(self.card.width() - (self.card.body.width() - line_width - slack), self.card.height())
        QApplication.processEvents()

        self.assertEqual(layout.lineCount(), 1)  # still fits on one line
        self.assertEqual(self.card.body.horizontalScrollBar().maximum(), 0)

    def test_typing_in_the_body_never_moves_the_window(self):
        # The body is a real child widget, so a press inside it must never
        # reach the card's own drag handling - only the chrome/margins around
        # it should be able to start a drag.
        origin = self.card.pos()
        self.card.body.setPlainText("some text")
        self.assertEqual(self.card.pos(), origin)


if __name__ == "__main__":
    unittest.main()
