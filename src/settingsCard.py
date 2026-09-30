# Settings (wedge always pinned near the bottom of the ring, per
# wedgeConfig.full_config) - four tabs: Wedges (relabel, reorder, or reassign
# the ring's other wedges), Look, Chat and Connect. Same toggled-square shape
# as note/todo (see noteCard.py): built lazily on first pick, then just
# shown/hidden.

from PySide6.QtWidgets import (
    QFileDialog, QWidget, QLabel, QLineEdit, QPushButton, QSlider, QStackedWidget, QButtonGroup, QVBoxLayout, QHBoxLayout,
)
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QCursor
from PySide6.QtCore import Qt, QRectF, QTimer, QEvent

import style
import shadow
import screenBounds
import timetable
import wedgeConfig
import autostart
import vaultIndex
from draggable import WindowDrag
from floatingCard import paint_card_bands
from ringPreview import RingPreview
from settingsWidgets import Toggle, Segmented, SettingRow, ghost_button, status_line
from util import reduce_motion_setting, save_reduce_motion_setting

WEDGE_NAMES = dict(wedgeConfig.ACTION_CHOICES)


def margin():
    return style.CARD_SHADOW_MARGIN  # extra window room around the visible face, for the shadow


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

        self.stack = QStackedWidget(self)
        self.stack.setFixedHeight(style.SETTINGS_BODY_HEIGHT)
        pages = [
            ("WEDGES", self.buildWedgesPage()),
            ("LOOK", self.buildLookPage()),
            ("CONNECT", self.buildConnectPage()),
        ]
        self.tabs = QButtonGroup(self)
        tab_row = QHBoxLayout()
        tab_row.setSpacing(style.SPACE_1)
        for index, (name, page) in enumerate(pages):
            tab = QPushButton(name, self)
            tab.setCheckable(True)
            tab.setChecked(index == 0)
            tab.setFixedHeight(style.SETTINGS_TAB_HEIGHT)
            tab.setCursor(Qt.PointingHandCursor)
            tab.setStyleSheet(style.settings_tab_stylesheet())
            self.tabs.addButton(tab, index)
            tab_row.addWidget(tab)
            self.stack.addWidget(page)
        tab_row.addStretch(1)
        self.tabs.idClicked.connect(self.stack.setCurrentIndex)

        root = QVBoxLayout(self)
        root.setContentsMargins(*[style.CHAT_PADDING + margin()] * 4)
        root.setSpacing(10)
        root.addLayout(header)
        root.addLayout(tab_row)
        root.addWidget(self.stack)
        root.addStretch(1)

    def newPage(self):
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(style.SPACE_3, style.SPACE_2, style.SPACE_3, style.SPACE_2)
        layout.setSpacing(0)
        return page, layout

    def buildWedgesPage(self):
        page, layout = self.newPage()
        self.entries = [{"id": entry["id"], "label": WEDGE_NAMES[entry["id"]]} for entry in wedgeConfig.load_other_wedges()]
        self.ring_preview = RingPreview(self)
        self.ring_preview.setConfig(wedgeConfig.full_config(self.entries))
        self.ring_preview.moved.connect(self.moveWedge)
        hint = QLabel("Click a wedge, then click where it should go. Or drag it there.", self)
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)
        hint.setStyleSheet(style.settings_desc_stylesheet())
        layout.addSpacing(style.SPACE_4)
        layout.addWidget(self.ring_preview, 0, Qt.AlignHCenter)
        layout.addSpacing(style.SPACE_3)
        layout.addWidget(hint)
        layout.addStretch(1)
        return page

    def buildLookPage(self):
        page, layout = self.newPage()
        layout.addWidget(SettingRow(self, "Accent", "Ring hover, links, slider and checks", self.buildAccentControl()))
        layout.addWidget(SettingRow(self, "Chat card size", "Applies the next time the chat opens", self.buildSizeControl()))
        self.motion_toggle = Toggle(self, reduce_motion_setting())
        self.motion_toggle.toggled.connect(save_reduce_motion_setting)
        layout.addWidget(SettingRow(self, "Reduce motion", "Skip the ring and card animations; an open chat updates next time", self.motion_toggle))
        self.startup_toggle = Toggle(self, autostart.isEnabled())
        self.startup_toggle.toggled.connect(autostart.setEnabled)
        layout.addWidget(SettingRow(self, "Start with Windows", "Runs quietly in the tray", self.startup_toggle))
        layout.addStretch(1)
        return page

    def buildConnectPage(self):
        page, layout = self.newPage()

        self.link_saved = timetable.saved_link()
        self.link_field = QLineEdit(self.link_saved, self)
        self.link_field.setEchoMode(QLineEdit.Password)  # anyone with the link can read the calendar
        self.link_field.setPlaceholderText("iCal link (optional)")
        self.link_field.setFixedHeight(style.SETTINGS_INPUT_HEIGHT)
        self.link_field.setStyleSheet(style.settings_field_stylesheet())
        self.link_field.textChanged.connect(self.scheduleSave)
        self.link_field.textChanged.connect(self.updateCalendarStatus)
        self.link_field.installEventFilter(self)  # Escape closes the card, not just the field
        calendar_row = SettingRow(self, "Calendar", stacked=True)
        calendar_row.addControl(self.link_field)
        status, self.calendar_status, self.calendar_dot = status_line(self, "", False)
        calendar_row.addControl(status)
        layout.addWidget(calendar_row)
        self.updateCalendarStatus()

        self.vault_field = QLineEdit(str(vaultIndex.VAULT_PATH or ""), self)
        self.vault_field.setPlaceholderText("No vault chosen")
        self.vault_field.setReadOnly(True)  # changed only through Browse, so it is always a real folder
        self.vault_field.setFixedHeight(style.SETTINGS_INPUT_HEIGHT)
        self.vault_field.setStyleSheet(style.settings_field_stylesheet())
        self.vault_field.installEventFilter(self)
        vault_row = SettingRow(self, "Vault folder", stacked=True)
        vault_row.addControl(self.fieldWithButton(self.vault_field, "BROWSE", self.browseVault))
        vault_status, self.vault_status, self.vault_dot = status_line(self, "", False)
        vault_row.addControl(vault_status)
        layout.addWidget(vault_row)
        self.updateVaultStatus()

        ocr = Segmented(self, ["Korean", "English", "Both"], "Korean", disabled=("English", "Both"))
        layout.addWidget(SettingRow(self, "Screen reading language", "Only Korean for now", ocr))
        layout.addWidget(SettingRow(self, "Claude", "sonnet, through your Claude CLI login"))
        layout.addStretch(1)

        note = QLabel("Every field here is optional. Bel works without a calendar or a vault; those features just stay quiet.", self)
        note.setWordWrap(True)
        note.setStyleSheet(style.settings_desc_stylesheet())
        layout.addWidget(note)
        return page

    def fieldWithButton(self, field, button_text, on_click):
        row = QHBoxLayout()
        row.setSpacing(style.SPACE_2)
        row.addWidget(field, 1)
        button = ghost_button(self, button_text)
        button.clicked.connect(on_click)
        row.addWidget(button)
        return row

    def browseVault(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose your vault folder", str(vaultIndex.VAULT_PATH or ""))
        if not folder:
            return
        try:
            vaultIndex.save_vault_path(folder)
        except ValueError:
            self.setVaultStatus("Can't use a Private folder", False)
            return
        self.vault_field.setText(str(vaultIndex.VAULT_PATH))
        self.updateVaultStatus()

    def updateVaultStatus(self):
        if vaultIndex.VAULT_PATH is None:
            self.setVaultStatus("No vault; ? lookups and ! save stay quiet", False)
            return
        found = vaultIndex.VAULT_PATH.exists()
        self.setVaultStatus("Folder found" if found else "Folder not found", found)

    def setVaultStatus(self, text, ok):
        self.vault_status.setText(text)
        color = style.STATUS_OK if ok else style.CHAT_INERT_HINT
        self.vault_dot.setStyleSheet(f"background: {color}; border-radius: 3px;")

    def updateCalendarStatus(self):
        has_link = bool(self.link_field.text().strip())
        self.calendar_status.setText("Link saved" if has_link else "No link yet; ! today and ! week stay quiet")
        color = style.STATUS_OK if has_link else style.CHAT_INERT_HINT
        self.calendar_dot.setStyleSheet(f"background: {color}; border-radius: 3px;")

    def buildAccentControl(self):
        row = QHBoxLayout()
        row.setSpacing(8)
        self.swatches = {}
        for name, (color, _) in style.ACCENT_CHOICES.items():
            swatch = QPushButton(self)
            swatch.setFixedSize(style.SETTINGS_SWATCH_SIZE, style.SETTINGS_SWATCH_SIZE)
            swatch.setCursor(Qt.PointingHandCursor)
            swatch.setToolTip(name)
            swatch.clicked.connect(lambda checked=False, name=name: self.onAccentPicked(name))
            self.swatches[name] = swatch
            row.addWidget(swatch)
        self.styleSwatches()
        return row

    def buildSizeControl(self):
        """Chat card size. Applies to the next chat card opened; one already
        open keeps the size it opened with."""
        self.size_value = QLabel(self)
        self.size_value.setStyleSheet(style.settings_desc_stylesheet())
        self.size_value.setFixedWidth(style.SETTINGS_ARROW_SIZE + 12)
        self.size_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.size_slider = QSlider(Qt.Horizontal, self)
        self.size_slider.setFixedWidth(style.SETTINGS_SLIDER_WIDTH)
        self.size_slider.setRange(round(style.CHAT_SIZE_SCALE_MIN * 100), round(style.CHAT_SIZE_SCALE_MAX * 100))
        self.size_slider.setStyleSheet(style.settings_slider_stylesheet())
        self.size_slider.setValue(round(style.CHAT_SIZE_SCALE * 100))
        self.size_slider.valueChanged.connect(self.onSizeChanged)
        self.size_slider.installEventFilter(self)  # Escape closes the card, not just the slider
        self.size_value.setText(f"{self.size_slider.value()}%")

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.size_slider)
        row.addWidget(self.size_value)
        return row

    def styleSwatches(self):
        for name, swatch in self.swatches.items():
            swatch.setStyleSheet(style.settings_swatch_stylesheet(style.ACCENT_CHOICES[name][0], name == style.accent_name))

    def onAccentPicked(self, name):
        style.save_accent(name)
        self.styleSwatches()
        self.size_slider.setStyleSheet(style.settings_slider_stylesheet())
        for tab in self.tabs.buttons():
            tab.setStyleSheet(style.settings_tab_stylesheet())
        for toggle in (self.motion_toggle, self.startup_toggle):
            toggle.update()

    def onSizeChanged(self, percent):
        self.size_value.setText(f"{percent}%")
        style.save_chat_size_scale(percent / 100)

    def moveWedge(self, wedge_id, target):
        """Takes the wedge out of its place and puts it at `target` (0 is first), the rest shifting to make room."""
        index = next(i for i, entry in enumerate(self.entries) if entry["id"] == wedge_id)
        if target == index:
            return
        self.entries.insert(target, self.entries.pop(index))
        self.ring_preview.setConfig(wedgeConfig.full_config(self.entries))
        self.save()

    # --- persistence ---

    def scheduleSave(self):
        self.save_timer.start(style.CARD_AUTOSAVE_MS)

    def save(self):
        self.save_timer.stop()
        entries = [dict(entry) for entry in self.entries]
        wedgeConfig.save_other_wedges(entries)
        link = self.link_field.text().strip()
        if link != self.link_saved:
            timetable.save_link(link)
            self.link_saved = link
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
        body_top = self.stack.y()
        paint_card_bands(painter, frame, style.CHAT_RADIUS, style.CARD_BODY, body_top, body_top)
        painter.setPen(QPen(QColor(style.CHAT_BORDER), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(frame, style.CHAT_RADIUS, style.CHAT_RADIUS)
