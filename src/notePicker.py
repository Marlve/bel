# The note picker a `?` lookup shows under Bel's answer or draft, per
# card.md: one row per candidate vault note, and clicking a row *is* the
# action - it picks where the `[[Concept]]` link goes and, on a miss,
# confirms writing the draft. A new Korean word reuses the same block with
# Vocab.md as its only row and its own header, and clicking it confirms
# saving the word (issue 23). No buttons, no modal; the outcome appends as a
# row inside the same block. Only the first click counts, since the pick
# may already have written to the vault.
#
# This widget never touches the vault itself - it only emits `picked`, and
# ChatCard calls vaultSearch.confirm_pick or append_vocab_row and reports
# back via showConnected/showSaved/showFailed.

import html
from pathlib import Path

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPalette, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

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


def matching_notes(notes, text):
    """The notes whose name or folder path contains `text`, ignoring case,
    the ".md" suffix and which slash separates folders, in their given (most
    recently edited) order."""
    wanted = text.replace("\\", "/").casefold()
    return [note for note in notes if wanted in Path(note["path"]).with_suffix("").as_posix().casefold()]


class NotePicker(QFrame):
    """`all_notes`, when given, adds issue 24's filter field: empty, the list
    is `notes` (the recent ones); typed into, it's every match in
    `all_notes`, filtered in memory rather than queried per keystroke."""

    picked = Signal(str)

    def __init__(self, notes, width, header="ambiguous — confirm the note", all_notes=None, parent=None):
        super().__init__(parent)
        self.setObjectName("notePicker")
        self.setStyleSheet(
            f"#notePicker {{ background: {style.PICKER_FILL}; border: 1px solid {style.PICKER_BORDER};"
            f" border-radius: {style.PICKER_RADIUS}px; }}"
        )
        self.setFixedWidth(width)
        self.outcome_label = None
        self.outcome_dot = None

        self.header_label = text_label(header, style.PICKER_HEADER_TEXT)
        header_row = QHBoxLayout()
        header_row.setSpacing(style.SPACE_2)
        header_row.addWidget(SearchIcon())
        header_row.addWidget(self.header_label)
        header_row.addStretch(1)

        self.notes = notes
        self.all_notes = all_notes
        self.filter_field = None
        if all_notes is not None:
            self.filter_field = QLineEdit()
            self.filter_field.setPlaceholderText("filter notes…")
            self.filter_field.setFocusPolicy(Qt.ClickFocus)  # the composer keeps focus when the picker pops in
            self.filter_field.setFixedHeight(style.PICKER_FILTER_HEIGHT)
            self.filter_field.setStyleSheet(
                f"background: {style.PICKER_FILTER_FILL}; color: {style.PICKER_HEADER_TEXT};"
                f" font-family: {style.FONT_FAMILY}; font-size: {style.CHAT_BODY_SIZE}px;"
                f" border: none; border-radius: {style.PICKER_FILTER_RADIUS}px; padding: 0 {style.SPACE_2}px;"
            )
            palette = self.filter_field.palette()
            palette.setColor(QPalette.PlaceholderText, QColor(style.MUTED))
            self.filter_field.setPalette(palette)
            self.filter_field.textChanged.connect(self.onFilterChanged)

        self.rows_widget = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_widget)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(0)
        self.empty_label = text_label("no matching notes", style.PICKER_FOLDER_TEXT)
        self.empty_label.setContentsMargins(0, style.SPACE_1, 0, style.SPACE_1)
        self.empty_label.setVisible(False)
        self.rows_layout.addWidget(self.empty_label)
        self.rows = []

        self.scroll = QScrollArea()
        self.scroll.setWidget(self.rows_widget)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setStyleSheet(style.chat_scrollbar_stylesheet())
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # same as the chat transcript - wheel still scrolls
        self.showNotes(notes)

        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(style.SPACE_3, style.SPACE_2, style.SPACE_3, style.SPACE_2)
        self.body.setSpacing(style.SPACE_2)
        self.body.addLayout(header_row)
        if self.filter_field is not None:
            self.body.addWidget(self.filter_field)
        self.body.addWidget(self.scroll)

    def showNotes(self, notes):
        """Replaces the listed rows with `notes`, or the "no matching notes"
        line when there are none."""
        for row in self.rows:
            self.rows_layout.removeWidget(row)
            row.hide()
            row.deleteLater()
        self.rows = []
        for note in notes:
            row = NoteRow(note)
            row.clicked.connect(self.onRowClicked)
            self.rows_layout.addWidget(row)
            # A row added to a picker already on screen stays hidden until
            # the next event loop pass, and the layout skips hidden rows -
            # the height below would come out 0 and the list look empty.
            row.setVisible(True)
            self.rows.append(row)
        self.empty_label.setVisible(not notes)
        self.scroll.setFixedHeight(min(self.rows_widget.sizeHint().height(), style.PICKER_LIST_MAX_HEIGHT))

    def onFilterChanged(self, text):
        text = text.strip()
        self.showNotes(matching_notes(self.all_notes, text) if text else self.notes)

    def onRowClicked(self, path):
        for row in self.rows:
            row.enabled = False
            row.setCursor(Qt.ArrowCursor)
            row.setNameColor(style.PICKER_NOTE_TEXT)
        if self.filter_field is not None:
            self.filter_field.setReadOnly(True)
        self.picked.emit(path)

    def showConnected(self, name):
        self.showOutcome(f"connected to <b>{html.escape(name)}</b>", style.PICKER_DOT_RECENT, Qt.RichText)

    def showSaved(self, name):
        self.showOutcome(f"saved to <b>{html.escape(name)}</b>", style.PICKER_DOT_RECENT, Qt.RichText)

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
