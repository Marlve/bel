# `! ss` (.scratch/screenshot-ask/issues/01): drag a rectangle on the
# screen, and the crop rides along on the next chat message. The screen is
# frozen the moment the selector opens, so what you crop is what you saw when
# you asked - not whatever changed underneath while you were dragging.

from datetime import datetime

from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtCore import Qt, QRect, QPoint, Signal

import style
from claude import SHOTS_DIR
from util import force_foreground

MIN_SIDE = 8  # a drag smaller than this is a stray click, not a selection
CHIP_THUMB_HEIGHT = 36
DIM = QColor(0, 0, 0, 110)


def save(pixmap):
    """Writes the crop where `claude` may read it (SHOTS_DIR sits inside its
    cwd, the one place a headless call can read without a permission prompt)
    and returns the path."""
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SHOTS_DIR / f"shot-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.png"
    if not pixmap.save(str(path), "PNG"):
        raise OSError(f"couldn't write {path}")
    return path


class RegionSelector(QWidget):
    """A dimmed, frozen copy of one screen to drag a rectangle over. Esc or a
    right click cancels."""

    selected = Signal(object)  # the cropped QPixmap, in the screen's real pixels
    cancelled = Signal()

    def __init__(self, screen, frozen):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setGeometry(screen.geometry())
        self.setCursor(Qt.CrossCursor)
        self.frozen = frozen
        self.origin = None
        self.selection = QRect()

    def open(self):
        self.show()
        self.raise_()
        force_foreground(int(self.winId()))  # or Esc goes to whatever app was focused
        self.activateWindow()
        self.setFocus()

    def source(self, rect):
        """`rect` in widget coordinates -> the same area of the frozen pixmap,
        whose pixels are device pixels, not logical ones."""
        scale = self.frozen.devicePixelRatio()
        return QRect(
            round(rect.x() * scale), round(rect.y() * scale),
            round(rect.width() * scale), round(rect.height() * scale),
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.frozen)
        painter.fillRect(self.rect(), DIM)
        if not self.selection.isEmpty():
            painter.drawPixmap(self.selection, self.frozen, self.source(self.selection))
            painter.setPen(QPen(QColor(style.CHAT_ACCENT), 1))
            painter.drawRect(self.selection.adjusted(0, 0, -1, -1))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.origin = event.position().toPoint()
            self.selection = QRect(self.origin, self.origin)
        else:
            self.cancelled.emit()

    def mouseMoveEvent(self, event):
        if self.origin is not None:
            # QRect(p1, p2) includes both corner pixels; the -1 makes the
            # crop exactly as wide as the drag.
            self.selection = QRect(self.origin, event.position().toPoint()).normalized().adjusted(0, 0, -1, -1)
            self.update()

    def mouseReleaseEvent(self, event):
        if self.origin is None or event.button() != Qt.LeftButton:
            return
        rect = self.selection.intersected(self.rect())
        self.origin = None
        if rect.width() < MIN_SIDE or rect.height() < MIN_SIDE:
            self.cancelled.emit()
            return
        self.selected.emit(self.frozen.copy(self.source(rect)))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.cancelled.emit()


class ShotChip(QWidget):
    """The pending screenshot above the composer: a thumbnail and a way to
    drop it before sending."""

    cleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.thumb = QLabel()
        self.thumb.setStyleSheet(f"border: 1px solid {style.CHAT_BORDER}; background: transparent;")
        note = QLabel("screenshot attached")
        note.setStyleSheet(f"color: {style.MUTED}; background: transparent;")
        remove = QPushButton("✕", self)
        remove.setFixedSize(18, 18)
        remove.setCursor(Qt.PointingHandCursor)
        remove.setStyleSheet(style.chat_close_stylesheet())
        remove.clicked.connect(self.cleared)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, style.SPACE_2)
        row.setSpacing(style.SPACE_2)
        row.addWidget(self.thumb)
        row.addWidget(note)
        row.addStretch(1)
        row.addWidget(remove)

    def show_shot(self, pixmap):
        self.thumb.setPixmap(thumbnail(pixmap, CHIP_THUMB_HEIGHT))


def thumbnail(pixmap, height):
    """A copy scaled to `height` logical pixels, crisp on a high-DPI screen."""
    scale = pixmap.devicePixelRatio()
    scaled = pixmap.scaledToHeight(round(height * scale), Qt.SmoothTransformation)
    scaled.setDevicePixelRatio(scale)
    return scaled
