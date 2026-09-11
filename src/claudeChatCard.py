# Where a prompt's answer lands, per claude-chat-flow.md: a square born as
# the prompt bar's exact rectangle, that flies to the top-right corner and
# becomes a real chat - transcript plus composer, not a one-shot answer.
# Docked, it stays fully open until explicitly minimized (see
# claudeEdgeDockState.py / claudeEdgeDockAnimation.py / claudeEdgeTrigger.py)
# - no automatic retreat - and a TAB peek lets it be reopened once hidden.
#
# design.md / claude-chat-flow.md: the card must NOT be a child of the
# overlay - the ring closes as soon as the prompt is sent, so the card is
# its own top-level window, and ChatSlot is what keeps it alive afterwards.

import html
import math

from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QPlainTextEdit, QScrollArea,
    QVBoxLayout, QHBoxLayout, QLayout, QApplication,
)
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QTransform
from PySide6.QtCore import Qt, QRectF, QTimer, QVariantAnimation, QPointF, Signal

import style
import wedgeConfig
from anims import curves, pose
from anims.clock import Clock, Tween
from claudeEdgeDockState import OPEN, HIDDEN, TAB
from claudeEdgeDockAnimation import EdgeDockDriver
from claudeEdgeTrigger import EdgeTrigger
from util import reduced_motion

def _tabFootprint():
    """The window footprint TAB needs to show the puck rotated without
    clipping it. claude-chat-flow.md hinges the tilt on the puck's own right
    edge, not its centre, so the swept bounding box is asymmetric - a plain
    size*(|cos|+|sin|) square (correct only for a centre-pivot rotation) and
    a symmetric inset clips the far corner (the bottom edge, at -9deg)."""
    size = style.DOCK_COMPACT_SIZE
    pivot = QPointF(size, size / 2)  # right-edge midpoint, puck's own top-left as local origin
    transform = QTransform().translate(pivot.x(), pivot.y()).rotate(style.DOCK_TAB_ROTATION_DEG).translate(
        -pivot.x(), -pivot.y()
    )
    swept = transform.mapRect(QRectF(0, 0, size, size))
    return math.ceil(swept.width()), math.ceil(swept.height()), math.ceil(-swept.left()), math.ceil(-swept.top())


TAB_WIDTH, TAB_HEIGHT, TAB_LEFT_INSET, TAB_TOP_INSET = _tabFootprint()


class Composer(QPlainTextEdit):
    """Present from the moment the card lands - no mode switch between
    reading and asking. Enter sends, Shift+Enter newlines, Escape blurs the
    field rather than closing the card."""

    submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(style.CHAT_COMPOSER_HEIGHT)
        self.setPlaceholderText("Ask a follow-up…")
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTabChangesFocus(True)
        self.setFrameShape(QPlainTextEdit.NoFrame)
        self.textChanged.connect(self.onTextChanged)
        self.onTextChanged()

    def onTextChanged(self):
        warm = bool(self.toPlainText().strip())
        self.setStyleSheet(style.chat_composer_stylesheet(warm))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.clearFocus()
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            text = self.toPlainText().strip()
            if text:
                self.submitted.emit(text)
                self.clear()
            return
        super().keyPressEvent(event)


class ChatCard(QWidget):
    dismissed = Signal(object)

    def __init__(self, born, dock_rect, screen):
        super().__init__(None)  # top-level: it outlives the overlay it came from
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)  # never yank focus off whatever the user is doing

        self.born = born
        self.dock_rect = dock_rect  # this card's OPEN geometry, fixed for the card's life
        self.screen = screen
        self.radius = min(born.width(), born.height()) / 2
        self.tilt = 0.0  # degrees, animated separately from the dock slide (claude-chat-flow.md's "260 ms rotation")
        self.wedge_id = None
        self.action = None
        self.session_id = None
        self.turn_count = 0  # messages sent in the current session; capped, see send()
        self.request = None
        self.buffered = ""
        self.turns = []  # {"role": "user"/"claude", "text": ...}, one per transcript row
        self.streaming_label = None
        self.streaming_text = ""
        self.streaming_index = None
        self.auto_scroll = True
        self.motion = not reduced_motion()

        self.buildContent()
        self.setContent(False)

        self.flight = Clock(self, self.onFlightTick, self.onLanded)
        self.fade = Tween(self, self.onFadeTick, self.onFaded)
        self.tilt_tween = Tween(self, self.onTiltTick)

        self.edge_driver = None
        self.edge_trigger = None

    def buildContent(self):
        self.header_label = QLabel("CLAUDE", self)
        header_font = QFont(style.CHAT_MONO_FAMILY)
        header_font.setPointSizeF(style.CHAT_HEADER_SIZE)
        header_font.setLetterSpacing(QFont.PercentageSpacing, style.CHAT_HEADER_TRACKING_PERCENT)
        self.header_label.setFont(header_font)
        self.header_label.setStyleSheet(f"color: {style.CHAT_LABEL_MONO}; background: transparent;")

        self.minimize_button = QPushButton("−", self)
        self.minimize_button.setFixedSize(18, 18)
        self.minimize_button.setCursor(Qt.PointingHandCursor)
        self.minimize_button.setStyleSheet(style.chat_close_stylesheet())
        self.minimize_button.clicked.connect(self.minimize)

        self.close_button = QPushButton("✕", self)
        self.close_button.setFixedSize(18, 18)
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setStyleSheet(style.chat_close_stylesheet())
        self.close_button.clicked.connect(self.dismiss)

        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(self.header_label)
        header.addStretch(1)
        header.addWidget(self.minimize_button)
        header.addWidget(self.close_button)

        self.transcript = QWidget()
        self.transcript_layout = QVBoxLayout(self.transcript)
        self.transcript_layout.setSpacing(8)
        self.transcript_layout.addStretch(1)  # keeps a short transcript bottom-anchored

        self.scroll = QScrollArea(self)
        self.scroll.setWidget(self.transcript)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setStyleSheet(style.chat_scrollbar_stylesheet())
        self.scroll.verticalScrollBar().valueChanged.connect(self.onScrollValueChanged)
        self.scroll.verticalScrollBar().rangeChanged.connect(self.onScrollRangeChanged)

        self.composer = Composer(self)
        self.composer.submitted.connect(self.send)

        root = QVBoxLayout(self)
        # This card's size is managed entirely by the dock state machine
        # (HIDDEN 64x64, TAB's puck, OPEN 340x340), not by Qt - left
        # at Qt's default, activating the layout floors the widget's
        # minimumSize at whatever's visible *at that moment*, and it never
        # shrinks back down again even once content is hidden for a smaller
        # state, silently clamping every setGeometry() call back up to it.
        root.setSizeConstraint(QLayout.SetNoConstraint)
        root.setContentsMargins(*[style.CHAT_PADDING] * 4)
        root.setSpacing(10)
        root.addLayout(header)
        root.addWidget(self.scroll, 1)
        root.addWidget(self.composer)

    def setContent(self, visible):
        for widget in (self.header_label, self.minimize_button, self.close_button, self.scroll, self.composer):
            widget.setVisible(visible)

    def setCompactVisual(self, compact):
        """TAB and HIDDEN show the bare frame only."""
        for widget in (self.header_label, self.minimize_button, self.close_button, self.scroll, self.composer):
            widget.setVisible(not compact)

    # --- the flight from the prompt bar ---

    def flying(self):
        return self.flight.state() == QVariantAnimation.Running

    def fly(self):
        self.setGeometry(self.born.toRect())
        self.show()
        self.raise_()
        if not self.motion:
            self.onLanded()
            return
        self.flight.run(style.CHAT_FLIGHT_MS)

    def onFlightTick(self, ms):
        self.setGeometry(pose.lerp_rect(self.born, self.dock_rect, pose.card_flight_progress(ms)).toRect())
        self.radius = pose.card_radius(ms, min(self.born.width(), self.born.height()) / 2)
        self.update()

    def onLanded(self):
        self.setGeometry(self.dock_rect.toRect())
        self.radius = style.CHAT_RADIUS
        self.setContent(True)
        self.layout().activate()

        self.edge_driver = EdgeDockDriver(
            self, self.geometryFor, self.onDockMoved, self.onDockStateChanged, self.motion,
            on_landed=self.onDockLanded,
        )
        self.edge_trigger = EdgeTrigger(self.onEdgeDistance, self.screen)

        if self.buffered:
            self.write(self.buffered)
            self.buffered = ""
        self.update()

    # --- the conversation ---

    def send(self, text):
        if self.request is not None or self.action is None:
            return
        if self.turn_count >= wedgeConfig.load_chat_context_limit():
            # The session has taken as much context as it's allowed to -
            # this message starts a brand new one rather than resuming.
            self.session_id = None
            self.turn_count = 0
        self.turn_count += 1
        self.appendUserTurn(text)
        self.streaming_label = self.appendClaudeTurn()
        self.streaming_text = ""
        self.composer.setReadOnly(True)

        self.request = self.action(text, session_id=self.session_id)
        self.request.chunk.connect(self.onChunk)
        self.request.session_started.connect(self.onSessionStarted)
        self.request.finished.connect(self.onStreamFinished)

    def onSessionStarted(self, session_id):
        self.session_id = session_id

    def onChunk(self, text):
        # Content only streams once the geometry is at rest - text reflowing
        # inside a widget that is still resizing re-hints every glyph.
        if self.flying():
            self.buffered += text
        else:
            self.write(text)

    def write(self, text):
        self.streaming_text += text
        self.turns[self.streaming_index]["text"] = self.streaming_text
        self.setTurnHtml(self.streaming_label, self.streaming_text, caret=True)
        QTimer.singleShot(0, self.scrollToBottomIfNeeded)

    def onStreamFinished(self):
        if self.streaming_label is not None:
            self.setTurnHtml(self.streaming_label, self.streaming_text, caret=False)
        self.streaming_label = None
        self.composer.setReadOnly(False)
        self.unwire()

    def unwire(self):
        if self.request is None:
            return
        self.request.chunk.disconnect(self.onChunk)
        self.request.session_started.disconnect(self.onSessionStarted)
        self.request.finished.disconnect(self.onStreamFinished)
        self.request = None

    # --- transcript ---

    def appendUserTurn(self, text):
        self.turns.append({"role": "user", "text": text})

        bubble = QLabel(html.escape(text))
        bubble.setWordWrap(True)
        bubble.setStyleSheet(style.chat_bubble_stylesheet())
        bubble.setMaximumWidth(self.bubbleMaxWidth())

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(bubble)
        self.insertTurnRow(row)

    def appendClaudeTurn(self):
        self.turns.append({"role": "claude", "text": ""})
        self.streaming_index = len(self.turns) - 1

        label = QLabel("")
        label.setTextFormat(Qt.RichText)
        label.setWordWrap(True)
        label.setStyleSheet(style.chat_turn_stylesheet())
        label.setMaximumWidth(self.contentWidth())

        row = QHBoxLayout()
        row.addWidget(label)
        row.addStretch(1)
        self.insertTurnRow(row)
        return label

    def insertTurnRow(self, row):
        # Before the trailing stretch, so the stretch keeps doing its job of
        # bottom-anchoring a transcript shorter than the frame.
        self.transcript_layout.insertLayout(self.transcript_layout.count() - 1, row)

    def setTurnHtml(self, label, text, caret):
        body = html.escape(text)
        if caret:
            body += f'<span style="color:{style.CHAT_ACCENT};">▏</span>'
        label.setText(body)

    def bubbleMaxWidth(self):
        return round(self.contentWidth() * style.CHAT_BUBBLE_MAX_WIDTH_FRACTION)

    def contentWidth(self):
        return style.CHAT_SIZE - 2 * style.CHAT_PADDING - self.scroll.verticalScrollBar().sizeHint().width()

    def onScrollValueChanged(self, value):
        bar = self.scroll.verticalScrollBar()
        self.auto_scroll = value >= bar.maximum() - 2

    def onScrollRangeChanged(self, minimum, maximum):
        if self.auto_scroll:
            self.scroll.verticalScrollBar().setValue(maximum)

    def scrollToBottomIfNeeded(self):
        if self.auto_scroll:
            bar = self.scroll.verticalScrollBar()
            bar.setValue(bar.maximum())

    # --- the edge dock ---

    def geometryFor(self, state):
        r = self.dock_rect
        area = self.screen.availableGeometry()
        edge = area.x() + area.width()
        size = style.DOCK_COMPACT_SIZE
        if state == OPEN:
            return QRectF(r)
        if state == HIDDEN:
            return QRectF(edge, r.top(), size, size)
        return QRectF(
            edge - style.DOCK_TAB_VISIBLE_PX - TAB_LEFT_INSET,
            r.top() - TAB_TOP_INSET,
            TAB_WIDTH,
            TAB_HEIGHT,
        )

    def onDockMoved(self, rect):
        self.setGeometry(rect.toRect())

    def onDockStateChanged(self, dock_state):
        # Reaching OPEN is the one transition where content becomes visible
        # rather than hidden - deferred to onDockLanded() so the labels don't
        # reflow every frame while the window is still growing from a
        # HIDDEN/TAB-sized footprint up to full size (same reasoning as
        # onChunk() buffering text until the flight animation is done).
        if dock_state != OPEN or not self.motion:
            self.setCompactVisual(dock_state in (TAB, HIDDEN))
        self.radius = style.CHAT_RADIUS
        target_tilt = style.DOCK_TAB_ROTATION_DEG if dock_state == TAB else 0.0
        if self.motion:
            self.tilt_tween.run(self.tilt, target_tilt, style.DOCK_TAB_ROTATE_MS, curves.CHAT_FLIGHT)
        else:
            self.tilt = target_tilt
        self.update()

    def onDockLanded(self):
        if self.edge_driver and self.edge_driver.dock.state == OPEN:
            self.setCompactVisual(False)

    def onTiltTick(self, value):
        self.tilt = value
        self.update()

    def onEdgeDistance(self, px):
        if self.edge_driver:
            self.edge_driver.cursorDistance(px)

    def minimize(self):
        if self.edge_driver:
            self.edge_driver.minimize()

    def reveal(self):
        """Picking this card's wedge again while its session is still alive
        just brings it back into view - no new session, no new message."""
        self.raise_()
        if self.edge_driver:
            self.edge_driver.reveal()

    def puckRect(self):
        """The puck's own rect within this widget. Scales the TAB insets by
        how far the geometry tween has grown from HIDDEN's bare size*size
        window towards TAB's full (asymmetric) footprint, so the
        puck tracks smoothly mid-transition instead of jumping to its final
        offset the instant TAB is reached."""
        size = style.DOCK_COMPACT_SIZE
        span = TAB_WIDTH - size
        t = max(0.0, min(1.0, (self.width() - size) / span)) if span else 1.0
        return QRectF(TAB_LEFT_INSET * t, TAB_TOP_INSET * t, size, size)

    def tabPivot(self):
        """claude-chat-flow.md: TAB is 'hinged on its right edge' - the pivot
        is the puck's own right-edge midpoint, not the window centre."""
        puck = self.puckRect()
        return QPointF(puck.right(), puck.center().y())

    def isTabbed(self):
        return self.edge_driver is not None and self.edge_driver.dock.state == TAB

    def tabContains(self, pos):
        pivot = self.tabPivot()
        inverse, ok = QTransform().translate(pivot.x(), pivot.y()).rotate(-style.DOCK_TAB_ROTATION_DEG).translate(
            -pivot.x(), -pivot.y()
        ).inverted()
        local = inverse.map(pos) if ok else pos
        return self.puckRect().contains(local)

    # --- leaving ---

    def dismiss(self):
        if self.fade.state() == QVariantAnimation.Running:
            return
        self.unwire()
        if self.edge_trigger:
            self.edge_trigger.stop()
        if not self.motion:
            self.onFaded()
            return
        self.fade.run(1.0, 0.0, style.CHAT_DISMISS_MS, curves.CHAT_FLIGHT)

    def onFadeTick(self, t):
        self.setWindowOpacity(t)
        travelled = round((1 - t) * style.CHAT_DISMISS_SLIDE)
        self.move(self.dock_rect.toRect().x() + travelled, self.dock_rect.toRect().y())

    def onFaded(self):
        # Only hide and announce. Tearing the widget down here would destroy
        # the very animation that is still emitting into this slot - the
        # stack holds the card until the event loop has unwound.
        self.hide()
        self.dismissed.emit(self)

    def mousePressEvent(self, event):
        if self.isTabbed():
            if self.tabContains(event.position()) and self.edge_driver:
                self.edge_driver.clickTab()
            return

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.dismiss()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        dock_state = self.edge_driver.dock.state if self.edge_driver else None
        if self.isTabbed() or (self.tilt != 0.0 and dock_state != OPEN):
            # Rotation is gated on self.tilt, not just isTabbed(), so the
            # untilt-back-to-0 animation stays visible after the state has
            # already left TAB - otherwise painting would drop to the
            # unrotated branch the instant TAB ends, and the still-running
            # tilt_tween would keep updating self.tilt with nothing drawing
            # it, making the tilt appear to vanish instantly. Excluded for
            # OPEN specifically: reopening grows the window to full size
            # while puckRect() stays clamped to its tiny footprint, so
            # keeping this branch there would paint a stuck puck instead of
            # the growing card until the tilt tween finished.
            painter.save()
            pivot = self.tabPivot()
            painter.translate(pivot)
            painter.rotate(self.tilt)
            painter.translate(-pivot.x(), -pivot.y())
            self.paintFrame(painter, self.puckRect())
            painter.restore()
            return

        self.paintFrame(painter, QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5))

    def paintFrame(self, painter, frame):
        border = style.CHAT_BORDER_TAB if self.isTabbed() else style.CHAT_BORDER
        painter.setBrush(QColor(style.CHAT_SURFACE))
        painter.setPen(QPen(QColor(border), 1))
        painter.drawRoundedRect(frame, self.radius, self.radius)


class ChatSlot:
    """Holds the one open chat card, if any - only one wedge can ever be
    assigned Claude at a time (settingsCard.py's collision swap), so there
    is never more than one live session to keep track of."""

    def __init__(self):
        self.card = None
        self.closing = []  # torn down on the next event loop turn, not mid-signal

    def dockRect(self, screen):
        area = screen.availableGeometry()  # work area, not monitor bounds
        return QRectF(
            area.x() + area.width() - style.CHAT_MARGIN - style.CHAT_SIZE,
            area.y() + style.CHAT_MARGIN,
            style.CHAT_SIZE,
            style.CHAT_SIZE,
        )

    def reveal(self, wedge_id):
        """If a card for this wedge is already open, bring it back into view
        instead of starting another one - the session only resets once that
        card is actually closed (see ChatCard.dismiss/forget below)."""
        if self.card is None or self.card.wedge_id != wedge_id:
            return False
        self.card.reveal()
        return True

    def open(self, born, prompt, wedge_id, action):
        if self.reveal(wedge_id):
            return self.card  # e.g. a prompt-jump shortcut raced past activateHoveredWedge()'s own check

        # The prompt bar was at the cursor, so its rect picks the monitor.
        screen = QApplication.screenAt(born.center().toPoint()) or QApplication.primaryScreen()
        if self.card is not None:
            self.forget(self.card)

        card = ChatCard(born, self.dockRect(screen), screen)
        card.wedge_id = wedge_id
        card.action = action
        card.dismissed.connect(self.forget)
        self.card = card

        card.fly()  # before the request starts, so early chunks buffer instead of landing early
        card.send(prompt)
        return card

    def forget(self, card):
        if self.card is card:
            self.card = None
        self.retire(card)

    def retire(self, card):
        """Take a card out of service. It stays referenced until the next
        event loop turn: this can be reached from inside the card's own fade
        animation, and dropping the last reference to the card there would
        destroy that animation mid-emit."""
        card.unwire()
        if card.edge_trigger:
            card.edge_trigger.stop()
        card.hide()
        self.closing.append(card)
        QTimer.singleShot(0, self.dropRetired)

    def dropRetired(self):
        for card in self.closing:
            card.close()
            card.deleteLater()
        self.closing.clear()
