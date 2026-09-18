# SettingsCard's own editing behaviour - separate from test_wedge_actions.py,
# which covers picking the Settings wedge through the real ring.

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

import cardStore
from settingsCard import SettingsCard


def key(code):
    return QKeyEvent(QEvent.KeyPress, code, Qt.NoModifier)


class SettingsCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_dir = cardStore.STORE_DIR
        self.original_legacy_path = cardStore.LEGACY_STORE_PATH
        cardStore.STORE_DIR = Path(self.tmp.name) / "cards"
        cardStore.LEGACY_STORE_PATH = Path(self.tmp.name) / "cards.json"
        self.changes = []
        self.card = SettingsCard(on_change=self.changes.append)

    def tearDown(self):
        self.card.close()
        self.card.deleteLater()
        cardStore.STORE_DIR = self.original_dir
        cardStore.LEGACY_STORE_PATH = self.original_legacy_path
        self.tmp.cleanup()

    def test_starts_with_the_default_rows_in_order(self):
        self.assertEqual([row.assigned_id for row in self.card.rows], ["todo", "note", "claude"])
        self.assertEqual([row.label_field.text() for row in self.card.rows], ["Todo", "Note", "Bel"])

    def test_editing_a_label_saves_and_notifies(self):
        self.card.rows[0].label_field.setText("Tasks")
        self.card.save()
        self.assertEqual(self.changes[-1][0], {"id": "todo", "label": "Tasks"})
        self.assertEqual(cardStore.load("wedges", None)[0], {"id": "todo", "label": "Tasks"})

    def test_blank_label_falls_back_to_untitled_rather_than_an_empty_wedge(self):
        self.card.rows[0].label_field.setText("   ")
        self.card.save()
        self.assertEqual(self.changes[-1][0]["label"], "Untitled")

    def test_picking_an_action_already_used_by_another_row_swaps_them(self):
        self.card.rows[0].action_combo.setCurrentIndex(self.card.rows[0].action_combo.findData("note"))
        self.assertEqual([row.assigned_id for row in self.card.rows], ["note", "todo", "claude"])
        # labels stay with their own row - only the underlying action moved
        self.assertEqual([row.label_field.text() for row in self.card.rows], ["Todo", "Note", "Bel"])
        self.assertEqual(self.changes[-1], [{"id": "note", "label": "Todo"}, {"id": "todo", "label": "Note"}, {"id": "claude", "label": "Bel"}])

    def test_reordering_moves_the_whole_row_not_just_the_id(self):
        self.card.rows[0].label_field.setText("Tasks")
        self.card.moveRow(self.card.rows[0], 1)
        self.assertEqual([row.assigned_id for row in self.card.rows], ["note", "todo", "claude"])
        self.assertEqual([row.label_field.text() for row in self.card.rows], ["Note", "Tasks", "Bel"])

    def test_arrows_are_disabled_at_the_ends(self):
        self.assertFalse(self.card.rows[0].up_button.isEnabled())
        self.assertTrue(self.card.rows[0].down_button.isEnabled())
        self.assertTrue(self.card.rows[-1].up_button.isEnabled())
        self.assertFalse(self.card.rows[-1].down_button.isEnabled())

    def test_escape_in_a_label_field_closes_the_card(self):
        self.card.show()
        handled = self.card.eventFilter(self.card.rows[0].label_field, key(Qt.Key_Escape))
        self.assertTrue(handled)
        self.assertFalse(self.card.isVisible())

    def test_hiding_flushes_a_pending_label_edit(self):
        self.card.show()  # hideEvent only fires when a visible widget is hidden
        self.card.rows[0].label_field.setText("Tasks")  # only schedules a debounced save
        self.card.hide()
        self.assertEqual(cardStore.load("wedges", None)[0]["label"], "Tasks")


if __name__ == "__main__":
    unittest.main()
