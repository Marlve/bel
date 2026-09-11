# Concept for ADR-0006: hotkey opens a ring around the cursor, split into
# wedges; moving the mouse toward one highlights it, clicking runs that
# wedge's action. A wedge whose action needs typed input hands off to the
# prompt bar instead of firing straight away.

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPainter, QColor, QCursor, QPainterPath, QPen, QRadialGradient
from PySide6.QtCore import Qt, QPointF, QRectF

import style
from anims import pose
from overlay import OverlayWindow
from promptFlow import PromptFlow
from claudeChatCard import ChatSlot
from pieMenuState import (
    PieMenuState,
    wedge_index,
    compass_wedge,
    INNER_RADIUS,
    HIT_RADIUS,
    HIDDEN,
    OPENING,
    OPEN,
    SELECTING,
    HANDOFF,
    PROMPTING,
    CLOSING,
)
from pieMenuAnimation import PieMenuAnimation
from util import force_foreground

# Furthest a wedge's ink can land from the anchor: grown by hover, pushed out
# by hover and select together, plus half the glow's stroke, all at the peak
# scale the open overshoot and select reach. Sizes dirty rects only - how far
# out the cursor still counts as pointing at a wedge is HIT_RADIUS, a
# separate question with a separate answer.
OPEN_PEAK_SCALE = max(pose.open_pose(ms)[0] for ms in range(style.OPEN_MS + 1))
PAINT_REACH = (
    (style.HOVER_GROW + style.HOVER_PUSH + style.SELECT_PUSH) * style.RING_RADIUS + style.GLOW_WIDTH / 2
) * OPEN_PEAK_SCALE * style.SELECT_SCALE

ARROW_ANGLE_BY_KEY = {Qt.Key_Up: 0, Qt.Key_Right: 90, Qt.Key_Down: 180, Qt.Key_Left: 270}
ACTIVATE_WIDGET_KEYS = (Qt.Key_Return, Qt.Key_Enter)


def ring_segment(outer, inner, start_angle, span):
    """Annular sector centered on the origin. Angles are Qt's: degrees,
    0 = right, growing counter-clockwise."""
    outer_rect = QRectF(-outer, -outer, outer * 2, outer * 2)
    inner_rect = QRectF(-inner, -inner, inner * 2, inner * 2)
    path = QPainterPath()
    path.arcMoveTo(outer_rect, start_angle)
    path.arcTo(outer_rect, start_angle, span)
    path.arcTo(inner_rect, start_angle + span, -span)
    path.closeSubpath()
    return path


def mix(a, b, t):
    a, b = QColor(a), QColor(b)
    return QColor.fromRgbF(
        pose.lerp(a.redF(), b.redF(), t),
        pose.lerp(a.greenF(), b.greenF(), t),
        pose.lerp(a.blueF(), b.blueF(), t),
    )


class PieMenu(OverlayWindow):
    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        self.state = PieMenuState(self.applySettings)

        self.prompt_flow = PromptFlow(self, len(self.state.wedges), self.onHandoffTick, self.onHandoffDone)
        self.prompt_bar = self.prompt_flow.bar
        self.prompt_bar.submitted.connect(self.onPromptSubmitted)
        self.prompt_bar.cancelled.connect(self.returnToRing)

        self.animation = PieMenuAnimation(
            self,
            self.state,
            len(self.state.wedges),
            self.prompt_flow.clock,
            request_repaint=lambda: self.update(self.ringRect()),
            on_select_done=self.beginClose,
            on_closed=lambda: self.setWindowOpacity(0),
        )
        self.clocks = self.animation.clocks
        self.open_clock = self.animation.open_clock
        self.chat = ChatSlot()  # the card is a top-level window; this is what keeps it alive

        self.setWindowOpacity(0)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setGeometry(QApplication.primaryScreen().virtualGeometry())
        self.show()

    @property
    def phase(self):
        return self.state.phase

    @property
    def chosen_wedge(self):
        return self.state.chosen_wedge

    @property
    def hovered_wedge(self):
        return self.state.hovered_wedge

    @property
    def wedges(self):
        return self.state.wedges

    @property
    def motion(self):
        return self.animation.motion

    @motion.setter
    def motion(self, value):
        self.animation.motion = value

    def applySettings(self, other_entries):
        """Called by the Settings card after a relabel/reorder/reassign is
        saved."""
        self.state.applySettings(self.applySettings)

    # --- hover wiring ---

    def setHovered(self, index):
        if index == self.state.hovered_wedge:
            return
        previous, self.state.hovered_wedge = self.state.hovered_wedge, index
        if previous is not None:
            self.animation.animateHover(previous, 0)
        if index is not None:
            self.animation.animateHover(index, 1)

    def ringRect(self):
        """Screen area the ring's ink can reach."""
        return QRectF(
            self.state.anchor.x() - PAINT_REACH,
            self.state.anchor.y() - PAINT_REACH,
            PAINT_REACH * 2,
            PAINT_REACH * 2,
        ).toAlignedRect()

    # --- phases ---

    def onKeyPress(self):
        """The global hotkey. Always does something: it opens the ring, or
        gets whatever's up out of the way."""
        if self.state.phase in (HIDDEN, CLOSING):
            self.openAtCursor()
        elif self.state.phase in (HANDOFF, PROMPTING):
            self.cancelPrompt()
        else:
            self.beginClose()

    def openAtCursor(self):
        self.animation.stopClocks()
        self.state.phase = OPENING
        self.state.anchor = QPointF(self.mapFromGlobal(QCursor.pos()))
        self.state.chosen_wedge = None
        self.state.prompt_text = None
        self.animation.open_ms = self.animation.select_ms = self.animation.close_ms = self.prompt_flow.ms = 0
        self.animation.clearHover()
        self.state.hovered_wedge = None
        self.prompt_bar.hide()

        self.repaint()  # bake the new anchor's frame in before revealing the window
        self.setWindowOpacity(1)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        force_foreground(int(self.winId()))
        self.activateWindow()
        self.setFocus()
        self.grabMouse()
        self.animation.open_clock.run(pose.open_total_ms(), self.motion)

    def activateHoveredWedge(self):
        if self.state.hovered_wedge is None:
            self.beginClose()
            return
        self.state.chosen_wedge = self.state.hovered_wedge
        wedge = self.state.wedges[self.state.chosen_wedge]
        if wedge.placeholder is None:
            # Run it now, not after the select/close animation finishes -
            # that animation is just the ring's own visual follow-through,
            # the card shouldn't wait on it to appear.
            wedge.action()
            self.beginSelect()
        elif self.chat.reveal(wedge.id):
            # A session for this wedge is already open - just resurface it,
            # no prompt bar, no new message.
            self.beginSelect()
        else:
            self.beginHandoff(wedge)

    def beginSelect(self):
        self.animation.stopClocks()
        self.state.phase = SELECTING
        self.animation.select_ms = 0
        self.animation.select_clock.run(pose.select_total_ms(), self.motion)

    def beginHandoff(self, wedge, seed=""):
        """Hand the ring off to the prompt bar: the ring clears out, then a
        rounded rect grows from the chosen wedge into the text field."""
        self.animation.stopClocks()
        self.state.phase = HANDOFF
        self.releaseMouse()  # the field has to be able to receive its own clicks

        # However the wedge was picked, it holds a full hover pose while the
        # rest of the ring leaves - that hold is what makes the pick register.
        self.animation.hover_anims[self.state.chosen_wedge].stop()
        self.animation.hover_t[self.state.chosen_wedge] = 1.0
        self.state.hovered_wedge = self.state.chosen_wedge

        self.prompt_flow.begin(self.state.anchor, self.state.chosen_wedge, wedge, seed, self.motion)

    def onHandoffTick(self):
        self.update(self.ringRect())

    def onHandoffDone(self):
        self.state.phase = PROMPTING

    def returnToRing(self):
        """Escape out of the prompt bar steps back to the ring, not straight
        to hidden."""
        self.animation.stopClocks()
        self.state.phase = OPENING
        self.prompt_bar.hide()
        self.state.chosen_wedge = None
        self.state.prompt_text = None
        self.animation.open_ms = self.prompt_flow.ms = 0
        self.animation.clearHover()
        self.state.hovered_wedge = None
        self.setFocus()
        self.grabMouse()
        self.animation.open_clock.run(pose.open_total_ms(), self.motion)

    def onPromptSubmitted(self, text):
        self.state.prompt_text = text
        self.state.born_rect = self.prompt_bar.screenRect()  # capture before anything hides it
        self.beginClose()

    def cancelPrompt(self):
        self.state.chosen_wedge = None  # nothing runs
        self.beginClose()

    def beginClose(self):
        self.animation.stopClocks()
        self.state.phase = CLOSING
        self.releaseMouse()
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        # A plain wedge's action already ran the instant it was picked (see
        # activateHoveredWedge) - this only has the prompt-wedge case left,
        # since that one needs the submitted text before it can run. Fired
        # here rather than waiting for the fade so the card exists before
        # the bar (born as its rect) goes.
        if self.state.chosen_wedge is not None:
            wedge = self.state.wedges[self.state.chosen_wedge]
            if wedge.placeholder is not None and self.state.prompt_text is not None:
                # None means activateHoveredWedge() already reused an open
                # card for this wedge instead of asking for a prompt.
                self.chat.open(self.state.born_rect, self.state.prompt_text, wedge.id, wedge.action)
        self.prompt_bar.hide()

        self.animation.close_ms = 0
        self.animation.close_clock.run(style.CLOSE_MS, self.motion)

    # --- input ---

    def mouseMoveEvent(self, event):
        if self.state.phase not in (OPENING, OPEN):
            return
        pos = event.position()
        dx = pos.x() - self.state.anchor.x()
        dy = pos.y() - self.state.anchor.y()
        self.setHovered(wedge_index(dx, dy, len(self.state.wedges), INNER_RADIUS, HIT_RADIUS))

    def mousePressEvent(self, event):
        if self.state.phase in (OPENING, OPEN):
            self.activateHoveredWedge()
        elif self.state.phase == PROMPTING:
            self.cancelPrompt()  # clicks on the field itself never reach here

    def keyPressEvent(self, event):
        if self.state.phase == HANDOFF:
            # The field isn't focusable yet, but the user may already be
            # typing - keep the keystrokes rather than dropping them.
            if event.key() == Qt.Key_Escape:
                self.returnToRing()
            elif self.isTyping(event):
                self.prompt_bar.appendSeed(event.text())
            return

        if self.state.phase not in (OPENING, OPEN):
            return

        key = event.key()
        if key == Qt.Key_Escape:
            self.beginClose()
        elif key in ACTIVATE_WIDGET_KEYS:
            self.activateHoveredWedge()
        elif key in ARROW_ANGLE_BY_KEY:
            self.setHovered(compass_wedge(len(self.state.wedges), ARROW_ANGLE_BY_KEY[key]))
        elif self.isTyping(event):
            self.jumpToPrompt(event.text())

    def isTyping(self, event):
        text = event.text()
        return bool(text) and text.isprintable() and not text.isspace()

    def jumpToPrompt(self, seed):
        """A printable keypress while the ring is up goes straight into the
        prompt, carrying the character that started it."""
        index = next((i for i, wedge in enumerate(self.state.wedges) if wedge.placeholder is not None), None)
        if index is None:
            return
        self.state.chosen_wedge = index
        self.beginHandoff(self.state.wedges[index], seed)

    # --- painting ---

    def paintEvent(self, event):
        if self.state.phase == HIDDEN:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        close_scale, close_alpha = pose.close_pose(self.animation.close_ms)
        open_scale, open_alpha = pose.open_pose(self.animation.open_ms)
        if self.state.chosen_wedge is None:
            # Not the chosen wedge's own hold-then-crossfade curve - the
            # shadow is one ambient blob under the whole ring, so it clears
            # out with the rest of the ring rather than lingering through
            # the handoff.
            exit_scale, exit_alpha = pose.ring_exit_pose(self.prompt_flow.ms, False)
            self.paintRingShadow(
                painter, open_scale * exit_scale * close_scale, open_alpha * exit_alpha * close_alpha
            )

        # Hovered wedge last so its glow sits above its neighbours.
        order = [i for i in range(len(self.state.wedges)) if i != self.state.hovered_wedge]
        if self.state.hovered_wedge is not None:
            order.append(self.state.hovered_wedge)
        for i in order:
            self.paintWedge(painter, i, close_scale, close_alpha)

    def paintRingShadow(self, painter, scale, alpha):
        """A soft ambient shadow tracing the ring's own donut shape, echoing
        shadow.py's card look (offset down, blurred) - approximated with a
        radial gradient since a QGraphicsDropShadowEffect can't target a
        shape hand-painted inside this full-screen overlay window. Hollow
        in the middle like the ring's own dead zone, and blurred on both
        the inner and outer edge, rather than a solid disc that shows
        straight through the ring's transparent hole."""
        if alpha <= 0:
            return
        inner = INNER_RADIUS * scale
        radius = style.RING_RADIUS * scale
        blur = style.CARD_SHADOW_BLUR
        outer = radius + blur
        painter.save()
        painter.translate(self.state.anchor.x(), self.state.anchor.y() + style.CARD_SHADOW_OFFSET_Y * scale)
        color = QColor(0, 0, 0, round(style.CARD_SHADOW_ALPHA * alpha))
        transparent = QColor(0, 0, 0, 0)
        gradient = QRadialGradient(0, 0, outer)
        gradient.setColorAt(max(0.0, inner - blur) / outer, transparent)
        gradient.setColorAt(inner / outer, color)
        gradient.setColorAt(radius / outer, color)
        gradient.setColorAt(1.0, transparent)
        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(QPointF(0, 0), outer, outer)
        painter.restore()

    def paintWedge(self, painter, index, close_scale, close_alpha):
        count = len(self.state.wedges)
        span = 360 / count
        t = self.animation.hover_t[index]
        chosen = index == self.state.chosen_wedge

        # Each exit sits at its resting pose until its own clock runs, so
        # they compose without caring which one is actually in play.
        open_scale, open_alpha = pose.open_pose(self.animation.open_ms)
        select_scale, select_alpha, select_push = pose.select_pose(self.animation.select_ms, chosen)
        exit_scale, exit_alpha = pose.ring_exit_pose(self.prompt_flow.ms, chosen)
        hover_push, outer, label_scale = pose.hover_pose(t)

        alpha = open_alpha * select_alpha * exit_alpha * close_alpha
        if alpha <= 0:
            return
        scale = open_scale * select_scale * exit_scale * close_scale
        bx, by = pose.bisector(index, count)
        push = hover_push + select_push

        painter.save()
        painter.setOpacity(alpha)
        painter.translate(self.state.anchor)
        painter.scale(scale, scale)
        painter.translate(push * bx, push * by)

        path = ring_segment(outer, INNER_RADIUS, 90 - index * span - span / 2, span)

        if t > 0:
            glow = QColor(style.GLOW)
            glow.setAlphaF(style.GLOW_ALPHA * t)
            painter.setPen(QPen(glow, style.GLOW_WIDTH))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)

        painter.setPen(QPen(QColor(style.WEDGE_BORDER), 1))
        painter.setBrush(QColor(style.WEDGE_PRESSED) if chosen else mix(style.WEDGE_IDLE, style.WEDGE_HOVER, t))
        painter.drawPath(path)

        label_r = style.RING_LABEL * style.RING_RADIUS
        painter.translate(label_r * bx, label_r * by)
        painter.scale(label_scale, label_scale)
        painter.setPen(mix(style.LABEL_IDLE, style.LABEL_HOVER, t))
        painter.drawText(QRectF(-50, -15, 100, 30), Qt.AlignCenter, self.state.wedges[index].label)
        painter.restore()
