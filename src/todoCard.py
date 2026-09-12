# Todo square (wedge 0), per design.md's "Todo square" section - simplified:
# a single toggled instance (not the modifier-key multi-spawn design.md gives
# the note), and using the app's shared neutral palette (style.CHAT_*)
# instead of the design doc's own blue, per the same redesign that already
# moved the ring and prompt bar onto that palette.
#
# design.md leaves open how a new item actually gets typed in - there's no
# add affordance in its spec. This adds one: a small field pinned at the
# bottom, always present, the same way the chat card's composer always is.

from PySide6.QtWidgets import QWidget, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QHBoxLayout
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics, QPalette
from PySide6.QtCore import Qt, QRectF, QTimer, QEvent

import style
import shadow
import cardStore
from anims.clock import Tween
from draggable import WindowDrag, ResizeGrip
from floatingCard import FloatingCard, paint_card_bands
from todoListAnimation import TodoListAnimation
from util import reduced_motion

STORE_KEY = "todo"


def margin():
    return style.CARD_SHADOW_MARGIN  # extra window room around the visible face, for the shadow


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
        self.animation = TodoListAnimation(self)

    @property
    def remove_timers(self):
        return self.animation.remove_timers

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
        self.card.updateOpenCount()
        if item["done"]:
            self.animation.scheduleRemoval(item)
        else:
            self.animation.cancelRemoval(item)

    def removeIfStillDone(self, item):
        self.animation.removeIfStillDone(item)

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
        pen_width = 1.5
        box = QRectF(
            pen_width / 2,  # flush with the header/add-field's left edge; just enough inset to
            # keep the full stroke onscreen (drawRoundedRect centers the pen on the path) -
            # style.SPACE_2 read as clipping-fixed but sat visibly righter than every other
            # left edge in the card, see card-visual-polish/02's live-check follow-up
            top + (style.TODO_ROW_HEIGHT - style.TODO_CHECKBOX) / 2,
            style.TODO_CHECKBOX,
            style.TODO_CHECKBOX,
        )

        painter.save()
        fade = self.animation.remove_fade.get(id(item), 1.0)
        painter.setOpacity(fade * 0.4 if item["done"] else fade)

        painter.setPen(QPen(QColor(style.CHAT_LABEL_MONO), pen_width))
        painter.setBrush(QColor(style.CHAT_ACCENT) if item["done"] else Qt.NoBrush)
        painter.drawRoundedRect(box, style.TODO_CHECKBOX_RADIUS, style.TODO_CHECKBOX_RADIUS)

        font = painter.font()
        font.setStrikeOut(item["done"])
        painter.setFont(font)
        painter.setPen(QColor(style.CHAT_BODY_TEXT))
        label_rect = QRectF(
            box.right() + style.SPACE_2, top, self.width() - box.right() - style.SPACE_2, style.TODO_ROW_HEIGHT
        )
        metrics = QFontMetrics(font)
        elided = metrics.elidedText(item["text"], Qt.ElideRight, int(label_rect.width()))
        painter.drawText(label_rect, Qt.AlignVCenter | Qt.AlignLeft, elided)
        painter.restore()


class TodoCard(FloatingCard, QWidget):
    def __init__(self):
        super().__init__(None)  # top-level: outlives the ring, persists for the app's life
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(style.CARD_MIN_WIDTH + 2 * margin(), style.CARD_MIN_HEIGHT + 2 * margin())

        self.drag = WindowDrag(self)
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save)
        self.motion = not reduced_motion()
        self.fade = Tween(self, self.onFadeTick)
        shadow.apply(self)

        saved = cardStore.load(STORE_KEY, {})
        face_w, face_h = saved.get("size", [style.TODO_DEFAULT_WIDTH, style.CHAT_SIZE])
        self.resize(face_w + 2 * margin(), face_h + 2 * margin())
        pos = saved.get("pos")
        if pos is not None:
            self.restorePosition(pos)

        self.buildContent()
        self.list.setItems(saved.get("items", []))
        self.updateOpenCount()
        self.grip.reposition()

    def afterRaise(self):
        # WA_ShowWithoutActivating keeps show() from stealing OS focus, so
        # the field's setFocus() alone would be Qt-internal only - actual
        # keystrokes need the window itself activated. Safe to do explicitly
        # here (unlike a passive reveal) since this always follows the ring
        # just having forced OS foreground for this process (util.force_foreground).
        self.activateWindow()
        self.add_field.setFocus()
        self.add_field.end(False)  # caret after any text the field already holds

    def buildContent(self):
        self.header_label = QLabel("Today", self)
        header_font = QFont(style.CHAT_MONO_FAMILY)
        header_font.setPointSizeF(style.CHAT_HEADER_SIZE)
        header_font.setLetterSpacing(QFont.PercentageSpacing, style.CHAT_HEADER_TRACKING_PERCENT)
        self.header_label.setFont(header_font)
        self.header_label.setStyleSheet(f"color: {style.CHAT_LABEL_MONO}; background: transparent;")
        self.header_label.setAttribute(Qt.WA_TransparentForMouseEvents)

        self.header_count_label = QLabel(self)
        self.header_count_label.setFont(header_font)
        self.header_count_label.setStyleSheet(f"color: {style.CHAT_LABEL_MONO}; background: transparent;")
        self.header_count_label.setAttribute(Qt.WA_TransparentForMouseEvents)

        self.close_button = QPushButton("✕", self)
        self.close_button.setFixedSize(18, 18)
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setStyleSheet(style.chat_close_stylesheet())
        self.close_button.clicked.connect(self.hide)

        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(self.header_label)
        header.addStretch(1)
        header.addWidget(self.header_count_label)
        header.addWidget(self.close_button)

        self.list = TodoList(self)
        self.scroll = QScrollArea(self)
        self.scroll.setWidget(self.list)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setStyleSheet(style.chat_scrollbar_stylesheet())

        self.add_field = QLineEdit(self)
        self.add_field.setPlaceholderText("add a task")
        self.add_field.setFixedHeight(style.CHAT_COMPOSER_HEIGHT)
        self.add_field.setFrame(False)  # no native frame metrics stealing space and shifting text off-center
        self.add_field.setStyleSheet(style.plain_field_stylesheet())
        palette = self.add_field.palette()
        palette.setColor(QPalette.PlaceholderText, QColor(style.MUTED))
        self.add_field.setPalette(palette)
        self.add_field.returnPressed.connect(self.addItem)
        self.add_field.installEventFilter(self)  # Escape closes the card, not just the field

        root = QVBoxLayout(self)
        root.setContentsMargins(*[style.CHAT_PADDING + margin()] * 4)
        root.setSpacing(0)
        root.addLayout(header)
        root.addSpacing(style.SPACE_2)
        root.addWidget(self.scroll, 1)
        # Matches the card's own bottom padding, so the add-field sits as far
        # from the list above it as from the card's edge below it - see
        # card-visual-polish/03's live-check follow-up.
        root.addSpacing(style.CHAT_PADDING)
        root.addWidget(self.add_field)

        self.grip = ResizeGrip(self)

    def addItem(self):
        text = self.add_field.text().strip()
        if not text:
            return
        self.list.items.append({"text": text, "done": False})
        self.list.updateHeight()
        self.list.update()
        self.updateOpenCount()
        self.add_field.clear()
        self.scheduleSave()

    def updateOpenCount(self):
        open_count = sum(1 for item in self.list.items if not item["done"])
        self.header_count_label.setText(f"{open_count} OPEN")

    # --- persistence ---

    def scheduleSave(self):
        self.save_timer.start(style.CARD_AUTOSAVE_MS)

    def save(self):
        cardStore.save(
            STORE_KEY,
            {
                "items": self.list.items,
                "size": [self.width() - 2 * margin(), self.height() - 2 * margin()],
                "pos": [self.x(), self.y()],
            },
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
        m = margin()
        frame = QRectF(self.rect()).adjusted(m + 0.5, m + 0.5, -m - 0.5, -m - 0.5)

        # Body and footer share the one dark tone (per floating-card-redesign.md,
        # their reference values are near-identical); only the header bar and the
        # footer's top seam actually differ from it. The seam sits at the
        # scroll area's own bottom edge, not the add-field's top - flush with
        # the field left equal padding above it inside the footer (0px) but
        # not below (CHAT_PADDING), reading as "too high" even though the
        # field's own position was already symmetric relative to the body -
        # see card-visual-polish/03's live-check follow-up.
        footer_seam = self.scroll.y() + self.scroll.height()
        paint_card_bands(painter, frame, style.CHAT_RADIUS, style.CARD_BODY, self.scroll.y(), footer_seam)

        dragging = hasattr(self, "grip") and self.grip.dragging
        painter.setPen(QPen(QColor(style.card_border_color(dragging)), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(frame, style.CHAT_RADIUS, style.CHAT_RADIUS)
