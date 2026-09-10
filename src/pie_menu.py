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
from actions import ACTIONS

INNER_RADIUS = style.PIE_DEADZONE  # hollow center matches the dead zone - nothing's selectable in there anyway


def wedge_index(dx, dy, count, deadzone=0, radius=None):
    """Index of the wedge (0 = up, going clockwise) that (dx, dy) points
    into, or None if the point is inside the deadzone or outside radius.
    dx/dy are a screen space offset from the menu's center - y grows
    downward.
    """
    dist = math.hypot(dx, dy)
    if dist < deadzone:
        return None
    if radius is not None and dist > radius:
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


# Which wedges the menu shows, in order. Each entry's "id" picks an action
# factory from ACTIONS; any other key is that action's own config (e.g.
# "claude" reads "prompt"). Hardcoded for now - once there's a settings UI,
# this is the shape it needs to produce.
WEDGE_CONFIG = [
    {"id": "announce", "label": "Up"},
    {"id": "announce", "label": "Right"},
    {"id": "announce", "label": "Down"},
    {"id": "announce", "label": "Left"},
    {"id": "claude", "label": "Claude"},
]


def build_wedges(config):
    return [Wedge(entry["label"], ACTIONS[entry["id"]](entry)) for entry in config]


class PieMenu(OverlayWindow):
    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        self.anchor = QPointF(0, 0)
        self.status = False
        self.hovered_wedge = None
        self.wedges = build_wedges(WEDGE_CONFIG)

        self.setWindowOpacity(0)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setGeometry(QApplication.primaryScreen().virtualGeometry())
        self.show()

    def onKeyPress(self):
      if self.status:
        self.closeMenu()
      else:
        self.openAtCursor()


    def openAtCursor(self):
        self.status = True
        self.anchor = QPointF(self.mapFromGlobal(QCursor.pos()))
        self.hovered_wedge = None
        self.repaint()  # bake the new anchor's frame in before revealing it
        self.setWindowOpacity(1)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.activateWindow()
        self.setFocus()
        self.grabMouse()

    def mouseMoveEvent(self, event):
        pos = event.position()
        dx = pos.x() - self.anchor.x()
        dy = pos.y() - self.anchor.y()
        current_index = wedge_index(dx, dy, len(self.wedges), style.PIE_DEADZONE, style.PIE_RADIUS)
        if self.hovered_wedge != current_index:
          self.hovered_wedge = current_index
          self.update()

    def mousePressEvent(self, event):
        if self.hovered_wedge is not None:
            self.wedges[self.hovered_wedge].action()
        self.closeMenu()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.closeMenu()

    def closeMenu(self):
        self.status = False
        self.releaseMouse()
        self.setWindowOpacity(0)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def paintEvent(self, event):
        print("painting")
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        wedge_width = 360 / len(self.wedges)
        cx, cy = self.anchor.x(), self.anchor.y()
        outer_rect = QRectF(cx - style.PIE_RADIUS, cy - style.PIE_RADIUS, style.PIE_RADIUS * 2, style.PIE_RADIUS * 2)
        inner_rect = QRectF(cx - INNER_RADIUS, cy - INNER_RADIUS, INNER_RADIUS * 2, INNER_RADIUS * 2)

        for i, wedge in enumerate(self.wedges):
            center_angle = (90 - i * wedge_width) % 360
            start_angle = center_angle - wedge_width / 2

            # Ring segment: outer arc, straight edge in, inner arc back, straight edge out.
            path = QPainterPath()
            path.arcMoveTo(outer_rect, start_angle)
            path.arcTo(outer_rect, start_angle, wedge_width)
            path.arcTo(inner_rect, start_angle + wedge_width, -wedge_width)
            path.closeSubpath()

            painter.setBrush(QColor(style.ACCENT) if i == self.hovered_wedge else QColor(style.BACKGROUND))
            painter.setPen(QColor(style.BORDER))
            painter.drawPath(path)

            label_angle = math.radians(center_angle)
            label_r = (style.PIE_RADIUS + INNER_RADIUS) / 2
            lx = cx + label_r * math.cos(label_angle)
            ly = cy - label_r * math.sin(label_angle)
            painter.setPen(QColor(style.TEXT))
            painter.drawText(QPointF(lx - 12, ly + 5), wedge.label)
