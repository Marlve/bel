# Settings' picture of the pie menu: the wedges as they will sit in the ring,
# to click or drag into a new order. The Settings wedge is drawn but stays
# where it is - wedgeConfig pins it near the bottom.

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtCore import Qt, QRectF, QPointF, Signal

import style
from anims import pose
from ringGeometry import ring_segment, wedge_index

SETTINGS_ID = "settings"


class RingPreview(QWidget):
    """Click a wedge to pick it up, then click where it should go; or drag it
    there. Either way `moved` says which wedge and which place among the
    movable ones (0 is first)."""

    moved = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(style.RING_PREVIEW_SIZE, style.RING_PREVIEW_SIZE)
        self.setMouseTracking(True)
        self.config = []
        self.selected = None  # id of the wedge picked up by a click
        self.hovered = None  # index into config
        self.pressed = None

    def setConfig(self, config):
        self.config = config
        self.selected = None
        self.update()

    def radius(self):
        return self.width() / 2 - 4

    def indexAt(self, position):
        center = QPointF(self.width() / 2, self.height() / 2)
        return wedge_index(
            position.x() - center.x(), position.y() - center.y(), len(self.config),
            deadzone=style.RING_INNER * self.radius(), radius=self.radius(),
        )

    def movable(self, index):
        return index is not None and self.config[index]["id"] != SETTINGS_ID

    def place(self, index):
        """Where wedge `index` sits among the movable ones, with Settings left out."""
        return [entry["id"] for entry in self.config if entry["id"] != SETTINGS_ID].index(self.config[index]["id"])

    def mouseMoveEvent(self, event):
        index = self.indexAt(event.position())
        if index != self.hovered:
            self.hovered = index
            self.setCursor(Qt.PointingHandCursor if self.movable(index) else Qt.ArrowCursor)
            self.update()

    def leaveEvent(self, event):
        self.hovered = None
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.pressed = self.indexAt(event.position())

    def mouseReleaseEvent(self, event):
        source, self.pressed = self.pressed, None
        if event.button() != Qt.LeftButton or not self.movable(source):
            return
        target = self.indexAt(event.position())
        if target is None:
            return
        source_id = self.config[source]["id"]
        if target != source:
            if self.movable(target):  # a drag, from the pressed wedge onto another
                self.moved.emit(source_id, self.place(target))
            return
        if self.selected is None:
            self.selected = source_id
        elif self.selected == source_id:
            self.selected = None
        else:  # a click on a second wedge while one is picked up: put the picked one there
            self.moved.emit(self.selected, self.place(target))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        count = len(self.config)
        if not count:
            return
        outer = self.radius()
        inner = style.RING_INNER * outer
        span = 360 / count

        font = QFont(style.FONT_FAMILY)
        font.setPixelSize(round(style.CHAT_BODY_SIZE))
        painter.setFont(font)

        for index, entry in enumerate(self.config):
            movable = entry["id"] != SETTINGS_ID
            picked = entry["id"] == self.selected
            if picked:
                fill = QColor(style.ACCENT)
            elif movable and index == self.hovered:
                fill = QColor(style.SURFACE_RAISED)
            else:
                fill = QColor(style.WEDGE_IDLE)
            painter.setPen(QPen(QColor(style.WEDGE_BORDER), 1))
            painter.setBrush(fill)
            painter.drawPath(ring_segment(outer, inner, 90 - index * span - span / 2, span))

            bx, by = pose.bisector(index, count)
            label_r = style.RING_LABEL * outer
            painter.setPen(QColor(style.INK if picked else style.BODY_DIM if movable else style.HINT))
            painter.drawText(QRectF(bx * label_r - 40, by * label_r - 12, 80, 24), Qt.AlignCenter, entry["label"])
