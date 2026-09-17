# The box a `! organize` answer shows in, per
# .scratch/command-styling/issues/01: one row per Inbox note, name on the
# left and the folder it's going to on the right, with what filing does
# beyond the move (rename, new folder, links, Atlas hub) on a smaller second
# line. Clicking a row files that note; a filed row dims and its second line
# says how it went. A note with no usable proposal says "pick a folder", and
# clicking it expands a filter field and folder list under that row.
#
# Like NotePicker, this never touches the vault - an entry emits `filed`,
# and ChatCard calls inboxOrganize.organize and reports back via
# showMoved/showFailed.

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QVBoxLayout

import style
from notePicker import NoteList, NoteRow


def organize_details(proposal):
    """What clicking a note's row will do, beyond the folder the row
    already shows."""
    if proposal["folder"] is None:
        return ""
    changes = []
    if proposal["new_folder"]:
        changes.append("new folder")
    if proposal["name"] != proposal["path"].stem:
        changes.append(f"renamed {proposal['name']}")
    if proposal["related"]:
        changes.append("links " + ", ".join(proposal["related"]))
    if proposal["atlas"]:
        changes.append(f"listed in {Path(proposal['atlas']).stem}")
    return " · ".join(changes)


class OrganizeEntry(QFrame):
    """One Inbox note's row, plus its folder list when it has no proposal."""

    filed = Signal(str)

    def __init__(self, proposal, folders):
        super().__init__()
        self.setObjectName("organizeEntry")
        self.proposal = proposal
        self.divided = False

        self.row = NoteRow(str(proposal["path"]), proposal["path"].stem, proposal["folder"] or "pick a folder")
        self.row.showDetail(organize_details(proposal))
        self.row.clicked.connect(self.onRowClicked)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(style.SPACE_3, style.SPACE_1, style.SPACE_3, style.SPACE_1)
        layout.setSpacing(style.SPACE_1)
        layout.addWidget(self.row)

        self.folder_list = None
        if proposal["folder"] is None:
            rows = [{"path": folder, "recent": False} for folder in folders]
            self.folder_list = NoteList(rows, all_notes=rows, placeholder="filter folders…")
            self.folder_list.picked.connect(self.onFolderPicked)
            self.folder_list.hide()
            layout.addWidget(self.folder_list)

    def setDivided(self, divided):
        self.divided = divided
        self.setStyleSheet(f"#organizeEntry {{ border: none; border-bottom: 1px solid {style.PICKER_DIVIDER}; }}" if divided else "")

    def onRowClicked(self):
        if self.folder_list is None:
            self.row.lock()
            self.filed.emit(self.proposal["folder"])
        else:
            self.folder_list.setVisible(self.folder_list.isHidden())

    def onFolderPicked(self, folder):
        self.folder_list.hide()
        self.row.folder_label.setFullText(folder)
        self.row.lock()
        self.filed.emit(folder)

    def showMoved(self, linked):
        self.row.dim()
        self.row.showDetail("moved" if linked else "moved, but couldn't add its links")

    def showFailed(self):
        self.row.showDetail("couldn't move the note")


class OrganizeList(QFrame):
    def __init__(self, proposals, folders, width, parent=None):
        super().__init__(parent)
        self.setObjectName("organizeList")
        self.setStyleSheet(
            f"#organizeList {{ background: {style.PICKER_FILL}; border: 1px solid {style.PICKER_BORDER};"
            f" border-radius: {style.PICKER_RADIUS}px; }}"
        )
        self.setFixedWidth(width)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.entries = []
        for position, proposal in enumerate(proposals):
            entry = OrganizeEntry(proposal, folders)
            entry.setDivided(position < len(proposals) - 1)
            layout.addWidget(entry)
            self.entries.append(entry)
