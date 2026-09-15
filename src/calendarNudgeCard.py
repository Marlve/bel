# The nudge card itself, per calendar-nudge.md: a quiet rail at a screen
# edge that slides out with a one-sentence summary once the startup
# calendar query (calendarNudge.py) finds something upcoming, expands on
# hover to show the actual items, and always collapses back to the same
# rail - there's no accept flow, so nothing else to do with it.

from PySide6.QtWidgets import QWidget, QApplication, QPushButton
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QFontMetricsF
from PySide6.QtCore import Qt, QRectF

import style
import calendarNudgeCopy
from calendarNudgeAnimation import CalendarNudgeDriver
from calendarNudgeState import QUIET, EXPANDED


def buildFont():
    font = QFont(style.FONT_FAMILY)
    font.setPointSizeF(style.FONT_SIZE)  # FONT_SIZE scales with style.apply_scale(), unlike a size-less QFont
    return font


def wrappedTextHeight(text, width, font):
    return QFontMetricsF(font).boundingRect(QRectF(0, 0, width, 0), Qt.TextWordWrap, text).height()


def elidedTitle(title, due, content_width, font):
    """Elides an item's title so it never runs into its own right-aligned
    due label - real assignment titles routinely outrun the card's width."""
    fm = QFontMetricsF(font)
    available = max(content_width - fm.horizontalAdvance(due) - style.SPACE_1, 0)
    return fm.elidedText(title, Qt.ElideRight, available)


class CalendarNudgeCard(QWidget):
    def __init__(self, motion=True):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMouseTracking(True)

        self.driver = CalendarNudgeDriver(
            self, self.geometryFor, self.onMoved, self.onStateChanged, motion=motion, on_landed=self.onLanded
        )
        self.retreat_snapshot = None  # (state, items, sentence, source) painted while the dismiss tween is in flight

        self.close_button = QPushButton("✕", self)
        self.close_button.setFixedSize(18, 18)
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setStyleSheet(style.chat_close_stylesheet())
        self.close_button.clicked.connect(self.dismiss)
        self.close_button.hide()  # starts QUIET - onStateChanged reveals it on the next show()

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
        else:
            width = style.NUDGE_WIDTH
            height = self.baseContentHeight()
            if state == EXPANDED:
                # baseContentHeight()'s trailing pad becomes the gap before
                # the item list (it's the same style.SPACE_2), so the items
                # themselves need their own bottom pad added back.
                height += len(self.driver.state.items) * style.NUDGE_ITEM_ROW_HEIGHT + style.SPACE_2
        return QRectF(right - width, top, width, height)

    def baseContentHeight(self):
        """Sentence + source line, sized to the sentence's actual wrapped
        height rather than a fixed guess - a short "before" wraps to one
        line, a long one to two or more, and the window needs to fit
        whichever it turns out to be."""
        pad = style.SPACE_2
        content_width = style.NUDGE_WIDTH - 2 * pad
        font = buildFont()
        sentence_h = wrappedTextHeight(self.driver.state.sentence, content_width, font)
        source_h = QFontMetricsF(font).height()
        return self.contentTopPad() + sentence_h + style.SPACE_1 + source_h + pad

    def contentTopPad(self):
        """Top inset reserved for the close button's row, above the
        sentence - paintEvent's sentence_rect must start at this same
        offset or the button will sit on top of the text."""
        return style.SPACE_2 + self.close_button.height() + style.SPACE_1

    def onMoved(self, rect):
        self.setGeometry(rect.toRect())
        self.positionCloseButton(rect.width())

    def positionCloseButton(self, width):
        pad = style.SPACE_2
        self.close_button.move(int(width - pad - self.close_button.width()), int(pad))

    def onStateChanged(self, state):
        # Positions against the target state's own width rather than
        # whatever self.width() happens to be at this instant - _moveTo()
        # can fire this before the slide's first animation tick lands, and
        # showing the button at the old (narrower) width would misplace it
        # for a frame.
        if state != QUIET:
            self.positionCloseButton(self.geometryFor(state).width())
        self.close_button.setVisible(state != QUIET)
        self.update()

    def onLanded(self):
        """Fires once any geometry tween reaches its target. Only meaningful
        here when that target was QUIET (show/hover's own landings are already
        painting correctly) - that's the retreat tween finishing, so the
        snapshot paintEvent has been drawing from can finally be dropped and
        the card actually goes blank."""
        if self.driver.state.state == QUIET:
            self.retreat_snapshot = None
            self.update()

    # --- input: hover expands it; the close button is the only thing that
    # dismisses it - the card stays on screen otherwise, per
    # calendar-nudge.md's "no accept flow" ---

    def enterEvent(self, event):
        self.driver.hover()
        super().enterEvent(event)

    def mousePressEvent(self, event):
        pass  # body clicks no longer dismiss - only the close button does

    def dismiss(self):
        # Snapshots what's on screen before the state machine clears it, so
        # paintEvent has something to keep drawing while the retreat tween
        # slides the card back to the rail - the same reasoning as the
        # entrance, which paints NUDGE's content the instant show() fires,
        # not once the slide finishes.
        if self.driver.motion and self.driver.state.state != QUIET:
            s = self.driver.state
            self.retreat_snapshot = (s.state, s.items, s.sentence, s.source)
        self.driver.dismiss()

    # --- painting ---

    def paintEvent(self, event):
        state = self.driver.state.state
        if state == QUIET:
            if self.retreat_snapshot is None:
                return  # "nothing visible", per calendar-nudge.md
            state, items, sentence, source = self.retreat_snapshot
        else:
            s = self.driver.state
            items, sentence, source = s.items, s.sentence, s.source

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        frame = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setBrush(QColor(style.NUDGE_BODY))
        painter.setPen(QPen(QColor(style.NUDGE_BORDER), 1))
        painter.drawRoundedRect(frame, style.CHAT_RADIUS, style.CHAT_RADIUS)

        pad = style.SPACE_2
        content_width = frame.width() - 2 * pad

        font = buildFont()
        painter.setFont(font)
        fm = QFontMetricsF(font)

        sentence_h = wrappedTextHeight(sentence, content_width, font)
        sentence_rect = QRectF(frame.left() + pad, frame.top() + self.contentTopPad(), content_width, sentence_h)
        painter.setPen(QColor(style.NUDGE_TEXT))
        painter.drawText(sentence_rect, Qt.TextWordWrap, sentence)

        source_rect = QRectF(frame.left() + pad, sentence_rect.bottom() + style.SPACE_1, content_width, fm.height())
        painter.setPen(QColor(style.NUDGE_TEXT_SECONDARY))
        painter.drawText(source_rect, Qt.AlignLeft, fm.elidedText(source, Qt.ElideRight, content_width))

        if state == EXPANDED:
            self.paintItems(painter, frame, source_rect.bottom() + style.SPACE_2, pad, content_width, font, items)

    def paintItems(self, painter, frame, y, pad, content_width, font, items):
        for item in items:
            row = QRectF(frame.left() + pad, y, content_width, style.NUDGE_ITEM_ROW_HEIGHT)
            due = item.get("due", "")
            title = elidedTitle(item.get("title", ""), due, content_width, font)
            painter.setPen(QColor(style.NUDGE_TEXT))
            painter.drawText(row, Qt.AlignLeft | Qt.AlignVCenter, title)
            painter.setPen(QColor(style.NUDGE_TEXT_MUTED))
            painter.drawText(row, Qt.AlignRight | Qt.AlignVCenter, due)
            y += style.NUDGE_ITEM_ROW_HEIGHT
