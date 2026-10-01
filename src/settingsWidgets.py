# Small building blocks for the tabbed Settings card: a setting's row, an
# on/off switch, a segmented choice, a status line. Kept apart from
# settingsCard.py so that file stays about the card's own behaviour.

from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QAbstractButton, QButtonGroup, QVBoxLayout, QHBoxLayout
from PySide6.QtGui import QPainter, QColor
from PySide6.QtCore import Qt, QRectF, Signal

import style
from hotkey import format_hotkey

MODIFIER_KEYS = (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta, Qt.Key_AltGr)


class Toggle(QAbstractButton):
    """An on/off switch: the track fills with the accent when on."""

    def __init__(self, parent, checked=False):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(style.SETTINGS_TOGGLE_WIDTH, style.SETTINGS_TOGGLE_HEIGHT)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        height = self.height()
        track = QRectF(self.rect())
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(style.CHAT_ACCENT if self.isChecked() else style.CHAT_INERT_HINT))
        painter.drawRoundedRect(track, height / 2, height / 2)
        knob = height - 4
        x = track.right() - knob - 2 if self.isChecked() else track.left() + 2
        painter.setBrush(QColor(style.CHAT_BODY_TEXT))
        painter.drawEllipse(QRectF(x, track.top() + 2, knob, knob))


class Segmented(QWidget):
    """A row of mutually exclusive options. `disabled` names options that are
    shown but not selectable yet."""

    def __init__(self, parent, options, current, on_change=None, disabled=()):
        super().__init__(parent)
        self.setStyleSheet(f"background: {style.CARD_BODY}; border-radius: 8px;")
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)
        for option in options:
            button = QPushButton(option, self)
            button.setCheckable(True)
            button.setChecked(option == current)
            button.setEnabled(option not in disabled)
            button.setCursor(Qt.PointingHandCursor)
            button.setFixedHeight(style.SETTINGS_BUTTON_HEIGHT - 6)
            button.setStyleSheet(style.settings_segment_stylesheet())
            self.group.addButton(button)
            layout.addWidget(button)
        if on_change is not None:
            self.group.buttonClicked.connect(lambda button: on_change(button.text()))


class KeyCapture(QPushButton):
    """Shows a hotkey; click it, then press the new combo. Needs a Ctrl, Shift
    or Alt unless the key is an F-key, so it can't swallow plain typing.
    Escape or clicking away keeps the old one."""

    captured = Signal(str)

    def __init__(self, parent, combo):
        super().__init__(parent)
        self.combo = combo
        self.capturing = False
        self.setFixedHeight(style.SETTINGS_BUTTON_HEIGHT)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(style.settings_button_stylesheet())
        self.clicked.connect(self.startCapture)
        self.showCombo()

    def setCombo(self, combo):
        self.combo = combo
        self.showCombo()

    def showCombo(self):
        self.capturing = False
        self.setText(format_hotkey(self.combo))

    def startCapture(self):
        self.capturing = True
        self.setText("Press keys...")
        self.setFocus()

    def keyPressEvent(self, event):
        if not self.capturing:
            super().keyPressEvent(event)
            return
        key = event.key()
        if key == Qt.Key_Escape:
            self.showCombo()
        elif key not in MODIFIER_KEYS:
            combo = self.comboFromEvent(event)
            if combo is None:
                return
            self.showCombo()
            self.captured.emit(combo)

    def comboFromEvent(self, event):
        key = event.key()
        is_function_key = Qt.Key_F1 <= key <= Qt.Key_F24
        if key == Qt.Key_Space:
            name = "space"
        elif Qt.Key_A <= key <= Qt.Key_Z:
            name = chr(key).lower()
        elif is_function_key:
            name = f"f{key - Qt.Key_F1 + 1}"
        else:
            return None
        modifiers = [
            word for word, flag in (("ctrl", Qt.ControlModifier), ("shift", Qt.ShiftModifier), ("alt", Qt.AltModifier))
            if event.modifiers() & flag
        ]
        if not modifiers and not is_function_key:
            return None
        return "+".join(modifiers + [name])

    def focusOutEvent(self, event):
        if self.capturing:
            self.showCombo()
        super().focusOutEvent(event)


def ghost_button(parent, text, enabled=True):
    button = QPushButton(text, parent)
    button.setEnabled(enabled)
    button.setFixedHeight(style.SETTINGS_BUTTON_HEIGHT)
    button.setCursor(Qt.PointingHandCursor if enabled else Qt.ArrowCursor)
    button.setStyleSheet(style.settings_button_stylesheet())
    return button


def status_line(parent, text, ok):
    """A dot and a short sentence - teal when the thing is ready, gray when it is not."""
    dot = QLabel(parent)
    dot.setFixedSize(7, 7)
    color = style.STATUS_OK if ok else style.CHAT_INERT_HINT
    dot.setStyleSheet(f"background: {color}; border-radius: 3px;")
    label = QLabel(text, parent)
    label.setStyleSheet(style.settings_desc_stylesheet())
    row = QHBoxLayout()
    row.setSpacing(7)
    row.addWidget(dot)
    row.addWidget(label, 1)
    return row, label, dot


class SettingRow(QWidget):
    """A setting: its name and one line of help on the left, its control on the
    right, a hairline above. `stacked` puts the control under the name instead,
    for a wide control like a text field."""

    def __init__(self, parent, title, desc="", control=None, stacked=False):
        super().__init__(parent)
        self.title = QLabel(title, self)
        self.title.setStyleSheet(style.settings_title_stylesheet())
        text = QVBoxLayout()
        text.setSpacing(3)
        text.addWidget(self.title)
        if desc:
            self.desc = QLabel(desc, self)
            self.desc.setStyleSheet(style.settings_desc_stylesheet())
            self.desc.setWordWrap(True)
            text.addWidget(self.desc)

        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(0, style.SPACE_3, 0, style.SPACE_3)
        self.body.setSpacing(style.SPACE_2)
        if stacked:
            self.body.addLayout(text)
        else:
            head = QHBoxLayout()
            head.setSpacing(style.SPACE_4)
            head.addLayout(text, 1)
            self.head = head
            self.body.addLayout(head)
        self.stacked = stacked
        if control is not None:
            self.addControl(control)

    def addControl(self, control):
        target = self.body if self.stacked else self.head
        if isinstance(control, QWidget):
            target.addWidget(control)
        else:
            target.addLayout(control)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QColor(style.CARD_DIVIDER))
        painter.drawLine(0, 0, self.width(), 0)
