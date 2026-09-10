# Where a prompt's answer lands: a square that is born as the prompt bar's
# exact rectangle, flies to the top-right corner of the work area and streams
# the response in once it has stopped moving.
#
# design.md: the card must NOT be a child of the overlay. The overlay closes
# as soon as the prompt is sent - the scrim clears while the card is still in
# the air - so the card is its own top-level window, and CardStack is what
# keeps it alive afterwards.

from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QTextBrowser, QVBoxLayout, QHBoxLayout, QApplication
from PySide6.QtGui import QPainter, QColor, QPen, QTextCursor
from PySide6.QtCore import Qt, QRectF, QTimer, QVariantAnimation, Signal

import style
import pie_anim
from util import reduced_motion


class ResultCard(QWidget):
    dismissed = Signal(object)

    def __init__(self, prompt, born, dock):
        super().__init__(None)  # top-level: it outlives the overlay it came from
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)  # never yank focus off whatever the user is doing

        self.prompt = prompt
        self.born = born
        self.dock = dock
        self.radius = min(born.width(), born.height()) / 2
        self.request = None
        self.buffered = ""  # chunks that arrive mid-flight wait their turn
        self.motion = not reduced_motion()

        self.buildContent()
        self.setContent(False)

        self.flight = QVariantAnimation(self)
        self.flight.setStartValue(0)
        self.flight.valueChanged.connect(self.onFlightTick)
        self.flight.finished.connect(self.onLanded)

        self.slide = QVariantAnimation(self)
        self.slide.valueChanged.connect(self.onSlideTick)

        self.fade = QVariantAnimation(self)
        self.fade.setStartValue(1.0)
        self.fade.setEndValue(0.0)
        self.fade.setDuration(style.CARD_DISMISS_MS)
        self.fade.setEasingCurve(pie_anim.CARD_FLIGHT)
        self.fade.valueChanged.connect(self.onFadeTick)
        self.fade.finished.connect(self.onFaded)

    def buildContent(self):
        self.mark = QLabel(self)
        self.mark.setFixedSize(style.CARD_MARK, style.CARD_MARK)
        self.mark.setStyleSheet(f"border: 2px solid {style.ACCENT}; border-radius: 4px;")

        self.echo = QLabel(self)
        self.echo.setStyleSheet(style.card_echo_stylesheet())

        self.close_button = QPushButton("✕", self)
        self.close_button.setFixedSize(18, 18)
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setStyleSheet(style.card_close_stylesheet())
        self.close_button.clicked.connect(self.dismiss)

        self.body = QTextBrowser(self)
        self.body.setReadOnly(True)
        self.body.setFrameShape(QTextBrowser.NoFrame)
        self.body.setStyleSheet(style.card_body_stylesheet())

        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(self.mark)
        header.addWidget(self.echo, 1)
        header.addWidget(self.close_button)

        root = QVBoxLayout(self)
        root.setContentsMargins(*[style.CARD_PADDING] * 4)
        root.setSpacing(10)
        root.addLayout(header)
        root.addWidget(self.body, 1)

    def setContent(self, visible):
        for widget in (self.mark, self.echo, self.close_button, self.body):
            widget.setVisible(visible)

    # --- the flight ---

    def flying(self):
        return self.flight.state() == QVariantAnimation.Running

    def fly(self):
        self.setGeometry(self.born.toRect())
        self.show()
        self.raise_()
        if not self.motion:
            self.onLanded()  # straight to the corner, and don't withhold the answer
            return
        self.flight.setEndValue(style.CARD_FLIGHT_MS)
        self.flight.setDuration(style.CARD_FLIGHT_MS)
        self.flight.start()

    def onFlightTick(self, ms):
        self.setGeometry(pie_anim.lerp_rect(self.born, self.dock, pie_anim.card_flight_progress(ms)).toRect())
        self.radius = pie_anim.card_radius(ms, min(self.born.width(), self.born.height()) / 2)
        self.update()

    def onLanded(self):
        self.setGeometry(self.dock.toRect())
        self.radius = style.CARD_RADIUS
        self.setContent(True)
        self.layout().activate()
        self.echo.setText(self.echo.fontMetrics().elidedText(self.prompt, Qt.ElideRight, max(self.echo.width(), 1)))
        if self.buffered:
            self.write(self.buffered)
            self.buffered = ""
        self.update()

    def slideTo(self, dock):
        """Move out of a newer card's way."""
        self.dock = dock
        if not self.isVisible() or self.flying():
            return  # still flying - onFlightTick already aims at the new dock
        if not self.motion:
            self.setGeometry(dock.toRect())
            return
        self.slide.stop()
        self.slide.setStartValue(QRectF(self.geometry()))
        self.slide.setEndValue(dock)
        self.slide.setDuration(style.CARD_RESTACK_MS)
        self.slide.setEasingCurve(pie_anim.CARD_FLIGHT)
        self.slide.start()

    def onSlideTick(self, rect):
        self.setGeometry(rect.toRect())

    # --- streaming ---

    def stream(self, action, prompt):
        """Ask, and follow the answer. The signals belong to this one
        request, so another prompt's output can never land in this card."""
        self.request = action(prompt)
        self.request.chunk.connect(self.onChunk)
        self.request.finished.connect(self.onStreamFinished)

    def onChunk(self, text):
        # Content only streams once the geometry is at rest - text reflowing
        # inside a widget that is still resizing re-hints every glyph.
        if self.flying():
            self.buffered += text
        else:
            self.write(text)

    def write(self, text):
        cursor = self.body.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.body.setTextCursor(cursor)  # keeps the newest line in view

    def onStreamFinished(self):
        self.unwire()

    def unwire(self):
        if self.request is None:
            return
        self.request.chunk.disconnect(self.onChunk)
        self.request.finished.disconnect(self.onStreamFinished)
        self.request = None

    # --- leaving ---

    def dismiss(self):
        if self.fade.state() == QVariantAnimation.Running:
            return
        self.unwire()
        if not self.motion:
            self.onFaded()
            return
        self.fade.start()

    def onFadeTick(self, t):
        self.setWindowOpacity(t)
        travelled = round((1 - t) * style.CARD_DISMISS_SLIDE)
        self.move(self.dock.toRect().x() + travelled, self.dock.toRect().y())

    def onFaded(self):
        # Only hide and announce. Tearing the widget down here would destroy
        # the very animation that is still emitting into this slot - the
        # stack holds the card until the event loop has unwound.
        self.hide()
        self.dismissed.emit(self)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.dismiss()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        frame = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setBrush(QColor(style.CARD_SURFACE))
        painter.setPen(QPen(QColor(style.CARD_BORDER), 1))
        painter.drawRoundedRect(frame, self.radius, self.radius)


class CardStack:
    """The open result cards, newest in the corner and older ones pushed
    down below it."""

    def __init__(self):
        self.cards = []
        self.closing = []  # torn down on the next event loop turn, not mid-signal

    def dockRect(self, slot, screen):
        area = screen.availableGeometry()  # work area, not monitor bounds
        return QRectF(
            area.x() + area.width() - style.CARD_MARGIN - style.CARD_SIZE,
            area.y() + style.CARD_MARGIN + slot * (style.CARD_SIZE + style.CARD_GAP),
            style.CARD_SIZE,
            style.CARD_SIZE,
        )

    def open(self, born, prompt, action):
        # The prompt bar was at the cursor, so its rect picks the monitor.
        screen = QApplication.screenAt(born.center().toPoint()) or QApplication.primaryScreen()

        card = ResultCard(prompt, born, self.dockRect(0, screen))
        card.dismissed.connect(self.forget)
        self.cards.insert(0, card)
        while len(self.cards) > style.CARD_MAX:
            self.retire(self.cards.pop())  # evict before re-docking, so nothing slides to a slot it loses
        for slot, older in enumerate(self.cards[1:], start=1):
            older.slideTo(self.dockRect(slot, screen))

        card.fly()  # before the request starts, so early chunks buffer instead of landing early
        card.stream(action, prompt)
        return card

    def forget(self, card):
        if card in self.cards:
            self.cards.remove(card)
        self.retire(card)
        screen = QApplication.screenAt(card.dock.center().toPoint()) or QApplication.primaryScreen()
        for slot, remaining in enumerate(self.cards):
            remaining.slideTo(self.dockRect(slot, screen))

    def retire(self, card):
        """Take a card out of service. It stays referenced until the next
        event loop turn: this can be reached from inside the card's own fade
        animation, and dropping the last reference to the card there would
        destroy that animation mid-emit."""
        card.unwire()
        card.hide()
        self.closing.append(card)
        QTimer.singleShot(0, self.dropRetired)

    def dropRetired(self):
        for card in self.closing:
            card.close()
            card.deleteLater()
        self.closing.clear()
