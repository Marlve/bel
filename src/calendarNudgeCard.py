# The nudge card itself, per calendar-nudge.md: a quiet rail at a screen
# edge that slides out with a one-sentence summary once the startup
# calendar query (calendarNudge.py) finds something upcoming, expands on
# hover to show the actual items, and always collapses back to the same
# rail - there's no accept flow, so nothing else to do with it.

from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtCore import Qt, QRectF

import style
import calendarNudgeCopy
from calendarNudgeAnimation import CalendarNudgeDriver
from calendarNudgeState import QUIET, EXPANDED


class CalendarNudgeCard(QWidget):
    def __init__(self, motion=True):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMouseTracking(True)

        self.driver = CalendarNudgeDriver(self, self.geometryFor, self.onMoved, self.onStateChanged, motion=motion)
        self.onMoved(self.driver.current_rect)
        self.show()

    def showNudge(self, items, before):
        sentence = calendarNudgeCopy.sentence(len(items), before)
        source = calendarNudgeCopy.source_line(len(items))
        self.driver.show(items, sentence, source)

    # --- placement: anchored to the top-right of the primary screen's work
    # area, growing leftward out of a fixed right edge so the rail and the
    # slid-out card always share that same edge. ---

    def geometryFor(self, state):
        area = QApplication.primaryScreen().availableGeometry()
        top = area.y() + style.CHAT_MARGIN
        right = area.x() + area.width() - style.CHAT_MARGIN
        if state == QUIET:
            width, height = style.NUDGE_RAIL_SIZE, style.NUDGE_HEIGHT
        elif state == EXPANDED:
            width = style.NUDGE_WIDTH
            height = style.NUDGE_HEIGHT + len(self.driver.state.items) * style.NUDGE_ITEM_ROW_HEIGHT
        else:
            width, height = style.NUDGE_WIDTH, style.NUDGE_HEIGHT
        return QRectF(right - width, top, width, height)

    def onMoved(self, rect):
        self.setGeometry(rect.toRect())

    def onStateChanged(self, state):
        self.update()

    # --- input: hover expands it, a click dismisses it - the card stays on
    # screen otherwise, per calendar-nudge.md's "no accept flow" ---

    def enterEvent(self, event):
        self.driver.hover()
        super().enterEvent(event)

    def mousePressEvent(self, event):
        self.driver.dismiss()

    # --- painting ---

    def paintEvent(self, event):
        state = self.driver.state.state
        if state == QUIET:
            return  # "nothing visible", per calendar-nudge.md

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        frame = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setBrush(QColor(style.NUDGE_BODY))
        painter.setPen(QPen(QColor(style.NUDGE_BORDER), 1))
        painter.drawRoundedRect(frame, style.CHAT_RADIUS, style.CHAT_RADIUS)

        pad = style.SPACE_2
        content_width = frame.width() - 2 * pad

        font = QFont(style.FONT_FAMILY)
        font.setPointSizeF(style.FONT_SIZE)  # FONT_SIZE scales with style.apply_scale(), unlike a size-less QFont
        painter.setFont(font)
        sentence_rect = QRectF(frame.left() + pad, frame.top() + pad, content_width, 18)
        painter.setPen(QColor(style.NUDGE_TEXT))
        painter.drawText(sentence_rect, Qt.TextWordWrap, self.driver.state.sentence)

        source_rect = QRectF(frame.left() + pad, sentence_rect.bottom() + style.SPACE_1, content_width, 16)
        painter.setPen(QColor(style.NUDGE_TEXT_SECONDARY))
        painter.drawText(source_rect, Qt.AlignLeft, self.driver.state.source)

        if state == EXPANDED:
            self.paintItems(painter, frame, source_rect.bottom() + style.SPACE_2, pad, content_width)

    def paintItems(self, painter, frame, y, pad, content_width):
        for item in self.driver.state.items:
            row = QRectF(frame.left() + pad, y, content_width, style.NUDGE_ITEM_ROW_HEIGHT)
            painter.setPen(QColor(style.NUDGE_TEXT))
            painter.drawText(row, Qt.AlignLeft | Qt.AlignVCenter, item.get("title", ""))
            painter.setPen(QColor(style.NUDGE_TEXT_MUTED))
            painter.drawText(row, Qt.AlignRight | Qt.AlignVCenter, item.get("due", ""))
            y += style.NUDGE_ITEM_ROW_HEIGHT
