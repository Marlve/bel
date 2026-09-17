import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

import style
from organizeList import OrganizeList, organize_details

FOLDERS = ["1 Project", "2 Areas", "2 Areas/School"]
PLACED = {
    "path": Path("C:/vault/0 Inbox/Assignment ETW.md"), "folder": "2 Areas/School/ETW2001", "new_folder": True,
    "title": "ETW Report", "name": "ETW Report", "related": ["Week 3", "Studies"], "atlas": "5 Atlas/School.md",
}
UNPLACED = {
    "path": Path("C:/vault/0 Inbox/Loose idea.md"), "folder": None, "new_folder": False,
    "title": "Loose idea", "name": "Loose idea", "related": [], "atlas": None,
}


def click(widget):
    for kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
        event = QMouseEvent(kind, QPointF(2, 2), QPointF(2, 2), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(widget, event)


class OrganizeDetailsTests(unittest.TestCase):
    def test_lists_everything_filing_does_beyond_the_move(self):
        self.assertEqual(organize_details(PLACED), "new folder · renamed ETW Report · links Week 3, Studies · listed in School")

    def test_a_plain_move_has_no_details(self):
        plain = dict(PLACED, new_folder=False, name="Assignment ETW", related=[], atlas=None)

        self.assertEqual(organize_details(plain), "")

    def test_a_note_without_a_folder_has_no_details(self):
        self.assertEqual(organize_details(UNPLACED), "")


class OrganizeListTests(unittest.TestCase):
    """command-styling/01: one box, one row per Inbox note, and clicking a
    row files that note."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.box = OrganizeList([PLACED, UNPLACED], FOLDERS, 360)
        self.addCleanup(self.box.deleteLater)
        self.filed = []
        for entry in self.box.entries:
            entry.filed.connect(lambda folder, entry=entry: self.filed.append((entry.proposal, folder)))
        self.placed, self.unplaced = self.box.entries

    def test_one_row_per_note_with_its_name_and_target_folder(self):
        self.assertEqual([entry.row.name_label.full_text for entry in self.box.entries], ["Assignment ETW", "Loose idea"])
        self.assertEqual([entry.row.folder_label.full_text for entry in self.box.entries], ["2 Areas/School/ETW2001", "pick a folder"])

    def test_rows_have_no_dots(self):
        self.assertTrue(all(entry.row.dot is None for entry in self.box.entries))

    def test_the_details_sit_on_the_rows_second_line(self):
        self.assertFalse(self.placed.row.detail_label.isHidden())
        self.assertEqual(self.placed.row.detail_label.text(), organize_details(PLACED))
        self.assertTrue(self.unplaced.row.detail_label.isHidden())

    def test_rows_are_split_by_a_divider_except_the_last(self):
        self.assertEqual([entry.divided for entry in self.box.entries], [True, False])

    def test_clicking_a_proposal_files_the_note_in_its_folder(self):
        click(self.placed.row)

        self.assertEqual(self.filed, [(PLACED, "2 Areas/School/ETW2001")])

    def test_only_the_first_click_on_a_row_counts(self):
        click(self.placed.row)
        click(self.placed.row)

        self.assertEqual(len(self.filed), 1)

    def test_a_note_without_a_folder_starts_collapsed(self):
        self.assertIsNone(self.placed.folder_list)
        self.assertTrue(self.unplaced.folder_list.isHidden())

    def test_clicking_a_note_without_a_folder_expands_the_folder_list_instead_of_filing(self):
        click(self.unplaced.row)

        self.assertFalse(self.unplaced.folder_list.isHidden())
        self.assertEqual([row.path for row in self.unplaced.folder_list.rows], FOLDERS)
        self.assertEqual(self.unplaced.folder_list.filter_field.placeholderText(), "filter folders…")
        self.assertEqual(self.filed, [])

    def test_clicking_it_again_collapses_the_list(self):
        click(self.unplaced.row)
        click(self.unplaced.row)

        self.assertTrue(self.unplaced.folder_list.isHidden())

    def test_the_filter_narrows_the_folders(self):
        click(self.unplaced.row)

        self.unplaced.folder_list.filter_field.setText("school")

        self.assertEqual([row.path for row in self.unplaced.folder_list.rows], ["2 Areas/School"])

    def test_picking_a_folder_files_the_note_there_and_collapses_the_list(self):
        click(self.unplaced.row)

        click(self.unplaced.folder_list.rows[0])

        self.assertEqual(self.filed, [(UNPLACED, "1 Project")])
        self.assertTrue(self.unplaced.folder_list.isHidden())
        self.assertEqual(self.unplaced.row.folder_label.full_text, "1 Project")
        self.assertFalse(self.unplaced.row.enabled)

    def test_a_filed_row_dims_and_says_moved(self):
        click(self.placed.row)

        self.placed.showMoved(linked=True)

        self.assertEqual(self.placed.row.name_color, style.PICKER_DIM_TEXT)
        self.assertEqual(self.placed.row.detail_label.text(), "moved")

    def test_a_move_whose_links_failed_says_so(self):
        click(self.placed.row)

        self.placed.showMoved(linked=False)

        self.assertEqual(self.placed.row.detail_label.text(), "moved, but couldn't add its links")

    def test_a_failed_move_stays_bright_and_says_so(self):
        click(self.unplaced.row)
        click(self.unplaced.folder_list.rows[0])

        self.unplaced.showFailed()

        self.assertEqual(self.unplaced.row.name_color, style.PICKER_NOTE_TEXT)
        self.assertFalse(self.unplaced.row.detail_label.isHidden())
        self.assertEqual(self.unplaced.row.detail_label.text(), "couldn't move the note")

    def test_filing_one_row_leaves_the_others_clickable(self):
        click(self.placed.row)
        self.placed.showMoved(linked=True)

        self.assertTrue(self.unplaced.row.enabled)
        self.assertEqual(self.unplaced.row.name_color, style.PICKER_NOTE_TEXT)


if __name__ == "__main__":
    unittest.main()
