import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QEvent, QPoint
from PySide6.QtGui import QKeyEvent

import style
import cardStore
from noteCard import NoteCard, MARGIN


def key(code):
    return QKeyEvent(QEvent.KeyPress, code, Qt.NoModifier)


class NoteCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_path = cardStore.STORE_PATH
        cardStore.STORE_PATH = Path(self.tmp.name) / "cards.json"
        self.card = NoteCard()

    def tearDown(self):
        self.card.close()
        self.card.deleteLater()
        QApplication.processEvents()  # actually run the deferred delete, or it outlives this test file
        cardStore.STORE_PATH = self.original_path
        self.tmp.cleanup()

    def test_starts_empty(self):
        self.assertEqual(self.card.body.toPlainText(), "")

    def test_save_persists_text_and_size(self):
        self.card.body.setPlainText("pick up dry cleaning")
        self.card.resize(400, 385)
        self.card.save()

        saved = cardStore.load("note", None)
        self.assertEqual(saved["text"], "pick up dry cleaning")
        self.assertEqual(saved["size"], [400 - 2 * MARGIN, 385 - 2 * MARGIN])

    def test_a_fresh_card_picks_up_previously_saved_text_and_size(self):
        cardStore.save("note", {"text": "remember this", "size": [300, 260]})
        card = NoteCard()
        try:
            self.assertEqual(card.body.toPlainText(), "remember this")
            self.assertEqual((card.width(), card.height()), (300 + 2 * MARGIN, 260 + 2 * MARGIN))
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
            (100 + style.CARD_SPAWN_OFFSET - MARGIN, 100 + style.CARD_SPAWN_OFFSET - MARGIN),
        )

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

    def test_typing_in_the_body_never_moves_the_window(self):
        # The body is a real child widget, so a press inside it must never
        # reach the card's own drag handling - only the chrome/margins around
        # it should be able to start a drag.
        origin = self.card.pos()
        self.card.body.setPlainText("some text")
        self.assertEqual(self.card.pos(), origin)


if __name__ == "__main__":
    unittest.main()
