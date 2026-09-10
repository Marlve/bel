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
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QCursor
from PySide6.QtCore import Qt, QRectF, QTimer, QEvent

import style
import shadow
import card_store
from draggable import WindowDrag, ResizeGrip

STORE_KEY = "note"
MARGIN = style.CARD_SHADOW_MARGIN  # extra window room around the visible face, for the shadow


class NoteCard(QWidget):
    def __init__(self):
        super().__init__(None)  # top-level: outlives the ring, persists for the app's life
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(style.CARD_MIN_SIZE + 2 * MARGIN, style.CARD_MIN_SIZE + 2 * MARGIN)

        self.drag = WindowDrag(self)
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save)
        shadow.apply(self)

        saved = card_store.load(STORE_KEY, {})
        face_w, face_h = saved.get("size", [style.CHAT_SIZE, style.CHAT_SIZE])
        self.resize(face_w + 2 * MARGIN, face_h + 2 * MARGIN)

        self.buildContent()
        self.body.setPlainText(saved.get("text", ""))
        self.grip.reposition()

    def open(self):
        """Lands near wherever the wedge was picked - like the ring itself
        always opening at the cursor, not wherever the card happened to be
        left after a previous drag or a previous session."""
        self.moveNear(QCursor.pos())
        self.show()
        self.raise_()

    def moveNear(self, cursor_pos):
        screen = QApplication.screenAt(cursor_pos) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        x = cursor_pos.x() + style.CARD_SPAWN_OFFSET - MARGIN
        y = cursor_pos.y() + style.CARD_SPAWN_OFFSET - MARGIN
        x = max(area.x(), min(x, area.x() + area.width() - self.width()))
        y = max(area.y(), min(y, area.y() + area.height() - self.height()))
        self.move(x, y)

    def buildContent(self):
        self.header_label = QLabel("NOTE", self)
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
        self.body.setStyleSheet(style.note_body_stylesheet())
        self.body.textChanged.connect(self.scheduleSave)
        self.body.installEventFilter(self)  # Escape closes the card, not just the field

        root = QVBoxLayout(self)
        root.setContentsMargins(*[style.CHAT_PADDING + MARGIN] * 4)
        root.setSpacing(10)
        root.addLayout(header)
        root.addWidget(self.body, 1)

        self.grip = ResizeGrip(self)

    # --- persistence ---

    def scheduleSave(self):
        self.save_timer.start(style.CARD_AUTOSAVE_MS)

    def save(self):
        card_store.save(
            STORE_KEY,
            {"text": self.body.toPlainText(), "size": [self.width() - 2 * MARGIN, self.height() - 2 * MARGIN]},
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
        frame = QRectF(self.rect()).adjusted(MARGIN + 0.5, MARGIN + 0.5, -MARGIN - 0.5, -MARGIN - 0.5)
        painter.setBrush(QColor(style.CHAT_SURFACE))
        painter.setPen(QPen(QColor(style.CHAT_BORDER), 1))
        painter.drawRoundedRect(frame, style.CHAT_RADIUS, style.CHAT_RADIUS)
