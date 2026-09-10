import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtCore import QPoint, QPointF

from draggable import WindowDrag


class FakeWindow:
    def __init__(self, x, y):
        self._pos = QPoint(x, y)
        self.move_calls = []

    def pos(self):
        return self._pos

    def move(self, point):
        self._pos = point
        self.move_calls.append(point)


class WindowDragTests(unittest.TestCase):
    def test_small_movement_does_not_drag(self):
        window = FakeWindow(100, 100)
        drag = WindowDrag(window)
        drag.press(QPointF(0, 0))
        moved = drag.move(QPointF(2, 2))  # under the 4px threshold
        self.assertFalse(moved)
        self.assertEqual(window.move_calls, [])

    def test_movement_past_threshold_drags_by_the_delta(self):
        window = FakeWindow(100, 100)
        drag = WindowDrag(window)
        drag.press(QPointF(0, 0))
        moved = drag.move(QPointF(10, -5))
        self.assertTrue(moved)
        self.assertEqual(window.pos(), QPoint(110, 95))

    def test_once_dragging_further_small_moves_still_count(self):
        window = FakeWindow(100, 100)
        drag = WindowDrag(window)
        drag.press(QPointF(0, 0))
        drag.move(QPointF(10, 0))  # crosses the threshold, starts the drag
        drag.move(QPointF(11, 0))  # a 1px follow-up should still move it
        self.assertEqual(window.pos(), QPoint(111, 100))

    def test_release_reports_whether_a_drag_happened(self):
        window = FakeWindow(100, 100)
        drag = WindowDrag(window)

        drag.press(QPointF(0, 0))
        drag.move(QPointF(1, 1))  # never crosses the threshold
        self.assertFalse(drag.release())

        drag.press(QPointF(0, 0))
        drag.move(QPointF(10, 10))
        self.assertTrue(drag.release())

    def test_release_resets_state_for_the_next_press(self):
        window = FakeWindow(100, 100)
        drag = WindowDrag(window)
        drag.press(QPointF(0, 0))
        drag.move(QPointF(10, 10))
        drag.release()
        self.assertFalse(drag.dragging)
        self.assertIsNone(drag.press_pos)


if __name__ == "__main__":
    unittest.main()
