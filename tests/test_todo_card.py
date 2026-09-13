import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt, QEvent, QPoint
from PySide6.QtGui import QKeyEvent

import style
import cardStore
from todoCard import TodoCard, TodoList, margin


def key(code):
    return QKeyEvent(QEvent.KeyPress, code, Qt.NoModifier)


# TodoList's own constructor doubles as the Qt parent, so the stub has to be
# a real QWidget rather than a plain object.
class StubCard(QWidget):
    def __init__(self):
        super().__init__()
        self.motion = False
        self.saved = 0

    def scheduleSave(self):
        self.saved += 1

    def updateOpenCount(self):
        pass


class TodoListTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_row_at_maps_y_to_the_right_index(self):
        card = TodoList(card=None)
        card.setItems([{"text": "a", "done": False}, {"text": "b", "done": False}])
        self.assertEqual(card.rowAt(0), 0)
        self.assertEqual(card.rowAt(35), 0)
        self.assertEqual(card.rowAt(36), 1)
        self.assertIsNone(card.rowAt(1000))

    def test_toggle_flips_done_and_schedules_a_save(self):
        stub = StubCard()
        list_widget = TodoList(stub)
        list_widget.setItems([{"text": "a", "done": False}])
        list_widget.toggle(0)
        self.assertTrue(list_widget.items[0]["done"])
        self.assertEqual(stub.saved, 1)

    def test_ticking_a_row_schedules_its_removal(self):
        stub = StubCard()
        list_widget = TodoList(stub)
        list_widget.setItems([{"text": "a", "done": False}])
        list_widget.toggle(0)
        self.assertIn(id(list_widget.items[0]), list_widget.remove_timers)

    def test_a_row_still_ticked_is_gone_once_its_timer_fires(self):
        stub = StubCard()
        list_widget = TodoList(stub)
        list_widget.setItems([{"text": "a", "done": False}, {"text": "b", "done": False}])
        item = list_widget.items[0]
        list_widget.toggle(0)
        list_widget.removeIfStillDone(item)  # simulate the delay elapsing
        self.assertEqual(list_widget.items, [{"text": "b", "done": False}])

    def test_unticking_before_the_timer_fires_cancels_the_removal(self):
        stub = StubCard()
        list_widget = TodoList(stub)
        list_widget.setItems([{"text": "a", "done": False}])
        item = list_widget.items[0]
        list_widget.toggle(0)  # done - removal scheduled
        list_widget.toggle(0)  # undone again - should cancel it
        self.assertNotIn(id(item), list_widget.remove_timers)
        list_widget.removeIfStillDone(item)  # even if this still fires, it's a no-op now
        self.assertEqual(list_widget.items, [{"text": "a", "done": False}])

    def test_removal_only_drops_the_exact_ticked_item(self):
        # Two rows with identical content are still distinct objects - the
        # timer for one must never remove the other.
        stub = StubCard()
        list_widget = TodoList(stub)
        list_widget.setItems([{"text": "a", "done": False}, {"text": "a", "done": False}])
        first, second = list_widget.items
        list_widget.toggle(0)
        list_widget.removeIfStillDone(first)
        self.assertEqual(list_widget.items, [{"text": "a", "done": False}])
        self.assertIs(list_widget.items[0], second)


class TodoCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_path = cardStore.STORE_PATH
        cardStore.STORE_PATH = Path(self.tmp.name) / "cards.json"
        self.card = TodoCard()

    def tearDown(self):
        self.card.close()
        self.card.deleteLater()
        QApplication.processEvents()  # actually run the deferred delete, or it outlives this test file
        cardStore.STORE_PATH = self.original_path
        self.tmp.cleanup()

    def test_starts_with_no_items(self):
        self.assertEqual(self.card.list.items, [])

    def test_scrollbar_never_draws_over_content(self):
        # A visible thumb clipped list-item text under it - still
        # scrollable via wheel/drag, just no drawn bar.
        self.assertEqual(self.card.scroll.verticalScrollBarPolicy(), Qt.ScrollBarAlwaysOff)

    def test_a_fresh_card_opens_at_the_default_width(self):
        self.assertEqual(self.card.width(), style.TODO_DEFAULT_WIDTH + 2 * margin())

    def test_header_count_reflects_open_items(self):
        self.assertEqual(self.card.header_count_label.text(), "0 OPEN")
        self.card.add_field.setText("buy milk")
        self.card.addItem()
        self.assertEqual(self.card.header_count_label.text(), "1 OPEN")
        self.card.list.toggle(0)
        self.assertEqual(self.card.header_count_label.text(), "0 OPEN")
        self.card.list.toggle(0)
        self.assertEqual(self.card.header_count_label.text(), "1 OPEN")

    def test_typing_and_enter_adds_an_item(self):
        self.card.add_field.setText("buy milk")
        self.card.addItem()
        self.assertEqual(self.card.list.items, [{"text": "buy milk", "done": False}])
        self.assertEqual(self.card.add_field.text(), "")

    def test_blank_text_adds_nothing(self):
        self.card.add_field.setText("   ")
        self.card.addItem()
        self.assertEqual(self.card.list.items, [])

    def test_save_persists_items_and_size(self):
        self.card.add_field.setText("water plants")
        self.card.addItem()
        self.card.resize(400, 385)
        self.card.save()

        saved = cardStore.load("todo", None)
        self.assertEqual(saved["items"], [{"text": "water plants", "done": False}])
        self.assertEqual(saved["size"], [400 - 2 * margin(), 385 - 2 * margin()])

    def test_a_fresh_card_picks_up_previously_saved_items_and_size(self):
        cardStore.save("todo", {"items": [{"text": "old item", "done": True}], "size": [300, 260]})
        card = TodoCard()
        try:
            self.assertEqual(card.list.items, [{"text": "old item", "done": True}])
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
        saved = cardStore.load("todo", None)
        self.assertEqual(saved["pos"], [150, 220])

    def test_a_fresh_card_picks_up_a_previously_saved_position(self):
        cardStore.save("todo", {"items": [], "size": [300, 260], "pos": [150, 220]})
        card = TodoCard()
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
        cardStore.save("todo", {"items": [], "size": [300, 260], "pos": off_screen})
        card = TodoCard()
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

    def test_open_focuses_the_add_field(self):
        self.card.open()
        self.card.activateWindow()
        QApplication.processEvents()
        self.assertTrue(self.card.add_field.hasFocus())

    def test_reopening_after_hide_focuses_the_add_field_again(self):
        self.card.open()
        self.card.hide()
        self.card.add_field.clearFocus()

        self.card.open()

        self.card.activateWindow()
        QApplication.processEvents()
        self.assertTrue(self.card.add_field.hasFocus())

    def test_close_button_hides_the_card(self):
        self.card.show()
        self.card.close_button.click()
        self.assertFalse(self.card.isVisible())

    def test_escape_hides_the_card(self):
        self.card.show()
        self.card.keyPressEvent(key(Qt.Key_Escape))
        self.assertFalse(self.card.isVisible())

    def test_escape_in_the_add_field_also_hides_the_card(self):
        self.card.show()
        handled = self.card.eventFilter(self.card.add_field, key(Qt.Key_Escape))
        self.assertTrue(handled)
        self.assertFalse(self.card.isVisible())

    def test_hiding_flushes_a_pending_save(self):
        self.card.show()  # hideEvent only fires when a visible widget is hidden
        self.card.add_field.setText("urgent")
        self.card.addItem()  # schedules a debounced save, not yet written
        self.card.hide()
        saved = cardStore.load("todo", None)
        self.assertEqual(saved["items"], [{"text": "urgent", "done": False}])


if __name__ == "__main__":
    unittest.main()
