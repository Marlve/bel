# Shared "press, then move past a few pixels, drags the window" gesture.
# Both the todo and note cards give this a different zone (design.md: the
# whole todo square vs. just the note's header/margins) but need the exact
# same press/move/release bookkeeping, so it lives once here instead of
# twice.

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtCore import Qt, QPointF

import style
from anims.clock import Tween
from anims import curves
from anims.pose import lerp


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
    shared with the todo card since both use the same corner-grip shape.
    A real child widget, not a hit-test region, so it sits above the card's
    other children (scroll area, text edit, ...) and a press there never
    falls through to their own drag/edit handling underneath.

    Per resize-handle/spec.md: a 20x20 hit zone (easy to grab) around a
    smaller 14x14 painted glyph (unobtrusive at rest) - enlarging the paint
    to match the hit zone was rejected as the thing that made the old grip
    read as a texture patch instead of a hint."""

    def __init__(self, card):
        super().__init__(card)
        self.card = card
        self.press_pos = None
        self.start_size = None
        self.dragging = False
        self.hover_t = 0.0  # 0 = rest ink, 1 = hover ink; frozen while dragging
        self.hover_tween = Tween(self, self.onHoverTick)
        self.setFixedSize(style.CARD_RESIZE_GRIP_HIT, style.CARD_RESIZE_GRIP_HIT)
        self.setCursor(Qt.SizeFDiagCursor)

    def reposition(self):
        # The card's own width/height is its top-level window, which is
        # bigger than the visible face by style.CARD_SHADOW_MARGIN on every
        # side (room for its drop shadow, see shadow.py). The hit zone then
        # sits right:1px/bottom:1px inside that face corner (spec.md), so it
        # overhangs the card's inner edge rather than leaving the border a
        # dead band.
        margin = style.CARD_SHADOW_MARGIN + style.CARD_RESIZE_GRIP_EDGE_OFFSET
        self.move(self.card.width() - margin - self.width(), self.card.height() - margin - self.height())
        self.raise_()

    def enterEvent(self, event):
        if not self.dragging:
            self.animateHoverTo(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.dragging:
            self.animateHoverTo(0.0)
        super().leaveEvent(event)

    def animateHoverTo(self, target):
        if not getattr(self.card, "motion", False):
            self.hover_tween.stop()
            self.hover_t = target
            self.update()
            return
        self.hover_tween.run(self.hover_t, target, style.CARD_RESIZE_GRIP_HOVER_MS, curves.CARD_RESIZE_GRIP_HOVER)

    def onHoverTick(self, value):
        self.hover_t = value
        self.update()

    def mousePressEvent(self, event):
        self.press_pos = event.globalPosition()
        self.start_size = self.card.size()
        self.dragging = True  # instant ink jump to the drag color, no tween
        self.hover_tween.stop()  # a hover tween mid-flight would keep overwriting hover_t after release
        self.update()
        self.card.update()  # border goes style.CARD_BORDER_DRAG while dragging

    def mouseMoveEvent(self, event):
        if self.press_pos is None:
            return
        min_width = style.CARD_MIN_WIDTH + 2 * style.CARD_SHADOW_MARGIN
        min_height = style.CARD_MIN_HEIGHT + 2 * style.CARD_SHADOW_MARGIN
        delta = event.globalPosition() - self.press_pos
        width = max(min_width, self.start_size.width() + int(delta.x()))
        height = max(min_height, self.start_size.height() + int(delta.y()))
        self.card.resize(width, height)
        self.reposition()

    def mouseReleaseEvent(self, event):
        self.press_pos = None
        self.dragging = False
        self.hover_t = 1.0 if self.underMouse() else 0.0  # reverts instantly, no tween out of the drag color
        self.update()
        self.card.update()
        self.card.scheduleSave()

    def inkColor(self):
        if self.dragging:
            return QColor(style.CARD_RESIZE_GRIP_DRAG)
        rest = QColor(style.CARD_RESIZE_GRIP_REST)
        hover = QColor(style.CARD_RESIZE_GRIP_HOVER)
        return QColor(
            int(lerp(rest.red(), hover.red(), self.hover_t)),
            int(lerp(rest.green(), hover.green(), self.hover_t)),
            int(lerp(rest.blue(), hover.blue(), self.hover_t)),
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(self.inkColor(), style.CARD_RESIZE_GRIP_STROKE)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        # 14x14 glyph inset style.CARD_RESIZE_GRIP_PAINT_OFFSET from the
        # card's own corner - since the hit zone already sits
        # CARD_RESIZE_GRIP_EDGE_OFFSET inside that same corner, that lands
        # the glyph this many px inside the hit zone's own edge.
        inset = style.CARD_RESIZE_GRIP_PAINT_OFFSET - style.CARD_RESIZE_GRIP_EDGE_OFFSET
        left = self.width() - inset - style.CARD_RESIZE_GRIP_PAINT
        top = self.height() - inset - style.CARD_RESIZE_GRIP_PAINT
        painter.drawLine(QPointF(left + 2.5, top + 11.5), QPointF(left + 11.5, top + 2.5))
        painter.drawLine(QPointF(left + 7, top + 11.5), QPointF(left + 11.5, top + 7))
