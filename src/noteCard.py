# Sticky note (wedge 1), per design.md's "Sticky note" section - simplified
# to a single toggled instance (like the todo card) rather than design.md's
# modifier-key multi-note spawning, and onto the app's shared neutral palette
# instead of the design doc's own amber.
#
# Drag zone is the header and margins only, per design.md - "dragging cannot
# fight text selection." The body is a real QPlainTextEdit child, so a press
# inside it never reaches the card's own drag handling at all; only the
# chrome around it (marked transparent-for-mouse, see buildContent) and the
# bare margins - not covered by any child widget - fall through to it.

from PySide6.QtWidgets import QWidget, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QHBoxLayout, QApplication
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtCore import Qt, QRectF, QTimer, QEvent

import style
import shadow
import cardStore
from anims.clock import Tween
from draggable import WindowDrag, ResizeGrip
from floatingCard import FloatingCard, paint_card_bands
from util import reduced_motion

STORE_KEY = "note"


def margin():
    return style.CARD_SHADOW_MARGIN  # extra window room around the visible face, for the shadow


class NoteCard(FloatingCard, QWidget):
    def __init__(self):
        super().__init__(None)  # top-level: outlives the ring, persists for the app's life
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(style.CARD_MIN_WIDTH + 2 * margin(), style.CARD_MIN_HEIGHT + 2 * margin())

        self.drag = WindowDrag(self)
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save)
        self.motion = not reduced_motion()
        self.fade = Tween(self, self.onFadeTick)
        shadow.apply(self)

        saved = cardStore.load(STORE_KEY, {})
        face_w, face_h = saved.get("size", [style.NOTE_DEFAULT_WIDTH, style.CHAT_SIZE])
        self.resize(face_w + 2 * margin(), face_h + 2 * margin())
        pos = saved.get("pos")
        if pos is not None:
            self.restorePosition(pos)

        self.buildContent()
        self.body.setPlainText(saved.get("text", ""))
        self.grip.reposition()

    def afterShow(self):
        # QPlainTextEdit lays out (and decides whether it needs a scrollbar)
        # against whatever geometry it had while the window was still
        # hidden, which can be stale - show()'s first real paint can flash
        # a scrollbar that vanishes as soon as anything triggers a repaint.
        # Flushing the pending layout here, before the card is actually
        # visible, keeps that first paint already correct.
        QApplication.processEvents()

    def buildContent(self):
        self.header_label = QLabel("Notes", self)
        header_font = QFont(style.CHAT_MONO_FAMILY)
        header_font.setPointSizeF(style.CHAT_HEADER_SIZE)
        header_font.setLetterSpacing(QFont.PercentageSpacing, style.CHAT_HEADER_TRACKING_PERCENT)
        self.header_label.setFont(header_font)
        self.header_label.setStyleSheet(f"color: {style.CHAT_LABEL_MONO}; background: transparent;")
        self.header_label.setAttribute(Qt.WA_TransparentForMouseEvents)

        self.close_button = QPushButton("✕", self)
        self.close_button.setFixedSize(18, 18)
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setStyleSheet(style.chat_close_stylesheet())
        self.close_button.clicked.connect(self.hide)

        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(self.header_label)
        header.addStretch(1)
        header.addWidget(self.close_button)

        self.body = QPlainTextEdit(self)
        self.body.setFrameShape(QPlainTextEdit.NoFrame)
        self.body.setStyleSheet(style.plain_field_stylesheet())
        self.body.document().setDocumentMargin(0)  # match the header's own zero *left* inset, not Qt's ~4px default
        # The header/body divider is drawn at self.body.y() (paintEvent,
        # below) - flush with the body widget's own top edge. Zero document
        # margin means the typed text starts right at that same y, so
        # without its own top inset the text sits flush against the divider
        # line with no breathing room, regardless of the header-to-divider
        # gap above (that's root's addSpacing below - a different gap).
        self.body.setViewportMargins(0, style.SPACE_2, 0, 0)
        self.body.textChanged.connect(self.scheduleSave)
        self.body.installEventFilter(self)  # Escape closes the card, not just the field

        root = QVBoxLayout(self)
        root.setContentsMargins(*[style.CHAT_PADDING + margin()] * 4)
        root.setSpacing(0)
        root.addLayout(header)
        root.addSpacing(style.SPACE_2)
        root.addWidget(self.body, 1)

        self.grip = ResizeGrip(self)

    # --- persistence ---

    def scheduleSave(self):
        self.save_timer.start(style.CARD_AUTOSAVE_MS)

    def save(self):
        cardStore.save(
            STORE_KEY,
            {
                "text": self.body.toPlainText(),
                "size": [self.width() - 2 * margin(), self.height() - 2 * margin()],
                "pos": [self.x(), self.y()],
            },
        )

    def hideEvent(self, event):
        self.save_timer.stop()
        self.save()
        super().hideEvent(event)

    def resizeEvent(self, event):
        if hasattr(self, "grip"):
            self.grip.reposition()
        super().resizeEvent(event)

    # --- input ---

    def eventFilter(self, watched, event):
        if watched is self.body and event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self.hide()
            return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        self.drag.press(event.globalPosition())

    def mouseMoveEvent(self, event):
        self.drag.move(event.globalPosition())

    def mouseReleaseEvent(self, event):
        self.drag.release()

    # --- painting ---

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        m = margin()
        frame = QRectF(self.rect()).adjusted(m + 0.5, m + 0.5, -m - 0.5, -m - 0.5)

        # Body reads one step lighter than the header bar - the one deliberate
        # exception in the palette, per floating-card-redesign.md: a note is
        # a different kind of object from the todo/chat cards.
        header_bottom = self.body.y()
        paint_card_bands(painter, frame, style.CHAT_RADIUS, style.SURFACE_RAISED, header_bottom, header_bottom)

        dragging = hasattr(self, "grip") and self.grip.dragging
        painter.setPen(QPen(QColor(style.card_border_color(dragging)), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(frame, style.CHAT_RADIUS, style.CHAT_RADIUS)
