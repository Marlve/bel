# Shared "fade in near the cursor" open flow for the note and todo cards -
# open()/onFadeTick()/moveNear() were duplicated identically between them
# except each card's own post-show step (NoteCard's scrollbar-flash flush,
# TodoCard's add-field focus). Those stay in each subclass via the
# afterShow()/afterRaise() hooks below, at the same point in the sequence
# they occupied before this split. First shared base class among this
# codebase's cards (ticket 09).

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QCursor

import style
from anims import curves


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
        screen = QApplication.screenAt(cursor_pos) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        x = cursor_pos.x() + style.CARD_SPAWN_OFFSET - style.CARD_SHADOW_MARGIN
        y = cursor_pos.y() + style.CARD_SPAWN_OFFSET - style.CARD_SHADOW_MARGIN
        x = max(area.x(), min(x, area.x() + area.width() - self.width()))
        y = max(area.y(), min(y, area.y() + area.height() - self.height()))
        self.move(x, y)
