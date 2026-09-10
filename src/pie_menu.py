# Concept for ADR-0006: hotkey opens a circle around the cursor, split into
# wedges; moving the mouse toward one highlights it, clicking runs that
# wedge's action.

import math
from dataclasses import dataclass
from typing import Callable

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPainter, QColor, QCursor, QPainterPath
from PySide6.QtCore import Qt, QPointF, QRectF

import style
from overlay import OverlayWindow
from wedge_actions import announce, ClaudeAction

RADIUS = style.PIE_RADIUS
DEADZONE = style.PIE_DEADZONE
INNER_RADIUS = DEADZONE  # hollow center matches the dead zone - nothing's selectable in there anyway


def wedge_index(dx, dy, count, deadzone=0):
    """Index of the wedge (0 = up, going clockwise) that (dx, dy) points
    into, or None if the point is inside the deadzone. dx/dy are a screen
    space offset from the menu's center - y grows downward.
    """
    if math.hypot(dx, dy) < deadzone:
        return None

    math_angle = math.degrees(math.atan2(-dy, dx)) % 360  # 0=right, 90=up
    compass_angle = (90 - math_angle) % 360  # 0=up, 90=right, clockwise
    wedge_width = 360 / count
    shifted = (compass_angle + wedge_width / 2) % 360
    return int(shifted // wedge_width)


@dataclass
class Wedge:
    label: str
    action: Callable[[], None]


class PieMenu(OverlayWindow):
    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        self._anchor = QPointF(0, 0)
        self._active = None
        self._wedges = [
            Wedge("Up", announce("Up")),
            Wedge("Right", announce("Right")),
            Wedge("Down", announce("Down")),
            Wedge("Left", announce("Left")),
            Wedge("Claude", ClaudeAction()),
        ]

    def open_at_cursor(self):
        # Cover the whole virtual desktop (all monitors) so the mouse can never
        # leave the widget mid-gesture - direction is read from the anchor
        # point (where the hotkey was pressed), not from the widget's center.
        self.setGeometry(QApplication.primaryScreen().virtualGeometry())
        self._anchor = QPointF(self.mapFromGlobal(QCursor.pos()))
        self._active = None
        self.show() # Shows widget / calls paintEvent
        self.activateWindow()
        self.setFocus()
        self.grabMouse()

    def mouseMoveEvent(self, event):
        pos = event.position()
        dx = pos.x() - self._anchor.x()
        dy = pos.y() - self._anchor.y()
        self._active = wedge_index(dx, dy, len(self._wedges), DEADZONE)
        self.update()

    def mousePressEvent(self, event):
        if self._active is not None:
            self._wedges[self._active].action()
        self._close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._close()

    def _close(self):
        self.releaseMouse()
        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        wedge_width = 360 / len(self._wedges)
        cx, cy = self._anchor.x(), self._anchor.y()
        outer_rect = QRectF(cx - RADIUS, cy - RADIUS, RADIUS * 2, RADIUS * 2)
        inner_rect = QRectF(cx - INNER_RADIUS, cy - INNER_RADIUS, INNER_RADIUS * 2, INNER_RADIUS * 2)

        for i, wedge in enumerate(self._wedges):
            center_angle = (90 - i * wedge_width) % 360
            start_angle = center_angle - wedge_width / 2

            # Ring segment: outer arc, straight edge in, inner arc back, straight edge out.
            path = QPainterPath()
            path.arcMoveTo(outer_rect, start_angle)
            path.arcTo(outer_rect, start_angle, wedge_width)
            path.arcTo(inner_rect, start_angle + wedge_width, -wedge_width)
            path.closeSubpath()

            painter.setBrush(QColor(style.ACCENT) if i == self._active else QColor(style.BACKGROUND))
            painter.setPen(QColor(style.BORDER))
            painter.drawPath(path)

            label_angle = math.radians(center_angle)
            label_r = (RADIUS + INNER_RADIUS) / 2
            lx = cx + label_r * math.cos(label_angle)
            ly = cy - label_r * math.sin(label_angle)
            painter.setPen(QColor(style.TEXT))
            painter.drawText(QPointF(lx - 12, ly + 5), wedge.label)
