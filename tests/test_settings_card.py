# SettingsCard's own editing behaviour - separate from test_wedge_actions.py,
# which covers picking the Settings wedge through the real ring.

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QEvent, QPointF
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import cardStore
import style
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

    def ids(self):
        return [entry["id"] for entry in self.card.entries]

    def wedgeCenter(self, index):
        """Where to click to hit wedge `index` of the preview - the middle of its label, out on the bisector."""
        from anims import pose
        preview = self.card.ring_preview
        bx, by = pose.bisector(index, len(preview.config))
        radius = style.RING_LABEL * preview.radius()
        return QPointF(preview.width() / 2 + bx * radius, preview.height() / 2 + by * radius)

    def click(self, index):
        preview = self.card.ring_preview
        QTest.mouseClick(preview, Qt.LeftButton, Qt.NoModifier, self.wedgeCenter(index).toPoint())

    def drag(self, source, target):
        preview = self.card.ring_preview
        QTest.mousePress(preview, Qt.LeftButton, Qt.NoModifier, self.wedgeCenter(source).toPoint())
        QTest.mouseRelease(preview, Qt.LeftButton, Qt.NoModifier, self.wedgeCenter(target).toPoint())

    def test_starts_with_the_default_wedges_in_order(self):
        self.assertEqual(self.ids(), ["todo", "note", "claude"])
        self.assertEqual([entry["label"] for entry in self.card.entries], ["Todo", "Note", "Bel"])

    def test_the_preview_shows_the_ring_with_settings_pinned_in(self):
        self.assertEqual([entry["id"] for entry in self.card.ring_preview.config], ["todo", "note", "settings", "claude"])

    def test_moving_a_wedge_to_a_place_shifts_the_others_and_saves(self):
        self.card.moveWedge("todo", 2)
        self.assertEqual(self.ids(), ["note", "claude", "todo"])
        self.assertEqual([entry["id"] for entry in self.changes[-1]], ["note", "claude", "todo"])
        self.assertEqual([entry["id"] for entry in cardStore.load("wedges", None)], ["note", "claude", "todo"])

    def test_moving_a_wedge_to_where_it_already_is_changes_nothing(self):
        self.card.moveWedge("note", 1)
        self.assertEqual(self.changes, [])

    def test_saved_wedges_carry_their_default_names(self):
        self.card.moveWedge("todo", 1)
        self.assertEqual([entry["label"] for entry in self.changes[-1]], ["Note", "Todo", "Bel"])

    def test_dragging_one_wedge_onto_another_moves_it_there(self):
        self.drag(0, 3)  # Todo onto Bel: last
        self.assertEqual(self.ids(), ["note", "claude", "todo"])

    def test_clicking_a_wedge_then_another_moves_the_first_there(self):
        self.click(3)  # pick up Bel
        self.assertEqual(self.card.ring_preview.selected, "claude")
        self.click(0)  # ...and put it where Todo is
        self.assertEqual(self.ids(), ["claude", "todo", "note"])
        self.assertIsNone(self.card.ring_preview.selected)

    def test_clicking_the_picked_up_wedge_again_puts_it_back_down(self):
        self.click(1)
        self.click(1)
        self.assertIsNone(self.card.ring_preview.selected)
        self.assertEqual(self.ids(), ["todo", "note", "claude"])

    def test_the_settings_wedge_can_be_neither_picked_up_nor_dropped_on(self):
        self.click(2)
        self.assertIsNone(self.card.ring_preview.selected)
        self.drag(0, 2)
        self.drag(2, 0)
        self.assertEqual(self.ids(), ["todo", "note", "claude"])

    def test_escape_in_the_calendar_field_closes_the_card(self):
        self.card.show()
        handled = self.card.eventFilter(self.card.link_field, key(Qt.Key_Escape))
        self.assertTrue(handled)
        self.assertFalse(self.card.isVisible())


if __name__ == "__main__":
    unittest.main()
