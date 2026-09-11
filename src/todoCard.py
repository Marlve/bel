# Todo square (wedge 0), per design.md's "Todo square" section - simplified:
# a single toggled instance (not the modifier-key multi-spawn design.md gives
# the note), and using the app's shared neutral palette (style.CHAT_*)
# instead of the design doc's own blue, per the same redesign that already
# moved the ring and prompt bar onto that palette.
#
# design.md leaves open how a new item actually gets typed in - there's no
# add affordance in its spec. This adds one: a small field pinned at the
# bottom, always present, the same way the chat card's composer always is.

from PySide6.QtWidgets import QWidget, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QHBoxLayout, QApplication
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics, QCursor
from PySide6.QtCore import Qt, QRectF, QTimer, QEvent

import style
import shadow
import cardStore
from anims.clock import Tween
from anims import curves
from draggable import WindowDrag, ResizeGrip
from util import reduced_motion

STORE_KEY = "todo"
MARGIN = style.CARD_SHADOW_MARGIN  # extra window room around the visible face, for the shadow


class TodoList(QWidget):
    """Custom-painted rows, one widget rather than one child per row - so a
    single press can resolve to either a tick or the start of a window drag
    (design.md: "press and move more than 4 px and it drags; under 4 px on a
    row it ticks") without the two gestures fighting over which widget owns
    the press."""

    def __init__(self, card):
        super().__init__(card)
        self.card = card
        self.items = []  # [{"text": ..., "done": bool}, ...]
        self.press_row = None
        self.remove_timers = {}  # id(item) -> QTimer, ticked rows waiting to auto-remove
        self.remove_fade = {}  # id(item) -> current fade-out alpha, for a row mid-removal
        self.fade_tweens = {}  # id(item) -> its Tween, kept alive while fading

    def setItems(self, items):
        self.items = items
        self.updateHeight()
        self.update()

    def updateHeight(self):
        self.setFixedHeight(max(len(self.items), 1) * style.TODO_ROW_HEIGHT)

    def rowAt(self, y):
        index = int(y // style.TODO_ROW_HEIGHT)
        return index if 0 <= index < len(self.items) else None

    def toggle(self, index):
        item = self.items[index]
        item["done"] = not item["done"]
        self.update()
        self.card.scheduleSave()
        if item["done"]:
            self.scheduleRemoval(item)
        else:
            self.cancelRemoval(item)

    def scheduleRemoval(self, item):
        """A ticked row is live for a beat in case the tick was a mistake -
        only once it's sat done for TODO_REMOVE_DELAY_MS untouched does it
        actually go. Keyed by the item's identity, not its content, so two
        rows with identical text/done never get their timers mixed up."""
        self.cancelRemoval(item)
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self.removeIfStillDone(item))
        timer.start(style.TODO_REMOVE_DELAY_MS)
        self.remove_timers[id(item)] = timer

    def cancelRemoval(self, item):
        timer = self.remove_timers.pop(id(item), None)
        if timer is not None:
            timer.stop()

    def removeIfStillDone(self, item):
        self.remove_timers.pop(id(item), None)
        if not item["done"]:
            return  # unticked before the timer fired
        if not getattr(self.card, "motion", False):
            self.finishRemoval(item)
            return
        self.remove_fade[id(item)] = 1.0
        tween = Tween(
            self, lambda v, item=item: self.onItemFadeTick(item, v), lambda item=item: self.onItemFadeDone(item)
        )
        self.fade_tweens[id(item)] = tween
        tween.run(1.0, 0.0, style.TODO_ITEM_FADE_MS, curves.CHAT_FLIGHT)

    def onItemFadeTick(self, item, value):
        self.remove_fade[id(item)] = value
        self.update()

    def onItemFadeDone(self, item):
        self.fade_tweens.pop(id(item), None)
        self.remove_fade.pop(id(item), None)
        if not item["done"]:
            return  # unticked mid-fade - stay put
        self.finishRemoval(item)

    def finishRemoval(self, item):
        for index, existing in enumerate(self.items):
            if existing is item:
                del self.items[index]
                break
        else:
            return
        self.updateHeight()
        self.update()
        self.card.scheduleSave()

    def mousePressEvent(self, event):
        self.card.drag.press(event.globalPosition())
        self.press_row = self.rowAt(event.position().y())

    def mouseMoveEvent(self, event):
        self.card.drag.move(event.globalPosition())

    def mouseReleaseEvent(self, event):
        dragged = self.card.drag.release()
        if not dragged and self.press_row is not None:
            self.toggle(self.press_row)
        self.press_row = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        for index, item in enumerate(self.items):
            self.paintRow(painter, index, item)

    def paintRow(self, painter, index, item):
        top = index * style.TODO_ROW_HEIGHT
        box = QRectF(
            0, top + (style.TODO_ROW_HEIGHT - style.TODO_CHECKBOX) / 2, style.TODO_CHECKBOX, style.TODO_CHECKBOX
        )

        painter.save()
        fade = self.remove_fade.get(id(item), 1.0)
        painter.setOpacity(fade * 0.4 if item["done"] else fade)

        painter.setPen(QPen(QColor(style.CHAT_LABEL_MONO), 1.5))
        painter.setBrush(QColor(style.CHAT_ACCENT) if item["done"] else Qt.NoBrush)
        painter.drawRoundedRect(box, style.TODO_CHECKBOX_RADIUS, style.TODO_CHECKBOX_RADIUS)

        font = painter.font()
        font.setStrikeOut(item["done"])
        painter.setFont(font)
        painter.setPen(QColor(style.CHAT_BODY_TEXT))
        label_rect = QRectF(box.right() + 10, top, self.width() - box.right() - 10, style.TODO_ROW_HEIGHT)
        metrics = QFontMetrics(font)
        elided = metrics.elidedText(item["text"], Qt.ElideRight, int(label_rect.width()))
        painter.drawText(label_rect, Qt.AlignVCenter | Qt.AlignLeft, elided)
        painter.restore()


class TodoCard(QWidget):
    def __init__(self):
        super().__init__(None)  # top-level: outlives the ring, persists for the app's life
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(style.CARD_MIN_WIDTH + 2 * MARGIN, style.CARD_MIN_HEIGHT + 2 * MARGIN)

        self.drag = WindowDrag(self)
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save)
        self.motion = not reduced_motion()
        self.fade = Tween(self, self.onFadeTick)
        shadow.apply(self)

        saved = cardStore.load(STORE_KEY, {})
        face_w, face_h = saved.get("size", [style.CHAT_SIZE, style.CHAT_SIZE])
        self.resize(face_w + 2 * MARGIN, face_h + 2 * MARGIN)

        self.buildContent()
        self.list.setItems(saved.get("items", []))
        self.grip.reposition()

    def open(self):
        """Lands near wherever the wedge was picked - like the ring itself
        always opening at the cursor, not wherever the card happened to be
        left after a previous drag or a previous session."""
        self.moveNear(QCursor.pos())
        self.setWindowOpacity(0 if self.motion else 1)
        self.show()
        self.raise_()
        if self.motion:
            self.fade.run(0.0, 1.0, style.CARD_OPEN_MS, curves.CHAT_FLIGHT)

    def onFadeTick(self, value):
        self.setWindowOpacity(value)

    def moveNear(self, cursor_pos):
        screen = QApplication.screenAt(cursor_pos) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        x = cursor_pos.x() + style.CARD_SPAWN_OFFSET - MARGIN
        y = cursor_pos.y() + style.CARD_SPAWN_OFFSET - MARGIN
        x = max(area.x(), min(x, area.x() + area.width() - self.width()))
        y = max(area.y(), min(y, area.y() + area.height() - self.height()))
        self.move(x, y)

    def buildContent(self):
        self.header_label = QLabel("TODO", self)
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

        self.list = TodoList(self)
        self.scroll = QScrollArea(self)
        self.scroll.setWidget(self.list)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setStyleSheet(style.chat_scrollbar_stylesheet())

        self.add_field = QLineEdit(self)
        self.add_field.setPlaceholderText("Add a to-do…")
        self.add_field.setFixedHeight(style.CHAT_COMPOSER_HEIGHT)
        self.add_field.setStyleSheet(style.chat_composer_stylesheet(False))
        self.add_field.textChanged.connect(self.onAddTextChanged)
        self.add_field.returnPressed.connect(self.addItem)
        self.add_field.installEventFilter(self)  # Escape closes the card, not just the field

        root = QVBoxLayout(self)
        root.setContentsMargins(*[style.CHAT_PADDING + MARGIN] * 4)
        root.setSpacing(10)
        root.addLayout(header)
        root.addWidget(self.scroll, 1)
        root.addWidget(self.add_field)

        self.grip = ResizeGrip(self)

    def onAddTextChanged(self, text):
        self.add_field.setStyleSheet(style.chat_composer_stylesheet(bool(text.strip())))

    def addItem(self):
        text = self.add_field.text().strip()
        if not text:
            return
        self.list.items.append({"text": text, "done": False})
        self.list.updateHeight()
        self.list.update()
        self.add_field.clear()
        self.scheduleSave()

    # --- persistence ---

    def scheduleSave(self):
        self.save_timer.start(style.CARD_AUTOSAVE_MS)

    def save(self):
        cardStore.save(
            STORE_KEY,
            {"items": self.list.items, "size": [self.width() - 2 * MARGIN, self.height() - 2 * MARGIN]},
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
        if watched is self.add_field and event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
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
        border = style.CARD_BORDER_DRAG if hasattr(self, "grip") and self.grip.dragging else style.CHAT_BORDER
        painter.setPen(QPen(QColor(border), 1))
        painter.drawRoundedRect(frame, style.CHAT_RADIUS, style.CHAT_RADIUS)
