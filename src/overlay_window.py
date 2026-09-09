# Base window every overlay (todo list, etc.) builds on top of.
# Frameless, translucent, always on top - looks like an overlay, not an app window.

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt

import style


class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(style.overlay_stylesheet())
