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
from notePicker import NotePicker


def click(widget):
    for kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
        event = QMouseEvent(kind, QPointF(2, 2), QPointF(2, 2), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(widget, event)


class NotePickerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.notes = [
            {"path": str(Path("1 Project") / "Plan.md"), "recent": True},
            {"path": str(Path("2 Areas") / "Korean" / "Grammar.md"), "recent": False},
        ]
        self.picked = []
        self.picker = NotePicker(self.notes, 360)
        self.picker.picked.connect(self.picked.append)
        self.addCleanup(self.picker.deleteLater)

    def test_one_row_per_candidate_note_showing_name_and_folder(self):
        rows = self.picker.rows
        self.assertEqual([row.name_label.text() for row in rows], ["Plan", "Grammar"])
        self.assertEqual(
            [row.folder_label.text() for row in rows],
            ["1 Project", str(Path("2 Areas") / "Korean")],
        )

    def test_recent_notes_get_the_sand_dot_and_the_rest_grey(self):
        self.assertEqual(
            [row.dot.color for row in self.picker.rows],
            [style.PICKER_DOT_RECENT, style.PICKER_DOT_OLDER],
        )

    def test_clicking_a_row_picks_that_note(self):
        click(self.picker.rows[1])

        self.assertEqual(self.picked, [str(Path("2 Areas") / "Korean" / "Grammar.md")])

    def test_only_the_first_click_counts(self):
        # The pick is the confirmation - a second click must not write again.
        click(self.picker.rows[0])
        click(self.picker.rows[1])

        self.assertEqual(self.picked, [str(Path("1 Project") / "Plan.md")])

    def test_a_confirmation_row_appends_after_a_successful_pick(self):
        self.assertIsNone(self.picker.outcome_label)

        self.picker.showConnected("Plan")

        self.assertIn("connected to", self.picker.outcome_label.text())
        self.assertIn("<b>Plan</b>", self.picker.outcome_label.text())
        self.assertEqual(self.picker.outcome_dot.color, style.PICKER_DOT_RECENT)

    def test_the_header_defaults_to_the_note_question_and_can_be_replaced(self):
        self.assertEqual(self.picker.header_label.text(), "ambiguous — confirm the note")

        picker = NotePicker(self.notes, 360, header="new word — save it?")
        self.addCleanup(picker.deleteLater)

        self.assertEqual(picker.header_label.text(), "new word — save it?")

    def test_a_long_header_is_shortened_to_fit_the_picker(self):
        header = "a very long inbox note title that keeps going and going past the edge — pick a folder"
        picker = NotePicker(self.notes, 360, header=header)
        self.addCleanup(picker.deleteLater)

        picker.show()
        QApplication.processEvents()

        self.assertTrue(picker.header_label.text().endswith("…"))
        self.assertLessEqual(picker.header_label.geometry().right(), picker.width())
        self.assertEqual(picker.header_label.full_text, header)

    def test_a_saved_row_appends_after_a_vocab_pick(self):
        self.picker.showSaved("Vocab")

        self.assertIn("saved to <b>Vocab</b>", self.picker.outcome_label.text())
        self.assertEqual(self.picker.outcome_dot.color, style.PICKER_DOT_RECENT)

    def test_a_failed_pick_says_so_with_a_grey_dot(self):
        self.picker.showFailed("couldn't save the note")

        self.assertEqual(self.picker.outcome_label.text(), "couldn't save the note")
        self.assertEqual(self.picker.outcome_dot.color, style.PICKER_DOT_OLDER)

    def test_note_names_are_not_interpreted_as_markup(self):
        picker = NotePicker([{"path": "<b>x</b>.md", "recent": False}], 360)
        self.addCleanup(picker.deleteLater)
        picker.showConnected("<b>x</b>")

        self.assertEqual(picker.rows[0].name_label.textFormat(), Qt.PlainText)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", picker.outcome_label.text())

    def test_a_long_name_and_folder_path_shorten_instead_of_overflowing(self):
        long_path = str(Path("2 Areas") / "School" / "COMP2123 Data Structures" / "Week 7" / "Lecture notes on graph traversal algorithms.md")
        picker = NotePicker([{"path": long_path, "recent": True}], 360)
        self.addCleanup(picker.deleteLater)
        picker.show()
        QApplication.processEvents()

        row = picker.rows[0]
        self.assertLessEqual(row.width(), picker.scroll.viewport().width())
        self.assertTrue(row.folder_label.text().startswith("…"))
        self.assertTrue(row.folder_label.text().endswith("Week 7"))

    def test_list_height_is_capped(self):
        many = [{"path": f"Note {i}.md", "recent": False} for i in range(30)]
        picker = NotePicker(many, 360)
        self.addCleanup(picker.deleteLater)

        self.assertEqual(picker.scroll.height(), style.PICKER_LIST_MAX_HEIGHT)


class NotePickerFilterTests(unittest.TestCase):
    """Issue 24: a type-to-filter field between the header and the list."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.all_notes = [
            {"path": str(Path("1 Project") / "Plan.md"), "recent": True},
            {"path": str(Path("2 Areas") / "School" / "FIT3143 Week 3.md"), "recent": False},
            {"path": str(Path("2 Areas") / "Korean" / "Grammar.md"), "recent": False},
            {"path": str(Path("2 Areas") / "School" / "FIT3161 Notes.md"), "recent": False},
        ]
        self.recent = self.all_notes[:1]
        self.picked = []
        self.picker = NotePicker(self.recent, 360, all_notes=self.all_notes)
        self.picker.picked.connect(self.picked.append)
        self.addCleanup(self.picker.deleteLater)

    def names(self):
        return [row.name_label.full_text for row in self.picker.rows]

    def test_the_field_starts_empty_showing_the_recent_list(self):
        self.assertEqual(self.picker.filter_field.text(), "")
        self.assertEqual(self.picker.filter_field.placeholderText(), "filter notes…")
        self.assertEqual(self.names(), ["Plan"])

    def test_a_picker_without_all_notes_has_no_field(self):
        # The one-row "new word — save to vocab" picker.
        picker = NotePicker(self.recent, 360, header="new word — save to vocab")
        self.addCleanup(picker.deleteLater)

        self.assertIsNone(picker.filter_field)

    def test_typing_matches_note_names_across_the_whole_index_in_recency_order(self):
        self.picker.filter_field.setText("fit31")

        self.assertEqual(self.names(), ["FIT3143 Week 3", "FIT3161 Notes"])

    def test_typing_matches_the_folder_path_too(self):
        self.picker.filter_field.setText("SCHOOL")

        self.assertEqual(self.names(), ["FIT3143 Week 3", "FIT3161 Notes"])

    def test_filtering_a_shown_picker_keeps_the_list_tall_enough_to_see_the_rows(self):
        # Rows added to a visible picker aren't shown until the next event
        # loop pass, so a height measured right away used to come out 0.
        self.picker.show()
        QApplication.processEvents()

        self.picker.filter_field.setText("fit31")
        QApplication.processEvents()

        self.assertEqual(len(self.picker.rows), 2)
        self.assertTrue(all(row.isVisible() for row in self.picker.rows))
        self.assertGreaterEqual(self.picker.scroll.height(), sum(row.sizeHint().height() for row in self.picker.rows))

    def test_either_slash_matches_a_folder_separator(self):
        for text in ("areas/school", "areas\\school"):
            with self.subTest(text=text):
                self.picker.filter_field.setText(text)

                self.assertEqual(self.names(), ["FIT3143 Week 3", "FIT3161 Notes"])

    def test_the_md_suffix_is_not_matched(self):
        self.picker.filter_field.setText(".md")

        self.assertEqual(self.names(), [])

    def test_clearing_the_field_restores_the_recent_list(self):
        self.picker.filter_field.setText("grammar")
        self.picker.filter_field.setText("")

        self.assertEqual(self.names(), ["Plan"])
        self.assertTrue(self.picker.empty_label.isHidden())

    def test_no_match_says_so(self):
        self.picker.filter_field.setText("nothing like this")

        self.assertEqual(self.names(), [])
        self.assertFalse(self.picker.empty_label.isHidden())
        self.assertEqual(self.picker.empty_label.text(), "no matching notes")

    def test_clicking_a_filtered_row_picks_that_note(self):
        self.picker.filter_field.setText("grammar")

        click(self.picker.rows[0])

        self.assertEqual(self.picked, [str(Path("2 Areas") / "Korean" / "Grammar.md")])

    def test_the_field_locks_with_the_rows_after_a_pick(self):
        click(self.picker.rows[0])

        self.assertTrue(self.picker.filter_field.isReadOnly())

    def test_the_field_only_takes_focus_when_clicked(self):
        # The composer keeps focus when the picker pops in.
        self.assertEqual(self.picker.filter_field.focusPolicy(), Qt.ClickFocus)


if __name__ == "__main__":
    unittest.main()
