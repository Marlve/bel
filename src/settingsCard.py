# Settings (wedge always pinned near the bottom of the ring, per
# wedgeConfig.full_config) - lets you relabel, reorder, or reassign the
# ring's other wedges. Same toggled-square shape as note/todo (see
# noteCard.py): built lazily on first pick, then just shown/hidden.

from PySide6.QtWidgets import QWidget, QLabel, QLineEdit, QComboBox, QPushButton, QVBoxLayout, QHBoxLayout
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QCursor
from PySide6.QtCore import Qt, QRectF, QTimer, QEvent

import style
import shadow
import screenBounds
import wedgeConfig
from draggable import WindowDrag

def margin():
    return style.CARD_SHADOW_MARGIN  # extra window room around the visible face, for the shadow


class SettingsRow(QWidget):
    """One editable wedge: label field, action picker, reorder arrows."""

    def __init__(self, card, entry, is_first, is_last):
        super().__init__(card)
        self.card = card
        self.assigned_id = entry["id"]
        self.setFixedHeight(style.SETTINGS_ROW_HEIGHT)

        self.label_field = QLineEdit(entry["label"], self)
        self.label_field.setStyleSheet(style.settings_field_stylesheet())
        self.label_field.textChanged.connect(card.scheduleSave)
        self.label_field.installEventFilter(card)  # Escape closes the card, not just the field

        self.action_combo = QComboBox(self)
        self.action_combo.setStyleSheet(style.settings_combo_stylesheet())
        for action_id, display in wedgeConfig.ACTION_CHOICES:
            self.action_combo.addItem(display, action_id)
        self.action_combo.setCurrentIndex(self.action_combo.findData(entry["id"]))
        self.action_combo.currentIndexChanged.connect(lambda: card.onActionChanged(self))

        self.up_button = QPushButton("↑", self)
        self.down_button = QPushButton("↓", self)
        for button in (self.up_button, self.down_button):
            button.setFixedSize(style.SETTINGS_ARROW_SIZE, style.SETTINGS_ARROW_SIZE)
            button.setCursor(Qt.PointingHandCursor)
            button.setStyleSheet(style.settings_arrow_stylesheet())
        self.up_button.setEnabled(not is_first)
        self.down_button.setEnabled(not is_last)
        self.up_button.clicked.connect(lambda: card.moveRow(self, -1))
        self.down_button.clicked.connect(lambda: card.moveRow(self, 1))

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(self.label_field, 1)
        row.addWidget(self.action_combo)
        row.addWidget(self.up_button)
        row.addWidget(self.down_button)

    def setAssignedId(self, action_id):
        self.assigned_id = action_id
        self.action_combo.blockSignals(True)
        self.action_combo.setCurrentIndex(self.action_combo.findData(action_id))
        self.action_combo.blockSignals(False)

    def entry(self):
        return {"id": self.assigned_id, "label": self.label_field.text().strip() or "Untitled"}


class SettingsCard(QWidget):
    def __init__(self, on_change):
        super().__init__(None)  # top-level: outlives the ring, persists for the app's life
        self.on_change = on_change
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.StrongFocus)

        self.drag = WindowDrag(self)
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save)
        shadow.apply(self)

        self.resize(style.SETTINGS_WIDTH + 2 * margin(), style.SETTINGS_HEIGHT + 2 * margin())
        self.buildContent()

    def open(self):
        """Lands near wherever the wedge was picked - like the ring itself
        always opening at the cursor, not wherever the card happened to be
        left after a previous drag or a previous session."""
        self.moveNear(QCursor.pos())
        self.show()
        self.raise_()

    def moveNear(self, cursor_pos):
        area = screenBounds.available_area(cursor_pos, margin=style.CARD_EDGE_MARGIN)
        x = cursor_pos.x() + style.CARD_SPAWN_OFFSET - margin()
        y = cursor_pos.y() + style.CARD_SPAWN_OFFSET - margin()
        x = screenBounds.clamp(x, area.x(), area.x() + area.width() - self.width())
        y = screenBounds.clamp(y, area.y(), area.y() + area.height() - self.height())
        self.move(x, y)

    def buildContent(self):
        self.header_label = QLabel("SETTINGS", self)
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

        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(style.SETTINGS_ROW_GAP)
        self.rows = []
        self.rebuildRows(wedgeConfig.load_other_wedges())

        root = QVBoxLayout(self)
        root.setContentsMargins(*[style.CHAT_PADDING + margin()] * 4)
        root.setSpacing(10)
        root.addLayout(header)
        root.addLayout(self.rows_layout)
        root.addStretch(1)

    def rebuildRows(self, entries):
        while self.rows_layout.count():
            self.rows_layout.takeAt(0).widget().deleteLater()
        self.rows = [
            SettingsRow(self, entry, index == 0, index == len(entries) - 1)
            for index, entry in enumerate(entries)
        ]
        for row in self.rows:
            self.rows_layout.addWidget(row)

    def currentEntries(self):
        return [row.entry() for row in self.rows]

    def moveRow(self, row, direction):
        entries = self.currentEntries()
        index = self.rows.index(row)
        target = index + direction
        entries[index], entries[target] = entries[target], entries[index]
        self.rebuildRows(entries)
        self.save()

    def onActionChanged(self, changed_row):
        """A 3-item list has no "unassigned" slot, so picking an action
        already claimed by another row swaps the two rather than leaving
        both silently pointing at the same action."""
        new_id = changed_row.action_combo.currentData()
        old_id = changed_row.assigned_id
        if new_id == old_id:
            return
        collision = next((row for row in self.rows if row is not changed_row and row.assigned_id == new_id), None)
        changed_row.assigned_id = new_id
        if collision is not None:
            collision.setAssignedId(old_id)
        self.save()

    # --- persistence ---

    def scheduleSave(self):
        self.save_timer.start(style.CARD_AUTOSAVE_MS)

    def save(self):
        self.save_timer.stop()
        entries = self.currentEntries()
        wedgeConfig.save_other_wedges(entries)
        if self.on_change is not None:
            self.on_change(entries)

    def hideEvent(self, event):
        self.save_timer.stop()
        self.save()
        super().hideEvent(event)

    # --- input ---

    def eventFilter(self, watched, event):
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
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
        painter.setBrush(QColor(style.CHAT_SURFACE))
        painter.setPen(QPen(QColor(style.CHAT_BORDER), 1))
        painter.drawRoundedRect(frame, style.CHAT_RADIUS, style.CHAT_RADIUS)
