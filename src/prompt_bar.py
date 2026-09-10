# The text field a wedge hands off to when its action needs typed input.
#
# design.md: the wedge does not morph into a text box - Qt has no meaningful
# interpolation between an annular sector and a pill - so a rounded rect
# grows out of the wedge's bounding box instead, and the real QLineEdit is
# placed inside it only once that rect has stopped moving. Animating a
# widget that holds text reflows and re-hints its glyphs every frame.
#
# This lives as a child of the pie overlay rather than as its own top-level
# window: the overlay has already fought Windows for keyboard focus (see
# util.force_foreground), and a second window would have to fight again.
# PieMenu drives the flight - this class only knows how to look right at a
# given point in it.

import math

from PySide6.QtWidgets import QWidget, QLineEdit
from PySide6.QtGui import QPainter, QColor, QPen, QPalette
from PySide6.QtCore import Qt, QRectF, QPointF, QEvent, Signal, QVariantAnimation

import style

EMPTY, TYPING, SENDING, REJECTED = "empty", "typing", "sending", "rejected"

BORDER_BY_STATE = {
    EMPTY: style.FIELD_BORDER,
    TYPING: style.FIELD_BORDER_TYPING,
    SENDING: style.FIELD_BORDER_SENDING,
    REJECTED: style.FIELD_BORDER_REJECTED,
}
SEND_HINT = "⏎"  # the return glyph, sitting in the right inset


class PromptBar(QWidget):
    submitted = Signal(str)
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rect_opacity = 0.0  # the frame fades in as the wedge fades out
        self.chrome_opacity = 0.0  # mark and hint follow, once the frame is at rest
        self.state = EMPTY
        self.rest_x = 0

        self.field = QLineEdit(self)
        self.field.setFrame(False)
        self.field.installEventFilter(self)  # Escape steps back to the ring, it doesn't close everything
        self.field.textChanged.connect(self.onTextChanged)
        self.field.returnPressed.connect(self.submit)
        self.applyFieldPalette()
        self.field.hide()

        # Rejected: the frame shakes in place, keeping whatever was typed.
        self.shake = QVariantAnimation(self)
        self.shake.setStartValue(0.0)
        self.shake.setEndValue(1.0)
        self.shake.setDuration(style.REJECT_MS)
        self.shake.valueChanged.connect(self.onShakeTick)
        self.shake.finished.connect(self.onShakeDone)

        self.hide()

    # --- the flight, driven by PieMenu's handoff clock ---

    def launch(self, placeholder, seed=""):
        """Reset for a fresh handoff. The field stays hidden until arrive()."""
        self.shake.stop()
        self.state = TYPING if seed.strip() else EMPTY
        self.rect_opacity = 0.0
        self.chrome_opacity = 0.0
        self.field.setReadOnly(False)
        self.field.setPlaceholderText(placeholder)
        self.field.setText(seed)
        self.applyFieldPalette()
        self.field.hide()
        self.show()

    def setFlight(self, rect_opacity, chrome_opacity):
        self.rect_opacity = rect_opacity
        self.chrome_opacity = chrome_opacity
        self.update()

    def appendSeed(self, text):
        """Keystrokes that landed while the field was still in flight."""
        self.field.setText(self.field.text() + text)

    def place(self):
        """Lay the field out inside the frame now that the frame is at rest.
        Visible but not yet focused - taking focus mid-flight opens the IME
        candidate window against a moving target."""
        if self.field.isVisible():
            return
        self.rest_x = self.x()
        self.field.setGeometry(
            style.FIELD_INSET_LEFT,
            0,
            max(self.width() - style.FIELD_INSET_LEFT - style.FIELD_INSET_RIGHT, 0),
            self.height(),
        )
        self.field.show()

    def takeFocus(self):
        self.field.setFocus()
        self.field.end(False)  # caret after any text the ring seeded

    # --- state ---

    def onTextChanged(self, text):
        if self.state in (SENDING, REJECTED):
            return
        self.state = TYPING if text.strip() else EMPTY
        self.update()

    def submit(self):
        text = self.field.text().strip()
        if not text:
            self.reject()
            return
        self.state = SENDING
        self.field.setReadOnly(True)
        self.applyFieldPalette()
        self.update()
        self.submitted.emit(text)

    def reject(self):
        self.state = REJECTED
        self.update()
        self.shake.start()

    def onShakeTick(self, t):
        offset = math.sin(t * 2 * math.pi * style.REJECT_SHAKES) * style.REJECT_SHIFT
        self.move(round(self.rest_x + offset), self.y())

    def onShakeDone(self):
        self.move(self.rest_x, self.y())
        self.state = TYPING if self.field.text().strip() else EMPTY
        self.update()

    def eventFilter(self, watched, event):
        if watched is self.field and event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self.cancelled.emit()
            return True
        return super().eventFilter(watched, event)

    # --- painting ---

    def applyFieldPalette(self):
        color = style.FIELD_TEXT_SENDING if self.state == SENDING else style.FIELD_TEXT
        self.field.setStyleSheet(style.prompt_field_stylesheet(color))
        palette = self.field.palette()
        palette.setColor(QPalette.PlaceholderText, QColor(style.FIELD_PLACEHOLDER))
        self.field.setPalette(palette)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setOpacity(self.rect_opacity)

        frame = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = min(frame.width(), frame.height()) / 2  # fully round at both ends of the grow
        painter.setBrush(QColor(style.FIELD_SURFACE))
        painter.setPen(QPen(QColor(BORDER_BY_STATE[self.state]), 1))
        painter.drawRoundedRect(frame, radius, radius)

        if self.chrome_opacity <= 0:
            return
        painter.setOpacity(self.rect_opacity * self.chrome_opacity)

        mark = QRectF(0, 0, style.FIELD_MARK, style.FIELD_MARK)
        mark.moveCenter(QPointF(style.FIELD_MARK_INSET + style.FIELD_MARK / 2, frame.center().y()))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(style.ACCENT), 2))
        painter.drawRoundedRect(mark, 7, 7)

        lit = self.state in (TYPING, SENDING)
        painter.setPen(QColor(style.FIELD_HINT_LIT if lit else style.FIELD_HINT_IDLE))
        hint = QRectF(frame.right() - style.FIELD_INSET_RIGHT, frame.top(), style.FIELD_INSET_RIGHT, frame.height())
        painter.drawText(hint, Qt.AlignCenter, SEND_HINT)
