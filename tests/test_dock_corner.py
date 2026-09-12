import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtCore import QPoint, QRect

import dockCorner
from dockCorner import TOP_LEFT, TOP_RIGHT, BOTTOM_LEFT, BOTTOM_RIGHT


class IsLeftTopTests(unittest.TestCase):
    def test_left_corners(self):
        self.assertTrue(dockCorner.is_left(TOP_LEFT))
        self.assertTrue(dockCorner.is_left(BOTTOM_LEFT))

    def test_right_corners(self):
        self.assertFalse(dockCorner.is_left(TOP_RIGHT))
        self.assertFalse(dockCorner.is_left(BOTTOM_RIGHT))

    def test_top_corners(self):
        self.assertTrue(dockCorner.is_top(TOP_LEFT))
        self.assertTrue(dockCorner.is_top(TOP_RIGHT))

    def test_bottom_corners(self):
        self.assertFalse(dockCorner.is_top(BOTTOM_LEFT))
        self.assertFalse(dockCorner.is_top(BOTTOM_RIGHT))


class NearestTests(unittest.TestCase):
    def setUp(self):
        self.area = QRect(0, 0, 1000, 800)

    def test_top_left_quadrant(self):
        self.assertEqual(dockCorner.nearest(QPoint(10, 10), self.area), TOP_LEFT)

    def test_top_right_quadrant(self):
        self.assertEqual(dockCorner.nearest(QPoint(990, 10), self.area), TOP_RIGHT)

    def test_bottom_left_quadrant(self):
        self.assertEqual(dockCorner.nearest(QPoint(10, 790), self.area), BOTTOM_LEFT)

    def test_bottom_right_quadrant(self):
        self.assertEqual(dockCorner.nearest(QPoint(990, 790), self.area), BOTTOM_RIGHT)

    def test_area_with_a_nonzero_origin(self):
        area = QRect(500, 300, 1000, 800)
        self.assertEqual(dockCorner.nearest(QPoint(1490, 1090), area), BOTTOM_RIGHT)
        self.assertEqual(dockCorner.nearest(QPoint(510, 310), area), TOP_LEFT)


class RectTests(unittest.TestCase):
    def setUp(self):
        self.area = QRect(0, 0, 1000, 800)
        self.size = 400
        self.margin = 8

    def test_top_right(self):
        r = dockCorner.rect(TOP_RIGHT, self.area, self.size, self.margin)
        self.assertEqual(r.top(), self.margin)
        self.assertEqual(r.right(), self.area.width() - self.margin)
        self.assertEqual(r.width(), self.size)
        self.assertEqual(r.height(), self.size)

    def test_top_left(self):
        r = dockCorner.rect(TOP_LEFT, self.area, self.size, self.margin)
        self.assertEqual(r.top(), self.margin)
        self.assertEqual(r.left(), self.margin)

    def test_bottom_right(self):
        r = dockCorner.rect(BOTTOM_RIGHT, self.area, self.size, self.margin)
        self.assertEqual(r.bottom(), self.area.height() - self.margin)
        self.assertEqual(r.right(), self.area.width() - self.margin)

    def test_bottom_left(self):
        r = dockCorner.rect(BOTTOM_LEFT, self.area, self.size, self.margin)
        self.assertEqual(r.bottom(), self.area.height() - self.margin)
        self.assertEqual(r.left(), self.margin)


if __name__ == "__main__":
    unittest.main()
