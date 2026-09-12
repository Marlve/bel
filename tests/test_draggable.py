import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, QVariantAnimation
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QWidget

import style
from draggable import WindowDrag, ResizeGrip


class FakeWindow:
    def __init__(self, x, y, width=100, height=100):
        self._pos = QPoint(x, y)
        self._width = width
        self._height = height
        self.move_calls = []

    def pos(self):
        return self._pos

    def width(self):
        return self._width

    def height(self):
        return self._height

    def move(self, point):
        self._pos = point
        self.move_calls.append(point)


class WindowDragTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

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

    def test_dragging_cannot_push_the_window_past_the_right_or_bottom_edge(self):
        area = (QApplication.screenAt(QPoint(0, 0)) or QApplication.primaryScreen()).availableGeometry()
        window = FakeWindow(100, 100, width=50, height=50)
        drag = WindowDrag(window)
        drag.press(QPointF(0, 0))
        drag.move(QPointF(area.width(), area.height()))  # drag way past the bottom-right corner
        self.assertEqual(
            window.pos(),
            QPoint(
                area.x() + area.width() - style.CARD_EDGE_MARGIN - 50,
                area.y() + area.height() - style.CARD_EDGE_MARGIN - 50,
            ),
        )

    def test_dragging_cannot_push_the_window_past_the_left_or_top_edge(self):
        area = (QApplication.screenAt(QPoint(0, 0)) or QApplication.primaryScreen()).availableGeometry()
        window = FakeWindow(100, 100, width=50, height=50)
        drag = WindowDrag(window)
        drag.press(QPointF(0, 0))
        drag.move(QPointF(-area.width(), -area.height()))  # drag way past the top-left corner
        self.assertEqual(
            window.pos(), QPoint(area.x() + style.CARD_EDGE_MARGIN, area.y() + style.CARD_EDGE_MARGIN)
        )

    def test_dragging_within_bounds_is_unaffected_by_the_clamp(self):
        window = FakeWindow(100, 100, width=50, height=50)
        drag = WindowDrag(window)
        drag.press(QPointF(0, 0))
        drag.move(QPointF(10, -5))
        self.assertEqual(window.pos(), QPoint(110, 95))


class FakeMouseEvent:
    """ResizeGrip's handlers only ever read globalPosition() off the event
    they're given - a real QMouseEvent needs several args PySide has no
    simple constructor for, so a bare stand-in is enough, same spirit as
    FakeWindow above."""

    def __init__(self, global_pos):
        self._pos = global_pos

    def globalPosition(self):
        return self._pos


class FakeCard(QWidget):
    def __init__(self, width=400, height=400):
        super().__init__()
        self.motion = False
        self.save_calls = 0
        self.resize(width, height)

    def scheduleSave(self):
        self.save_calls += 1


class ResizeGripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.card = FakeCard()
        self.grip = ResizeGrip(self.card)

    def test_reposition_sits_one_px_inside_the_face_corner(self):
        self.grip.reposition()
        margin = style.CARD_SHADOW_MARGIN + style.CARD_RESIZE_GRIP_EDGE_OFFSET
        self.assertEqual(
            self.grip.pos(),
            QPoint(self.card.width() - margin - self.grip.width(), self.card.height() - margin - self.grip.height()),
        )

    def test_dragging_resizes_the_card_by_the_delta(self):
        self.grip.mousePressEvent(FakeMouseEvent(QPointF(0, 0)))
        self.grip.mouseMoveEvent(FakeMouseEvent(QPointF(30, 10)))
        self.assertEqual((self.card.width(), self.card.height()), (430, 410))

    def test_dragging_never_moves_the_card_only_resizes_it(self):
        # Anchored top-left per spec.md: only the bottom-right corner moves.
        origin = self.card.pos()
        self.grip.mousePressEvent(FakeMouseEvent(QPointF(0, 0)))
        self.grip.mouseMoveEvent(FakeMouseEvent(QPointF(30, 10)))
        self.assertEqual(self.card.pos(), origin)

    def test_dragging_clamps_to_the_200x120_minimum(self):
        self.grip.mousePressEvent(FakeMouseEvent(QPointF(0, 0)))
        self.grip.mouseMoveEvent(FakeMouseEvent(QPointF(-1000, -1000)))
        margin = style.CARD_SHADOW_MARGIN
        self.assertEqual(
            (self.card.width(), self.card.height()),
            (style.CARD_MIN_WIDTH + 2 * margin, style.CARD_MIN_HEIGHT + 2 * margin),
        )

    def test_press_marks_dragging_and_release_clears_it_and_schedules_a_save(self):
        self.grip.mousePressEvent(FakeMouseEvent(QPointF(0, 0)))
        self.assertTrue(self.grip.dragging)
        self.grip.mouseReleaseEvent(FakeMouseEvent(QPointF(0, 0)))
        self.assertFalse(self.grip.dragging)
        self.assertEqual(self.card.save_calls, 1)

    def test_ink_color_while_dragging_is_the_drag_color(self):
        self.grip.mousePressEvent(FakeMouseEvent(QPointF(0, 0)))
        self.assertEqual(self.grip.inkColor(), QColor(style.CARD_RESIZE_GRIP_DRAG))

    def test_ink_color_at_rest_and_at_full_hover(self):
        self.assertEqual(self.grip.inkColor(), QColor(style.CARD_RESIZE_GRIP_REST))
        self.grip.hover_t = 1.0
        self.assertEqual(self.grip.inkColor(), QColor(style.CARD_RESIZE_GRIP_HOVER))

    def test_hover_jumps_instantly_with_motion_off(self):
        self.card.motion = False
        self.grip.animateHoverTo(1.0)
        self.assertEqual(self.grip.hover_t, 1.0)
        self.assertNotEqual(self.grip.hover_tween.state(), QVariantAnimation.Running)

    def test_hover_animates_over_120ms_with_motion_on(self):
        self.card.motion = True
        self.grip.animateHoverTo(1.0)
        self.assertEqual(self.grip.hover_tween.state(), QVariantAnimation.Running)
        self.assertEqual(self.grip.hover_tween.duration(), style.CARD_RESIZE_GRIP_HOVER_MS)

    def test_entering_while_dragging_does_not_disturb_the_drag_ink(self):
        self.grip.mousePressEvent(FakeMouseEvent(QPointF(0, 0)))
        self.grip.enterEvent(None)
        self.assertEqual(self.grip.hover_t, 0.0)  # animateHoverTo was skipped, not just interrupted mid-flight

    def test_pressing_mid_hover_tween_stops_it(self):
        # Otherwise a hover animation already in flight keeps ticking through
        # the drag and overwrites the release's instant hover_t snap.
        self.card.motion = True
        self.grip.animateHoverTo(1.0)
        self.assertEqual(self.grip.hover_tween.state(), QVariantAnimation.Running)
        self.grip.mousePressEvent(FakeMouseEvent(QPointF(0, 0)))
        self.assertNotEqual(self.grip.hover_tween.state(), QVariantAnimation.Running)


if __name__ == "__main__":
    unittest.main()
