# Picking the todo/note wedges end-to-end through the real PieMenu wiring
# (test_pie_menu_flow.py stubs every wedge's action, so it never exercises
# actions/todo_action.py or note_action.py themselves).
#
# Asserts on the *new* card that appears after a pick, not an absolute count -
# other test files construct and deleteLater() their own TodoCard/NoteCard
# instances, and Qt's deferred deletion isn't guaranteed to have actually run
# by the time this file's tests execute in the same process.

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import card_store
from pie_menu import PieMenu, OPEN
from todo_card import TodoCard
from note_card import NoteCard

TODO_WEDGE = 0
NOTE_WEDGE = 1


class WedgeToggleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_path = card_store.STORE_PATH
        card_store.STORE_PATH = Path(self.tmp.name) / "cards.json"
        self.menu = PieMenu()
        self.menu.motion = False

    def tearDown(self):
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, (TodoCard, NoteCard)):
                widget.close()
                widget.deleteLater()
        self.menu.close()
        self.menu.deleteLater()
        QApplication.processEvents()
        card_store.STORE_PATH = self.original_path
        self.tmp.cleanup()

    def pickWedge(self, index):
        self.menu.openAtCursor()
        self.assertEqual(self.menu.phase, OPEN)
        self.menu.setHovered(index)
        self.menu.activateHoveredWedge()

    def existingIds(self, cls):
        return {id(w) for w in QApplication.topLevelWidgets() if isinstance(w, cls)}

    def newCards(self, cls, before_ids):
        return [w for w in QApplication.topLevelWidgets() if isinstance(w, cls) and id(w) not in before_ids]

    def test_picking_todo_opens_a_visible_card(self):
        before = self.existingIds(TodoCard)
        self.pickWedge(TODO_WEDGE)
        new = self.newCards(TodoCard, before)
        self.assertEqual(len(new), 1)
        self.assertTrue(new[0].isVisible())

    def test_picking_todo_twice_toggles_the_same_card_closed(self):
        before = self.existingIds(TodoCard)
        self.pickWedge(TODO_WEDGE)
        self.pickWedge(TODO_WEDGE)
        new = self.newCards(TodoCard, before)
        self.assertEqual(len(new), 1)  # one card built, reused on the second pick
        self.assertFalse(new[0].isVisible())

    def test_picking_note_opens_a_visible_card(self):
        before = self.existingIds(NoteCard)
        self.pickWedge(NOTE_WEDGE)
        new = self.newCards(NoteCard, before)
        self.assertEqual(len(new), 1)
        self.assertTrue(new[0].isVisible())


if __name__ == "__main__":
    unittest.main()
