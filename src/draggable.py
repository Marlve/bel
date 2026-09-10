# Shared "press, then move past a few pixels, drags the window" gesture.
# Both the todo and note cards give this a different zone (design.md: the
# whole todo square vs. just the note's header/margins) but need the exact
# same press/move/release bookkeeping, so it lives once here instead of
# twice.

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtCore import Qt

import style


class WindowDrag:
    def __init__(self, window):
        self.window = window
        self.press_pos = None
        self.window_pos = None
        self.dragging = False

    def press(self, global_pos):
        self.press_pos = global_pos
        self.window_pos = self.window.pos()
        self.dragging = False

    def move(self, global_pos):
        """Moves the window once the press has travelled far enough to count
        as a drag rather than a click. Returns whether a drag is under way,
        so a caller like a todo row can tell a tick from a drag."""
        if self.press_pos is None:
            return self.dragging
        delta = global_pos - self.press_pos
        if not self.dragging and delta.x() ** 2 + delta.y() ** 2 < style.CARD_DRAG_THRESHOLD_PX ** 2:
            return False
        self.dragging = True
        self.window.move(self.window_pos + delta.toPoint())
        return True

    def release(self):
        was_dragging = self.dragging
        self.press_pos = None
        self.dragging = False
        return was_dragging


class ResizeGrip(QWidget):
    """Bottom-right corner handle that resizes its window instead of moving
    it - design.md's note for the note card ("add a corner resize grip"),
    shared with the todo card since both are the same fixed-square shape.
    A real child widget, not a hit-test region, so it sits above the card's
    other children (scroll area, text edit, ...) and a press there never
    falls through to their own drag/edit handling underneath."""

    def __init__(self, card):
        super().__init__(card)
        self.card = card
        self.press_pos = None
        self.start_size = None
        self.setFixedSize(style.CARD_RESIZE_GRIP, style.CARD_RESIZE_GRIP)
        self.setCursor(Qt.SizeFDiagCursor)

    def reposition(self):
        # The card's own width/height is its top-level window, which is
        # bigger than the visible face by style.CARD_SHADOW_MARGIN on every
        # side (room for its drop shadow, see shadow.py) - the grip belongs
        # at the face's corner, not the window's.
        margin = style.CARD_SHADOW_MARGIN
        self.move(self.card.width() - margin - self.width(), self.card.height() - margin - self.height())
        self.raise_()

    def mousePressEvent(self, event):
        self.press_pos = event.globalPosition()
        self.start_size = self.card.size()

    def mouseMoveEvent(self, event):
        if self.press_pos is None:
            return
        min_size = style.CARD_MIN_SIZE + 2 * style.CARD_SHADOW_MARGIN
        delta = event.globalPosition() - self.press_pos
        width = max(min_size, self.start_size.width() + int(delta.x()))
        height = max(min_size, self.start_size.height() + int(delta.y()))
        self.card.resize(width, height)
        self.reposition()

    def mouseReleaseEvent(self, event):
        self.press_pos = None
        self.card.scheduleSave()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(style.CHAT_BORDER_TAB), 1.5))
        size = self.width()
        for offset in (size - 4, size - 8, size - 12):
            painter.drawLine(offset, size - 2, size - 2, offset)
