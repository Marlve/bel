# What the chat composer and the prompt bar's field share: Tab completes a
# `!` command, and the rest of it shows dimmed after the caret first.

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPainter, QPalette

from commandComplete import CommandCompleter


class CommandCompletion:
    """Mixin for a text field. The field supplies commandText(), fillCommand(text)
    and caretAtEnd(), sets `self.completer = CommandCompleter()`, and ends its
    paintEvent with paintGhost(surface)."""

    tab_leaves_field = True  # False where Tab has nowhere useful to take the focus

    def focusNextPrevChild(self, forward):
        """Qt turns Tab into a focus move before keyPressEvent sees it, so
        this is where Tab completes a command instead of leaving the field."""
        if forward and not self.isReadOnly():
            completed = self.completer.complete(self.commandText())
            if completed is not None:
                self.fillCommand(completed)
                return True
        return super().focusNextPrevChild(forward) if self.tab_leaves_field else True

    def paintGhost(self, surface):
        """Draws what Tab would add in the field's placeholder color, right after the caret."""
        if self.isReadOnly() or not self.hasFocus() or not self.caretAtEnd():
            return
        ghost = self.completer.ghost(self.commandText())
        if not ghost:
            return
        caret = self.cursorRect()
        painter = QPainter(surface)
        painter.setFont(self.font())
        painter.setPen(self.palette().color(QPalette.PlaceholderText))
        painter.drawText(QRect(caret.right() + 1, caret.top(), surface.width(), caret.height()), Qt.AlignLeft | Qt.AlignVCenter, ghost)
