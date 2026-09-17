import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import style
from dueList import DueList

TODAY = [(None, [("FIT3143 Lecture", "10:00–12:00"), ("ETW Assignment due", "all day")])]
WEEK = [("Thu 17 Sep", [("FIT3143 Lecture", "10:00–12:00")]), ("Sat 19 Sep", [("ETW Assignment due", "all day")])]


class DueListTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def dueList(self, boxes, width=600):
        due_list = DueList(boxes, width)
        self.addCleanup(due_list.deleteLater)
        due_list.show()
        return due_list

    def test_one_row_per_item_with_its_name_and_due_label(self):
        due_list = self.dueList(TODAY)

        self.assertEqual(
            [(row.name_label.text(), row.due_label.text()) for row in due_list.rows],
            [("FIT3143 Lecture", "10:00–12:00"), ("ETW Assignment due", "all day")],
        )

    def test_today_has_no_heading(self):
        self.assertEqual(self.dueList(TODAY).headings, [])

    def test_week_heads_each_days_box_with_its_day(self):
        due_list = self.dueList(WEEK)

        self.assertEqual([heading.text() for heading in due_list.headings], ["Thu 17 Sep", "Sat 19 Sep"])
        self.assertEqual(len(due_list.boxes), 2)

    def test_rows_are_divided_except_the_last_in_each_box(self):
        due_list = self.dueList(TODAY + WEEK)

        self.assertEqual(
            [style.DUE_DIVIDER in row.styleSheet() for row in due_list.rows],
            [True, False, False, False],
        )

    def test_a_long_name_is_cut_short_but_the_due_label_stays_whole(self):
        due_list = self.dueList([(None, [("THEORY OF COMPUTATION, Applied Session, Group 12", "16:00–18:00")])], width=220)

        [row] = due_list.rows
        self.assertTrue(row.name_label.text().endswith("…"))
        self.assertEqual(row.due_label.text(), "16:00–18:00")

    def test_takes_the_width_it_is_given(self):
        self.assertEqual(self.dueList(WEEK, width=300).width(), 300)


if __name__ == "__main__":
    unittest.main()
