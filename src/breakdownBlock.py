# The block a `?` sentence lookup shows under its translation (korean.md):
# every word and grammar point the sentence uses, with the ones already in
# the vault dimmed and the new ones clickable to file them.
#
# It shows all of them rather than only the new ones on purpose
# (.scratch/korean-sentence/issues/02): a sentence Derich typed is one he is
# trying to read, so the explanation is the point and filing is the side
# effect. A new-only list would drop a word from the explanation of his own
# sentence the moment he saved it.
#
# Rows are NoteRow, shared with the note picker and the `! organize` box, so
# all three look the same. NoteList is deliberately not reused: it locks and
# dims every other row on a click, because a picker is a one-shot choice -
# here each row is filed on its own and the rest must stay live. It has no
# scroll area either; a sentence's worth of rows can't run away the way a
# vault's worth of notes can.
#
# Never touches the vault itself - it emits `picked` and ChatCard calls
# vaultSearch.append_vocab_row / append_grammar_row, reporting back through
# showSaved/showFailed. Same split as NotePicker.

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout

import style
from notePicker import ElidedLabel, NoteRow, SearchIcon, text_label


def word_name(word):
    """How a word row reads: the form as written, then the dictionary form it
    files under. Collapsed to one when they're the same, so an unchanged word
    doesn't read as "매일 → 매일"."""
    if word["surface"] == word["lemma"]:
        return word["lemma"]
    return f"{word['surface']} → {word['lemma']}"


def entries(breakdown):
    """The breakdown's words and grammar points as one list of rows to build,
    each carrying what append_vocab_row/append_grammar_row would need. `term`
    is the lemma for a word and the point itself for grammar - in both cases
    the cell resolve_breakdown matched on, so a row's key can't drift from
    what gets written."""
    rows = [
        {"kind": "word", "key": f"word:{word['lemma']}", "name": word_name(word),
         "term": word["lemma"], "meaning": word["meaning"], "filed": word["row"] is not None}
        for word in breakdown["words"]
    ]
    rows += [
        {"kind": "grammar", "key": f"grammar:{point['point']}", "name": point["point"],
         "term": point["point"], "meaning": point["meaning"], "filed": point["row"] is not None}
        for point in breakdown["grammar"]
    ]
    return rows


class BreakdownBlock(QFrame):
    """card.md's picker block, rebuilt for a sentence: a header, then a
    "words" section and a "grammar" section, each a list of NoteRows.

    Emits `picked` with the entry dict of a clicked row. Only new rows are
    clickable - a filed one is locked and dimmed, since there is nothing to
    write for it."""

    picked = Signal(object)

    def __init__(self, breakdown, width, header="breakdown — click a new word or point to save it", parent=None):
        super().__init__(parent)
        self.setObjectName("breakdownBlock")
        self.setStyleSheet(
            f"#breakdownBlock {{ background: {style.PICKER_FILL}; border: 1px solid {style.PICKER_BORDER};"
            f" border-radius: {style.PICKER_RADIUS}px; }}"
        )
        self.setFixedWidth(width)
        self.rows = {}

        header_row = QHBoxLayout()
        header_row.setSpacing(style.SPACE_2)
        header_row.addWidget(SearchIcon())
        header_row.addWidget(ElidedLabel(header, style.PICKER_HEADER_TEXT, Qt.ElideRight), 1)

        body = QVBoxLayout(self)
        body.setContentsMargins(style.SPACE_3, style.SPACE_2, style.SPACE_3, style.SPACE_2)
        body.setSpacing(style.SPACE_2)
        body.addLayout(header_row)

        all_entries = entries(breakdown)
        for kind, title in (("word", "words"), ("grammar", "grammar")):
            section = [entry for entry in all_entries if entry["kind"] == kind]
            if not section:
                # A one-word "sentence" never reaches this block, but a
                # breakdown with no grammar points is an ordinary answer -
                # an empty heading over nothing would read as a failure.
                continue
            body.addWidget(text_label(title, style.PICKER_FOLDER_TEXT, size=style.PICKER_DETAIL_SIZE))
            for position, entry in enumerate(section):
                body.addWidget(self.buildRow(entry, divided=position < len(section) - 1))

    def buildRow(self, entry, divided):
        # The meaning goes on the detail line, not in NoteRow's right-hand
        # slot. That slot is sized and elided for folder paths - 2/5 of the
        # row, cut from the left so the tail survives - which would serve a
        # grammar explanation as "…hat the sentence is about". The detail line
        # is full width and wraps. The slot carries the row's state instead,
        # which is short enough to always fit.
        row = NoteRow(entry["key"], entry["name"], "filed" if entry["filed"] else "")
        row.showDetail(entry["meaning"])
        row.setDivided(divided)
        if entry["filed"]:
            # Nothing to write, so nothing to click. Dimmed as well as locked,
            # or a filed row reads as one that failed to respond. The meaning
            # stays readable: the block explains the sentence whether or not
            # there is anything left to file.
            row.lock()
            row.dim()
        else:
            row.clicked.connect(lambda key, entry=entry: self.picked.emit(entry))
        self.rows[entry["key"]] = row
        return row

    def showSaved(self, key):
        """Marks one row written and takes it out of play, leaving every other
        new row still clickable - the whole reason this isn't a NoteList."""
        row = self.rows[key]
        row.lock()
        row.dim()
        row.folder_label.setFullText("saved")

    def showFailed(self, key, text):
        """Reports a failed write in the row's state slot. The row stays
        locked - the pick may already have touched the vault, same rule as the
        note picker's first-click-only."""
        row = self.rows[key]
        row.lock()
        row.folder_label.setFullText(text)
