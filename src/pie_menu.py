# Concept for ADR-0006: hotkey opens a circle around the cursor, split into
# wedges; moving the mouse toward one highlights it, clicking selects it and
# prints the choice. Wedges aren't wired to real features yet - this only
# proves the keybind -> menu -> selection mechanism works.

import math

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QCursor
from PySide6.QtCore import Qt, QPointF

import style
from pie_math import wedge_index

LABELS = ["Up", "Right", "Down", "Left"]
RADIUS = 90
DEADZONE = 20


class PieMenu(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        size = RADIUS * 2 + 20
        self.resize(size, size)
        self._active = None

    def open_at_cursor(self):
        cursor = QCursor.pos()
        self.move(cursor.x() - self.width() // 2, cursor.y() - self.height() // 2)
        self._active = None
        self.show()
        self.activateWindow()
        self.setFocus()
        self.grabMouse()

    def mouseMoveEvent(self, event):
        pos = event.position()
        dx = pos.x() - self.width() / 2
        dy = pos.y() - self.height() / 2
        self._active = wedge_index(dx, dy, len(LABELS), DEADZONE)
        self.update()

    def mousePressEvent(self, event):
        if self._active is not None:
            print(f"selected: {LABELS[self._active]}")
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

        wedge_width = 360 / len(LABELS)
        cx, cy = self.width() / 2, self.height() / 2

        for i, label in enumerate(LABELS):
            center_angle = (90 - i * wedge_width) % 360
            start_angle = center_angle - wedge_width / 2

            painter.setBrush(QColor(style.ACCENT) if i == self._active else QColor(style.BACKGROUND))
            painter.setPen(QColor(style.BORDER))
            painter.drawPie(
                int(cx - RADIUS), int(cy - RADIUS), RADIUS * 2, RADIUS * 2,
                int(start_angle * 16), int(wedge_width * 16),
            )

            label_angle = math.radians(center_angle)
            label_r = RADIUS * 0.6
            lx = cx + label_r * math.cos(label_angle)
            ly = cy - label_r * math.sin(label_angle)
            painter.setPen(QColor(style.TEXT))
            painter.drawText(QPointF(lx - 12, ly + 5), label)
