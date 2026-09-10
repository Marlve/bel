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
from settings_card import SettingsCard

TODO_WEDGE = 0
NOTE_WEDGE = 1
SETTINGS_WEDGE = 2


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
            if isinstance(widget, (TodoCard, NoteCard, SettingsCard)):
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

    def test_picking_settings_opens_a_visible_card(self):
        before = self.existingIds(SettingsCard)
        self.pickWedge(SETTINGS_WEDGE)
        new = self.newCards(SettingsCard, before)
        self.assertEqual(len(new), 1)
        self.assertTrue(new[0].isVisible())

    def test_an_unrelated_settings_save_does_not_orphan_an_open_todo_card(self):
        # A settings save rebuilds every wedge's config; build_wedges() is
        # what's supposed to keep this same TodoCard reachable afterward
        # rather than losing it behind a freshly-built toggle closure.
        before_todo = self.existingIds(TodoCard)
        self.pickWedge(TODO_WEDGE)
        todo_card = self.newCards(TodoCard, before_todo)[0]
        self.assertTrue(todo_card.isVisible())

        before_settings = self.existingIds(SettingsCard)
        self.pickWedge(SETTINGS_WEDGE)
        settings_card = self.newCards(SettingsCard, before_settings)[0]
        settings_card.rows[-1].label_field.setText("Ask AI")  # unrelated to the todo wedge
        settings_card.save()

        self.pickWedge(TODO_WEDGE)  # toggles the *same* card closed if it's still wired up
        self.assertFalse(todo_card.isVisible())

    def test_settings_save_is_reflected_in_the_ring_immediately(self):
        before_settings = self.existingIds(SettingsCard)
        self.pickWedge(SETTINGS_WEDGE)
        settings_card = self.newCards(SettingsCard, before_settings)[0]
        settings_card.rows[0].label_field.setText("Tasks")
        settings_card.save()

        self.assertEqual(self.menu.wedges[TODO_WEDGE].label, "Tasks")


if __name__ == "__main__":
    unittest.main()
