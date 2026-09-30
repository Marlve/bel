# Shared "fade in near the cursor" open flow for the note and todo cards -
# open()/onFadeTick()/moveNear() were duplicated identically between them
# except each card's own post-show step (NoteCard's scrollbar-flash flush,
# TodoCard's add-field focus). Those stay in each subclass via the
# afterShow()/afterRaise() hooks below, at the same point in the sequence
# they occupied before this split. First shared base class among this
# codebase's cards (ticket 09).

from PySide6.QtGui import QCursor, QColor, QPainterPath, QPen
from PySide6.QtCore import Qt, QRectF, QPointF, QPoint

import style
import screenBounds
from anims import curves


def paint_card_bands(painter, frame, radius, body_color, header_bottom, divider_y):
    """The header/body two-tone fill shared by todo, notes, and chat's card
    shell, clipped to the card's rounded frame: a header-colored band down
    to `header_bottom`, `body_color` for the rest, and one divider line at
    `divider_y` (the header/body seam for notes, the body/footer seam for
    todo/chat)."""
    path = QPainterPath()
    path.addRoundedRect(frame, radius, radius)
    painter.save()
    painter.setClipPath(path)
    painter.fillRect(frame, QColor(body_color))
    painter.fillRect(
        QRectF(frame.left(), frame.top(), frame.width(), header_bottom - frame.top()),
        QColor(style.SURFACE),
    )
    painter.setPen(QPen(QColor(style.CARD_DIVIDER), 1))
    painter.drawLine(QPointF(frame.left(), divider_y), QPointF(frame.right(), divider_y))
    painter.restore()


def paint_header_accent(painter, title, header_bottom):
    """A short accent rule under a card's title, sitting on the header's lower edge -
    todo and notes share it so the accent shows on both even with nothing selected."""
    painter.save()
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(style.CHAT_ACCENT))
    painter.drawRect(QRectF(title.x(), header_bottom - style.ACCENT_RULE_HEIGHT, title.width(), style.ACCENT_RULE_HEIGHT))
    painter.restore()


class FloatingCard:
    positioned = False  # set once a real position is known, from a restore or a first moveNear

    def open(self):
        """Lands near wherever the wedge was picked, like the ring itself -
        but only the first time a card has never had a position of its own.
        After that it stays wherever it was left, restored or dragged."""
        if not self.positioned:
            self.moveNear(QCursor.pos())
        self.setWindowOpacity(0 if self.motion else 1)
        self.show()
        self.afterShow()
        self.raise_()
        self.afterRaise()
        if self.motion:
            self.fade.run(0.0, 1.0, style.CARD_OPEN_MS, curves.CHAT_FLIGHT)

    def afterShow(self):
        pass

    def afterRaise(self):
        pass

    def onFadeTick(self, value):
        self.setWindowOpacity(value)

    def moveNear(self, cursor_pos):
        area = screenBounds.available_area(cursor_pos, margin=style.CARD_EDGE_MARGIN)
        x = cursor_pos.x() + style.CARD_SPAWN_OFFSET - style.CARD_SHADOW_MARGIN
        y = cursor_pos.y() + style.CARD_SPAWN_OFFSET - style.CARD_SHADOW_MARGIN
        x = screenBounds.clamp(x, area.x(), area.x() + area.width() - self.width())
        y = screenBounds.clamp(y, area.y(), area.y() + area.height() - self.height())
        self.move(x, y)
        self.positioned = True

    def restorePosition(self, pos):
        """Applies a position saved from a previous session, clamped like
        every other placement here in case it no longer falls on any screen
        (a monitor unplugged, or a resolution changed, since it was saved)."""
        x, y = pos
        area = screenBounds.available_area(QPoint(x, y), margin=style.CARD_EDGE_MARGIN)
        x = screenBounds.clamp(x, area.x(), area.x() + area.width() - self.width())
        y = screenBounds.clamp(y, area.y(), area.y() + area.height() - self.height())
        self.move(x, y)
        self.positioned = True
