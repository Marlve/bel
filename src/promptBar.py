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
#
# Per ADR-0007, split into this view (widget/paint/input),
# promptBarState.py (the mode, no Qt) and promptBarAnimation.py (the
# rejection shake plus the tick-fed flight opacities) - PromptBar keeps its
# previous attribute surface via thin properties so callers outside this
# file don't need to know the split happened.

from PySide6.QtWidgets import QWidget, QLineEdit
from PySide6.QtGui import QPainter, QColor, QPen, QPalette, QPixmap
from PySide6.QtCore import Qt, QRectF, QPoint, QEvent, Signal

import style
import shadow
from promptBarState import PromptBarState, EMPTY, TYPING, SENDING, REJECTED
from promptBarAnimation import PromptBarAnimation

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
        self.bar_state = PromptBarState()
        self.animation = PromptBarAnimation(self)

        # A press on the frame's own chrome - the send hint's inset -
        # would otherwise reach the overlay behind it, which reads any click
        # as "cancel" and would throw away what the user had typed.
        self.setAttribute(Qt.WA_NoMousePropagation)

        self.field = QLineEdit(self)
        self.field.setFrame(False)
        self.field.installEventFilter(self)  # Escape steps back to the ring, it doesn't close everything
        self.field.textChanged.connect(self.onTextChanged)
        self.field.returnPressed.connect(self.submit)
        self.applyFieldPalette()
        self.field.hide()

        shadow.apply(self)
        self.hide()

    # --- thin forwarding to bar_state/animation, for callers outside this file ---

    @property
    def state(self):
        return self.bar_state.state

    @state.setter
    def state(self, value):
        self.bar_state.state = value

    @property
    def rect_opacity(self):
        return self.animation.rect_opacity

    @property
    def chrome_opacity(self):
        return self.animation.chrome_opacity

    @property
    def rest_x(self):
        return self.animation.rest_x

    @property
    def motion(self):
        return self.animation.motion

    @motion.setter
    def motion(self, value):
        self.animation.motion = value

    @property
    def shake(self):
        return self.animation.shake

    def warmup(self):
        """Pay two one-time-per-process Qt/Windows costs now, at silent
        startup, instead of during the user's first handoff.

        setStyleSheet's first call anywhere in the app bootstraps Qt's
        QStyleSheetStyle proxy machinery; SEND_HINT is an uncommon glyph
        (U+23CE) most fonts don't have, so its first draw makes Windows
        search every installed font for a fallback. Both block the main
        thread synchronously - done during launch() instead, either one can
        stall the box's very first appearance for a second or more.
        """
        self.applyFieldPalette()
        pixmap = QPixmap(1, 1)
        painter = QPainter(pixmap)
        painter.drawText(QRectF(0, 0, 1, 1), Qt.AlignCenter, SEND_HINT)
        painter.end()

    # --- the flight, driven by PieMenu's handoff clock ---

    def launch(self, placeholder, seed=""):
        """Reset for a fresh handoff. The field stays hidden until arrive()."""
        self.animation.reset()
        self.bar_state.state = TYPING if seed.strip() else EMPTY
        self.field.setReadOnly(False)
        self.field.setPlaceholderText(placeholder)
        self.field.setText(seed)
        self.applyFieldPalette()
        self.field.hide()
        self.show()

    def setFlight(self, rect_opacity, chrome_opacity):
        self.animation.setFlight(rect_opacity, chrome_opacity)

    def screenRect(self):
        """Where the frame sits in screen coordinates - what the result card
        is born as."""
        origin = self.mapToGlobal(QPoint(0, 0))
        return QRectF(origin.x(), origin.y(), self.width(), self.height())

    def appendSeed(self, text):
        """Keystrokes that landed while the field was still in flight."""
        self.field.setText(self.field.text() + text)

    def place(self):
        """Lay the field out inside the frame now that the frame is at rest.
        Visible but not yet focused - taking focus mid-flight opens the IME
        candidate window against a moving target."""
        if self.field.isVisible():
            return
        self.animation.rest_x = self.x()
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

    def mousePressEvent(self, event):
        if self.field.isVisible():
            self.field.setFocus()

    def onTextChanged(self, text):
        if self.bar_state.state == SENDING:
            return
        self.bar_state.state = TYPING if text.strip() else EMPTY  # also clears a rejection - the user is fixing it
        self.update()

    def submit(self):
        text = self.field.text().strip()
        if not text:
            self.reject()
            return
        self.bar_state.state = SENDING
        self.field.setReadOnly(True)
        self.applyFieldPalette()
        self.update()
        self.submitted.emit(text)

    def reject(self):
        self.bar_state.state = REJECTED  # the border stays warned until the user changes the text
        self.update()
        if self.animation.motion:
            self.animation.shake.run(0.0, 1.0, style.REJECT_MS)

    def eventFilter(self, watched, event):
        if watched is self.field and event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self.cancelled.emit()
            return True
        return super().eventFilter(watched, event)

    # --- painting ---

    def applyFieldPalette(self):
        color = style.FIELD_TEXT_SENDING if self.bar_state.state == SENDING else style.FIELD_TEXT
        self.field.setStyleSheet(style.prompt_field_stylesheet(color))
        palette = self.field.palette()
        palette.setColor(QPalette.PlaceholderText, QColor(style.FIELD_PLACEHOLDER))
        self.field.setPalette(palette)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setOpacity(self.animation.rect_opacity)

        frame = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setBrush(QColor(style.FIELD_SURFACE))
        painter.setPen(QPen(QColor(BORDER_BY_STATE[self.bar_state.state]), 1))
        painter.drawRoundedRect(frame, style.FIELD_RADIUS, style.FIELD_RADIUS)

        if self.animation.chrome_opacity <= 0:
            return
        painter.setOpacity(self.animation.rect_opacity * self.animation.chrome_opacity)

        lit = self.bar_state.state in (TYPING, SENDING)
        painter.setPen(QColor(style.FIELD_HINT_LIT if lit else style.FIELD_HINT_IDLE))
        hint = QRectF(frame.right() - style.FIELD_INSET_RIGHT, frame.top(), style.FIELD_INSET_RIGHT, frame.height())
        painter.drawText(hint, Qt.AlignCenter, SEND_HINT)
