# The note picker a `?` lookup shows under Bel's answer or draft, per
# card.md: one row per candidate vault note, and clicking a row *is* the
# action - it picks where the `[[Concept]]` link goes and, on a miss,
# confirms writing the draft. No buttons, no modal; the outcome appends as a
# row inside the same block. Only the first click counts, since the pick
# may already have written to the vault.
#
# This widget never touches the vault itself - it only emits `picked`, and
# ChatCard calls vaultSearch.confirm_pick and reports back via
# showConnected/showFailed.

import html
from pathlib import Path

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

import style


def label_stylesheet(color):
    return f"color: {color}; font-family: {style.FONT_FAMILY}; font-size: {style.CHAT_BODY_SIZE}px; background: transparent;"


def text_label(text, color, text_format=Qt.PlainText):
    label = QLabel(text)
    label.setTextFormat(text_format)
    label.setStyleSheet(label_stylesheet(color))
    return label


class ElidedLabel(QLabel):
    """Shortens its text with "…" to whatever width the row gives it, so a
    long note name or deep folder path can't push the row past the
    picker's edge."""

    def __init__(self, text, color, elide_mode):
        super().__init__(text)
        self.full_text = text
        self.elide_mode = elide_mode
        self.setTextFormat(Qt.PlainText)
        self.setStyleSheet(label_stylesheet(color))
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setText(self.fontMetrics().elidedText(self.full_text, self.elide_mode, self.width()))


class Dot(QWidget):
    def __init__(self, color):
        super().__init__()
        self.color = color
        self.setFixedSize(style.PICKER_DOT_SIZE, style.PICKER_DOT_SIZE)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self.color))
        painter.drawEllipse(self.rect())


class SearchIcon(QWidget):
    """A small magnifier - circle plus handle."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(style.PICKER_ICON_SIZE, style.PICKER_ICON_SIZE)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(style.PICKER_HEADER_TEXT), 1.2))
        size = self.width()
        lens = size * 0.62
        painter.drawEllipse(QPointF(lens / 2 + 0.5, lens / 2 + 0.5), lens / 2 - 0.5, lens / 2 - 0.5)
        painter.drawLine(QPointF(lens * 0.9, lens * 0.9), QPointF(size - 1, size - 1))


class NoteRow(QWidget):
    clicked = Signal(str)

    def __init__(self, note):
        super().__init__()
        self.path = note["path"]
        self.enabled = True
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover)

        path = Path(self.path)
        self.dot = Dot(style.PICKER_DOT_RECENT if note["recent"] else style.PICKER_DOT_OLDER)
        self.name_label = ElidedLabel(path.stem, style.PICKER_NOTE_TEXT, Qt.ElideRight)
        folder = str(path.parent)
        # Elided from the left, so the folder nearest the note stays visible.
        self.folder_label = ElidedLabel("" if folder == "." else folder, style.PICKER_FOLDER_TEXT, Qt.ElideLeft)
        self.folder_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, style.SPACE_1, 0, style.SPACE_1)
        layout.setSpacing(style.SPACE_2)
        layout.addWidget(self.dot)
        layout.addWidget(self.name_label, 3)
        layout.addWidget(self.folder_label, 2)

    def setNameColor(self, color):
        self.name_label.setStyleSheet(label_stylesheet(color))

    def enterEvent(self, event):
        if self.enabled:
            self.setNameColor(style.PICKER_HEADER_TEXT)

    def leaveEvent(self, event):
        self.setNameColor(style.PICKER_NOTE_TEXT)

    def mouseReleaseEvent(self, event):
        if self.enabled and event.button() == Qt.LeftButton:
            self.clicked.emit(self.path)


class NotePicker(QFrame):
    picked = Signal(str)

    def __init__(self, notes, width, parent=None):
        super().__init__(parent)
        self.setObjectName("notePicker")
        self.setStyleSheet(
            f"#notePicker {{ background: {style.PICKER_FILL}; border: 1px solid {style.PICKER_BORDER};"
            f" border-radius: {style.PICKER_RADIUS}px; }}"
        )
        self.setFixedWidth(width)
        self.outcome_label = None
        self.outcome_dot = None

        header = QHBoxLayout()
        header.setSpacing(style.SPACE_2)
        header.addWidget(SearchIcon())
        header.addWidget(text_label("ambiguous — confirm the note", style.PICKER_HEADER_TEXT))
        header.addStretch(1)

        rows_widget = QWidget()
        rows_layout = QVBoxLayout(rows_widget)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(0)
        self.rows = []
        for note in notes:
            row = NoteRow(note)
            row.clicked.connect(self.onRowClicked)
            rows_layout.addWidget(row)
            self.rows.append(row)

        self.scroll = QScrollArea()
        self.scroll.setWidget(rows_widget)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setStyleSheet(style.chat_scrollbar_stylesheet())
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # same as the chat transcript - wheel still scrolls
        self.scroll.setFixedHeight(min(rows_widget.sizeHint().height(), style.PICKER_LIST_MAX_HEIGHT))

        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(style.SPACE_3, style.SPACE_2, style.SPACE_3, style.SPACE_2)
        self.body.setSpacing(style.SPACE_2)
        self.body.addLayout(header)
        self.body.addWidget(self.scroll)

    def onRowClicked(self, path):
        for row in self.rows:
            row.enabled = False
            row.setCursor(Qt.ArrowCursor)
            row.setNameColor(style.PICKER_NOTE_TEXT)
        self.picked.emit(path)

    def showConnected(self, name):
        self.showOutcome(f"connected to <b>{html.escape(name)}</b>", style.PICKER_DOT_RECENT, Qt.RichText)

    def showFailed(self, text):
        self.showOutcome(text, style.PICKER_DOT_OLDER, Qt.PlainText)

    def showOutcome(self, text, dot_color, text_format):
        self.outcome_dot = Dot(dot_color)
        self.outcome_label = text_label(text, style.PICKER_HEADER_TEXT, text_format)
        self.outcome_label.setWordWrap(True)
        row = QHBoxLayout()
        row.setSpacing(style.SPACE_2)
        row.addWidget(self.outcome_dot)
        row.addWidget(self.outcome_label, 1)
        self.body.addLayout(row)
