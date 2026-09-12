# Shared "fade in near the cursor" open flow for the note and todo cards -
# open()/onFadeTick()/moveNear() were duplicated identically between them
# except each card's own post-show step (NoteCard's scrollbar-flash flush,
# TodoCard's add-field focus). Those stay in each subclass via the
# afterShow()/afterRaise() hooks below, at the same point in the sequence
# they occupied before this split. First shared base class among this
# codebase's cards (ticket 09).

from PySide6.QtGui import QCursor, QColor, QPainterPath, QPen
from PySide6.QtCore import QRectF, QPointF

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


class FloatingCard:
    def open(self):
        """Lands near wherever the wedge was picked - like the ring itself
        always opening at the cursor, not wherever the card happened to be
        left after a previous drag or a previous session."""
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
        area = screenBounds.available_area(cursor_pos)
        x = cursor_pos.x() + style.CARD_SPAWN_OFFSET - style.CARD_SHADOW_MARGIN
        y = cursor_pos.y() + style.CARD_SPAWN_OFFSET - style.CARD_SHADOW_MARGIN
        x = screenBounds.clamp(x, area.x(), area.x() + area.width() - self.width())
        y = screenBounds.clamp(y, area.y(), area.y() + area.height() - self.height())
        self.move(x, y)
