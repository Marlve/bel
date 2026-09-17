# The "what is due" box a `! today` / `! week` answer shows in, per
# .scratch/command-styling/issues/01: a bordered inset with one row per
# event, name on the left and its time right-aligned, rows split by a thin
# divider. `! week` gets one box per day under that day's heading. It is
# information, not a form - no clicks, no dots, no accent.

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

import style
from notePicker import ElidedLabel, text_label


class DueRow(QFrame):
    def __init__(self, name, due, divided):
        super().__init__()
        self.setObjectName("dueRow")
        if divided:
            self.setStyleSheet(f"#dueRow {{ border: none; border-bottom: 1px solid {style.DUE_DIVIDER}; }}")

        self.name_label = ElidedLabel(name, style.DUE_NAME_TEXT, Qt.ElideRight)
        self.due_label = text_label(due, style.DUE_LABEL_TEXT)
        self.due_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.due_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)  # never squeezed, so the time is always whole

        layout = QHBoxLayout(self)
        layout.setContentsMargins(style.SPACE_3, style.SPACE_2, style.SPACE_3, style.SPACE_2)
        layout.setSpacing(style.SPACE_3)
        layout.addWidget(self.name_label, 1)
        layout.addWidget(self.due_label)


class DueList(QWidget):
    """`boxes` is timetable.due_boxes's list of (heading or None, rows)."""

    def __init__(self, boxes, width, parent=None):
        super().__init__(parent)
        self.setFixedWidth(width)
        self.headings = []
        self.boxes = []
        self.rows = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(style.SPACE_2)
        for heading, rows in boxes:
            if heading is not None:
                label = text_label(heading, style.DUE_HEADING_TEXT)  # brighter than the rows, not bold - brightness-only hierarchy
                self.headings.append(label)
                layout.addWidget(label)

            box = QFrame()
            box.setObjectName("dueBox")
            box.setStyleSheet(
                f"#dueBox {{ background: {style.DUE_FILL}; border: 1px solid {style.DUE_BORDER};"
                f" border-radius: {style.DUE_RADIUS}px; }}"
            )
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(0, 0, 0, 0)
            box_layout.setSpacing(0)
            for position, (name, due) in enumerate(rows):
                row = DueRow(name, due, divided=position < len(rows) - 1)
                box_layout.addWidget(row)
                self.rows.append(row)
            self.boxes.append(box)
            layout.addWidget(box)
