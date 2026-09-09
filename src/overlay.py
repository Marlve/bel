# Base window every overlay (todo list, etc.) builds on top of.
# Frameless, translucent, always on top - looks like an overlay, not an app window.

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor
from PySide6.QtCore import Qt, QRectF

import style


class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint  # no titlebar
            | Qt.WindowStaysOnTopHint  # stays above other windows
            | Qt.Tool  # no taskbar icon, skipped in Alt+Tab
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(style.overlay_stylesheet())

    def paintEvent(self, event):
        # Test square so we can see the overlay is actually rendering. Remove once a real feature draws here.
        size = 50
        x = self.width() / 2 - size / 2
        y = self.height() / 2 - size / 2
        painter = QPainter(self)
        painter.fillRect(QRectF(x, y, size, size), QColor(style.ACCENT))
