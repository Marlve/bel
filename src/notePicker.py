# The note picker a `?` lookup shows under Bel's answer or draft, per
# card.md: one row per candidate vault note, and clicking a row *is* the
# action - it picks where the `[[Concept]]` link goes and, on a miss,
# confirms writing the draft. A new Korean word reuses the same block with
# Vocab.md as its only row and its own header, and clicking it confirms
# saving the word (issue 23). No buttons, no modal; how the pick went shows
# on the picked row's second line, and the other rows dim. Only the first
# click counts, since the pick may already have written to the vault.
#
# This widget never touches the vault itself - it only emits `picked`, and
# ChatCard calls vaultSearch.confirm_pick or append_vocab_row and reports
# back via showConnected/showSaved/showFailed. NoteRow and NoteList are
# shared with the `! organize` box (organizeList.py), so both look the same.

from pathlib import Path

from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPalette, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

import style


def label_stylesheet(color, size=None):
    # Looked up here, not as a default argument, so style.apply_scale has already run.
    size = size or style.CHAT_BODY_SIZE
    return f"color: {color}; font-family: {style.FONT_FAMILY}; font-size: {size}px; background: transparent;"


def text_label(text, color, size=None):
    label = QLabel(text)
    label.setTextFormat(Qt.PlainText)
    label.setStyleSheet(label_stylesheet(color, size))
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

    def setFullText(self, text):
        self.full_text = text
        self.setText(self.fontMetrics().elidedText(self.full_text, self.elide_mode, self.width()))

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


class NoteRow(QFrame):
    """One clickable row: a name, its folder right-aligned in dim mono, and
    a smaller second line, hidden until it has something to say. The
    `! organize` box's rows pass no `dot_color` and get no dot."""

    clicked = Signal(str)

    def __init__(self, path, name, folder, dot_color=None):
        super().__init__()
        self.setObjectName("noteRow")
        self.path = path
        self.enabled = True
        self.press_pos = None
        self.divided = False
        self.name_color = style.PICKER_NOTE_TEXT
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover)

        self.dot = Dot(dot_color) if dot_color else None
        self.name_label = ElidedLabel(name, self.name_color, Qt.ElideRight)
        # Elided from the left, so the folder nearest the note stays visible.
        self.folder_label = ElidedLabel(folder, style.PICKER_FOLDER_TEXT, Qt.ElideLeft)
        self.folder_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.detail_label = text_label("", style.PICKER_DETAIL_TEXT, size=style.PICKER_DETAIL_SIZE)
        self.detail_label.setWordWrap(True)
        if self.dot is not None:
            self.detail_label.setContentsMargins(style.PICKER_DOT_SIZE + style.SPACE_2, 0, 0, 0)  # lines up under the name
        self.detail_label.hide()

        top = QHBoxLayout()
        top.setSpacing(style.SPACE_2)
        if self.dot is not None:
            top.addWidget(self.dot)
        top.addWidget(self.name_label, 3)
        top.addWidget(self.folder_label, 2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, style.SPACE_1, 0, style.SPACE_1)
        layout.setSpacing(0)
        layout.addLayout(top)
        layout.addWidget(self.detail_label)

    def setDivided(self, divided):
        self.divided = divided
        self.setStyleSheet(f"#noteRow {{ border: none; border-bottom: 1px solid {style.PICKER_DIVIDER}; }}" if divided else "")

    def showDetail(self, text):
        self.detail_label.setText(text)
        self.detail_label.setVisible(bool(text))

    def paintName(self, color):
        self.name_label.setStyleSheet(label_stylesheet(color))

    def lock(self):
        self.enabled = False
        self.setCursor(Qt.ArrowCursor)
        self.paintName(self.name_color)

    def dim(self):
        self.name_color = style.PICKER_DIM_TEXT
        self.paintName(self.name_color)
        self.folder_label.setStyleSheet(label_stylesheet(style.PICKER_DIM_SECONDARY))
        if self.dot is not None:
            self.dot.color = style.PICKER_DIM_SECONDARY
            self.dot.update()

    def enterEvent(self, event):
        if self.enabled:
            self.paintName(style.PICKER_HEADER_TEXT)

    def leaveEvent(self, event):
        self.paintName(self.name_color)

    def mousePressEvent(self, event):
        self.press_pos = event.globalPosition()
        event.ignore()  # the card still sees the press, so a drag can start here

    def mouseReleaseEvent(self, event):
        # Passed on to the card too, or a drag that started on this row
        # never docks. A press that travelled as far as a drag isn't a click.
        event.ignore()
        travelled = event.globalPosition() - self.press_pos if self.press_pos is not None else None
        self.press_pos = None
        if travelled is None or travelled.x() ** 2 + travelled.y() ** 2 >= style.CARD_DRAG_THRESHOLD_PX ** 2:
            return
        if self.enabled and event.button() == Qt.LeftButton:
            self.clicked.emit(self.path)


def note_row(note):
    path = Path(note["path"])
    folder = str(path.parent)
    dot_color = style.PICKER_DOT_RECENT if note["recent"] else style.PICKER_DOT_OLDER
    return NoteRow(note["path"], path.stem, "" if folder == "." else folder, dot_color)


def matching_notes(notes, text):
    """The notes whose name or folder path contains `text`, ignoring case,
    the ".md" suffix and which slash separates folders, in their given (most
    recently edited) order."""
    wanted = text.replace("\\", "/").casefold()
    return [note for note in notes if wanted in Path(note["path"]).with_suffix("").as_posix().casefold()]


class NoteList(QWidget):
    """A scrollable list of note rows. `all_notes`, when given, adds issue
    24's filter field: empty, the list is `notes` (the recent ones); typed
    into, it's every match in `all_notes`, filtered in memory rather than
    queried per keystroke. The first click locks every row and dims all but
    the picked one."""

    picked = Signal(str)

    def __init__(self, notes, all_notes=None, placeholder="filter notes…", parent=None):
        super().__init__(parent)
        self.notes = notes
        self.all_notes = all_notes
        self.picked_row = None
        self.filter_field = None
        if all_notes is not None:
            self.filter_field = QLineEdit()
            self.filter_field.setPlaceholderText(placeholder)
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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(style.SPACE_2)
        if self.filter_field is not None:
            layout.addWidget(self.filter_field)
        layout.addWidget(self.scroll)

    def showNotes(self, notes):
        """Replaces the listed rows with `notes`, or the "no matching notes"
        line when there are none."""
        for row in self.rows:
            self.rows_layout.removeWidget(row)
            row.hide()
            row.deleteLater()
        self.rows = []
        for position, note in enumerate(notes):
            row = note_row(note)
            row.setDivided(position < len(notes) - 1)
            row.clicked.connect(lambda path, row=row: self.onRowClicked(row))
            self.rows_layout.addWidget(row)
            # A row added to a picker already on screen stays hidden until
            # the next event loop pass, and the layout skips hidden rows -
            # the height below would come out 0 and the list look empty.
            row.setVisible(True)
            self.rows.append(row)
        self.empty_label.setVisible(not notes)
        self.fitHeight()

    def fitHeight(self):
        self.scroll.setFixedHeight(min(self.rows_widget.sizeHint().height(), style.PICKER_LIST_MAX_HEIGHT))

    def onFilterChanged(self, text):
        text = text.strip()
        self.showNotes(matching_notes(self.all_notes, text) if text else self.notes)

    def onRowClicked(self, picked):
        self.picked_row = picked
        for row in self.rows:
            row.lock()
            if row is not picked:
                row.dim()
        if self.filter_field is not None:
            self.filter_field.setReadOnly(True)
        self.picked.emit(picked.path)

    def lockRows(self):
        """Makes every row display-only - no pointer cursor, no hover, no
        click. What a "maybe" block wants: notes to notice, not to act on."""
        for row in self.rows:
            row.lock()

    def showResult(self, text):
        self.picked_row.showDetail(text)
        self.fitHeight()  # the second line makes the picked row taller
        # Once the layout has made room for that line, so a capped list
        # doesn't leave it hidden below the fold.
        QTimer.singleShot(0, self, lambda: self.scroll.ensureWidgetVisible(self.picked_row, 0, 0))


class NotePicker(QFrame):
    """card.md's block: a header over a NoteList (see there for
    `all_notes`)."""

    picked = Signal(str)

    def __init__(self, notes, width, header="ambiguous — confirm the note", all_notes=None, parent=None):
        super().__init__(parent)
        self.setObjectName("notePicker")
        self.setStyleSheet(
            f"#notePicker {{ background: {style.PICKER_FILL}; border: 1px solid {style.PICKER_BORDER};"
            f" border-radius: {style.PICKER_RADIUS}px; }}"
        )
        self.setFixedWidth(width)

        self.header_label = ElidedLabel(header, style.PICKER_HEADER_TEXT, Qt.ElideRight)
        header_row = QHBoxLayout()
        header_row.setSpacing(style.SPACE_2)
        header_row.addWidget(SearchIcon())
        header_row.addWidget(self.header_label, 1)

        self.list = NoteList(notes, all_notes)
        self.list.picked.connect(self.picked)
        self.filter_field = self.list.filter_field
        self.scroll = self.list.scroll
        self.empty_label = self.list.empty_label

        body = QVBoxLayout(self)
        body.setContentsMargins(style.SPACE_3, style.SPACE_2, style.SPACE_3, style.SPACE_2)
        body.setSpacing(style.SPACE_2)
        body.addLayout(header_row)
        body.addWidget(self.list)

    @property
    def rows(self):
        return self.list.rows

    def lockRows(self):
        self.list.lockRows()

    def showConnected(self):
        self.list.showResult("connected")

    def showSaved(self):
        self.list.showResult("saved")

    def showFailed(self, text):
        self.list.showResult(text)
