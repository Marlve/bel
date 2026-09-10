# Concept for ADR-0006: hotkey opens a ring around the cursor, split into
# wedges; moving the mouse toward one highlights it, clicking runs that
# wedge's action. A wedge whose action needs typed input hands off to the
# prompt bar instead of firing straight away.

import math
from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPainter, QColor, QCursor, QPainterPath, QPen
from PySide6.QtCore import Qt, QPointF, QRectF, QVariantAnimation

import style
import pie_anim
from overlay import OverlayWindow
from prompt_bar import PromptBar
from actions import ACTIONS
from util import force_foreground, reduced_motion

INNER_RADIUS = style.RING_INNER * style.RING_RADIUS  # hollow center doubles as the dead zone
HIT_RADIUS = style.RING_HIT_OUTER * style.RING_RADIUS

# Furthest a wedge's ink can land from the anchor: grown by hover, pushed out
# by hover and select together, plus half the glow's stroke, all at the peak
# scale the open overshoot and select reach. Sizes dirty rects only - how far
# out the cursor still counts as pointing at a wedge is HIT_RADIUS, a
# separate question with a separate answer.
OPEN_PEAK_SCALE = max(pie_anim.open_pose(ms, 0)[0] for ms in range(style.OPEN_MS + 1))
PAINT_REACH = (
    (style.HOVER_GROW + style.HOVER_PUSH + style.SELECT_PUSH) * style.RING_RADIUS + style.GLOW_WIDTH / 2
) * OPEN_PEAK_SCALE * style.SELECT_SCALE

CYCLE_STEP_BY_KEY = {Qt.Key_Right: 1, Qt.Key_Left: -1}
ACTIVATE_WIDGET_KEYS = (Qt.Key_Return, Qt.Key_Enter)

# The menu's life cycle. Input only counts while opening or open (or, once
# the prompt bar has arrived, while prompting); the exits play out untouched
# once started.
HIDDEN, OPENING, OPEN, SELECTING, HANDOFF, PROMPTING, CLOSING = (
    "hidden", "opening", "open", "selecting", "handoff", "prompting", "closing",
)


def wedge_index(dx, dy, count, deadzone=0, radius=None):
    """Index of the wedge (0 = up, going clockwise) that (dx, dy) points
    into, or None if the point is inside the deadzone or outside radius.
    dx/dy are a screen space offset from the menu's center - y grows
    downward.
    """
    dist = math.hypot(dx, dy)
    if dist < deadzone:
        return None
    if radius is not None and dist > radius:
        return None

    math_angle = math.degrees(math.atan2(-dy, dx)) % 360  # 0=right, 90=up
    compass_angle = (90 - math_angle) % 360  # 0=up, 90=right, clockwise
    wedge_width = 360 / count
    shifted = (compass_angle + wedge_width / 2) % 360
    return int(shifted // wedge_width)


def cycle_wedge(current, count, step):
    """Index of the wedge step (+1 = right/next, -1 = left/previous) away
    from current, wrapping around. current=None starts from just before the
    first wedge (step=+1) or just after the last (step=-1).
    """
    if current is None:
        current = -1 if step > 0 else 0
    return (current + step) % count


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
        pie_anim.lerp(a.redF(), b.redF(), t),
        pie_anim.lerp(a.greenF(), b.greenF(), t),
        pie_anim.lerp(a.blueF(), b.blueF(), t),
    )


@dataclass
class Wedge:
    label: str
    action: Callable[..., None]
    placeholder: Optional[str] = None  # set = ask for text first, and pass it to the action


# Which wedges the menu shows, in order. Each entry's "id" picks an action
# factory from ACTIONS; any other key is that action's own config (e.g.
# "claude" reads "prompt"). A "placeholder" sends the wedge through the
# prompt bar first. Hardcoded for now - once there's a settings UI, this is
# the shape it needs to produce.
WEDGE_CONFIG = [
    {"id": "announce", "label": "Todo"},
    {"id": "announce", "label": "Note"},
    {"id": "announce", "label": "Down"},
    {"id": "claude", "label": "Claude", "placeholder": "Ask Bel anything…"},
]


def build_wedges(config):
    return [
        Wedge(entry["label"], ACTIONS[entry["id"]](entry), entry.get("placeholder"))
        for entry in config
    ]


class PieMenu(OverlayWindow):
    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        self.anchor = QPointF(0, 0)
        self.phase = HIDDEN
        self.hovered_wedge = None
        self.chosen_wedge = None
        self.prompt_text = None
        self.wedges = build_wedges(WEDGE_CONFIG)
        self.motion = not reduced_motion()

        # Elapsed ms into each phase. A phase that hasn't run sits at 0,
        # where its pose is the resting one, so they all just multiply
        # together in paintWedge without any "has this started yet" branches.
        self.open_ms = 0
        self.select_ms = 0
        self.handoff_ms = 0
        self.close_ms = 0
        self.open_clock = self.makeClock(self.onOpenTick, self.onOpened)
        self.select_clock = self.makeClock(self.onSelectTick, self.beginClose)
        self.handoff_clock = self.makeClock(self.onHandoffTick, self.onHandoffDone)
        self.close_clock = self.makeClock(self.onCloseTick, self.onClosed)
        self.clocks = (self.open_clock, self.select_clock, self.handoff_clock, self.close_clock)

        # One 0..1 float per wedge drives every hover property, so a wedge
        # caught mid-retreat animates from wherever it actually is.
        self.hover_t = [0.0] * len(self.wedges)
        self.hover_anims = [self.makeHoverAnimation(i) for i in range(len(self.wedges))]

        self.prompt_bar = PromptBar(self)
        self.prompt_bar.submitted.connect(self.onPromptSubmitted)
        self.prompt_bar.cancelled.connect(self.returnToRing)

        self.setWindowOpacity(0)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setGeometry(QApplication.primaryScreen().virtualGeometry())
        self.show()

    # --- animation plumbing ---

    def makeClock(self, on_tick, on_done):
        clock = QVariantAnimation(self)
        clock.setStartValue(0)
        clock.valueChanged.connect(on_tick)
        clock.finished.connect(on_done)
        return clock

    def runClock(self, clock, total_ms):
        clock.setEndValue(total_ms)
        clock.setDuration(total_ms)
        clock.start()
        if not self.motion:
            clock.setCurrentTime(total_ms)  # jump straight to the resting pose

    def stopClocks(self):
        # Every phase change calls this. A clock left running would keep
        # ticking into the new phase and, worse, still fire its finished
        # handler - which for select_clock means running the chosen wedge's
        # action a second time.
        for clock in self.clocks:
            clock.stop()

    def makeHoverAnimation(self, index):
        anim = QVariantAnimation(self)
        anim.valueChanged.connect(lambda t: self.onHoverTick(index, t))
        return anim

    def onHoverTick(self, index, t):
        self.hover_t[index] = t
        self.update(self.ringRect())

    def animateHover(self, index, target):
        anim = self.hover_anims[index]
        anim.stop()
        if not self.motion:
            self.onHoverTick(index, float(target))
            return
        anim.setStartValue(self.hover_t[index])
        anim.setEndValue(float(target))
        if target:
            anim.setDuration(style.HOVER_IN_MS)
            anim.setEasingCurve(pie_anim.HOVER_IN)
        else:
            anim.setDuration(style.HOVER_OUT_MS)
            anim.setEasingCurve(pie_anim.HOVER_OUT)
        anim.start()

    def clearHover(self):
        for anim in self.hover_anims:
            anim.stop()
        self.hover_t = [0.0] * len(self.wedges)
        self.hovered_wedge = None

    def ringRect(self):
        """Screen area the ring's ink can reach."""
        return QRectF(
            self.anchor.x() - PAINT_REACH, self.anchor.y() - PAINT_REACH, PAINT_REACH * 2, PAINT_REACH * 2
        ).toAlignedRect()

    # --- geometry the prompt bar flies between ---

    def wedgeBox(self, index):
        """The square the prompt bar's rect grows out of, centered on the
        wedge's label."""
        bx, by = pie_anim.bisector(index, len(self.wedges))
        reach = style.RING_LABEL * style.RING_RADIUS
        box = QRectF(0, 0, style.WEDGE_BOX, style.WEDGE_BOX)
        box.moveCenter(QPointF(self.anchor.x() + reach * bx, self.anchor.y() + reach * by))
        return box

    def fieldRect(self):
        rect = QRectF(0, 0, style.FIELD_WIDTH, style.FIELD_HEIGHT)
        rect.moveCenter(self.anchor)
        return rect

    # --- phases ---

    def onKeyPress(self):
        """The global hotkey. Always does something: it opens the ring, or
        gets whatever's up out of the way."""
        if self.phase in (HIDDEN, CLOSING):
            self.openAtCursor()
        elif self.phase in (HANDOFF, PROMPTING):
            self.cancelPrompt()
        else:
            self.beginClose()

    def openAtCursor(self):
        self.stopClocks()
        self.phase = OPENING
        self.anchor = QPointF(self.mapFromGlobal(QCursor.pos()))
        self.chosen_wedge = None
        self.prompt_text = None
        self.open_ms = self.select_ms = self.handoff_ms = self.close_ms = 0
        self.clearHover()
        self.prompt_bar.hide()

        self.repaint()  # bake the new anchor's frame in before revealing the window
        self.setWindowOpacity(1)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        force_foreground(int(self.winId()))
        self.activateWindow()
        self.setFocus()
        self.grabMouse()
        self.runClock(self.open_clock, pie_anim.open_total_ms(len(self.wedges)))

    def onOpenTick(self, ms):
        self.open_ms = ms
        # The scrim covers the whole desktop but stops changing well before
        # the wedges do; past that only the ring is dirty.
        self.update() if ms <= style.SCRIM_MS else self.update(self.ringRect())

    def onOpened(self):
        self.phase = OPEN

    def setHovered(self, index):
        if index == self.hovered_wedge:
            return
        previous, self.hovered_wedge = self.hovered_wedge, index
        if previous is not None:
            self.animateHover(previous, 0)
        if index is not None:
            self.animateHover(index, 1)

    def activateHoveredWedge(self):
        if self.hovered_wedge is None:
            self.beginClose()
            return
        self.chosen_wedge = self.hovered_wedge
        wedge = self.wedges[self.chosen_wedge]
        if wedge.placeholder is None:
            self.beginSelect()
        else:
            self.beginHandoff(wedge)

    def beginSelect(self):
        self.stopClocks()
        self.phase = SELECTING
        self.select_ms = 0
        self.runClock(self.select_clock, pie_anim.select_total_ms())

    def onSelectTick(self, ms):
        self.select_ms = ms
        self.update(self.ringRect())

    def beginHandoff(self, wedge, seed=""):
        """Hand the ring off to the prompt bar: the ring clears out, then a
        rounded rect grows from the chosen wedge into the text field."""
        self.stopClocks()
        self.phase = HANDOFF
        self.handoff_ms = 0
        self.releaseMouse()  # the field has to be able to receive its own clicks

        # However the wedge was picked, it holds a full hover pose while the
        # rest of the ring leaves - that hold is what makes the pick register.
        self.hover_anims[self.chosen_wedge].stop()
        self.hover_t[self.chosen_wedge] = 1.0
        self.hovered_wedge = self.chosen_wedge

        self.prompt_bar.launch(wedge.placeholder, seed)
        self.prompt_bar.setGeometry(self.wedgeBox(self.chosen_wedge).toRect())
        self.prompt_bar.raise_()
        self.runClock(self.handoff_clock, pie_anim.handoff_total_ms())

    def onHandoffTick(self, ms):
        self.handoff_ms = ms
        grown = pie_anim.lerp_rect(self.wedgeBox(self.chosen_wedge), self.fieldRect(), pie_anim.grow_progress(ms))
        self.prompt_bar.setGeometry(grown.toRect())
        self.prompt_bar.setFlight(pie_anim.crossfade_progress(ms), pie_anim.field_progress(ms))
        if ms >= pie_anim.geometry_rest_ms():
            self.prompt_bar.place()  # only now that the rect has stopped moving
        self.update(self.ringRect())

    def onHandoffDone(self):
        self.phase = PROMPTING
        self.prompt_bar.place()
        self.prompt_bar.takeFocus()

    def returnToRing(self):
        """Escape out of the prompt bar steps back to the ring, not straight
        to hidden."""
        self.stopClocks()
        self.phase = OPENING
        self.prompt_bar.hide()
        self.chosen_wedge = None
        self.prompt_text = None
        self.open_ms = self.handoff_ms = 0
        self.clearHover()
        self.setFocus()
        self.grabMouse()
        self.runClock(self.open_clock, pie_anim.open_total_ms(len(self.wedges)))

    def onPromptSubmitted(self, text):
        self.prompt_text = text
        self.beginClose()

    def cancelPrompt(self):
        self.chosen_wedge = None  # nothing runs
        self.beginClose()

    def beginClose(self):
        self.stopClocks()
        self.phase = CLOSING
        self.releaseMouse()
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.prompt_bar.hide()

        # Fire at the start of the close, not the end - the user shouldn't wait on the fade.
        if self.chosen_wedge is not None:
            wedge = self.wedges[self.chosen_wedge]
            if wedge.placeholder is None:
                wedge.action()
            else:
                wedge.action(self.prompt_text)

        self.close_ms = 0
        self.runClock(self.close_clock, style.CLOSE_MS)

    def onCloseTick(self, ms):
        self.close_ms = ms
        self.update()  # the scrim is fading too, so the whole screen is dirty

    def onClosed(self):
        self.phase = HIDDEN
        self.setWindowOpacity(0)

    # --- input ---

    def mouseMoveEvent(self, event):
        if self.phase not in (OPENING, OPEN):
            return
        pos = event.position()
        dx = pos.x() - self.anchor.x()
        dy = pos.y() - self.anchor.y()
        self.setHovered(wedge_index(dx, dy, len(self.wedges), INNER_RADIUS, HIT_RADIUS))

    def mousePressEvent(self, event):
        if self.phase in (OPENING, OPEN):
            self.activateHoveredWedge()
        elif self.phase == PROMPTING:
            self.cancelPrompt()  # clicks on the field itself never reach here

    def keyPressEvent(self, event):
        if self.phase == HANDOFF:
            # The field isn't focusable yet, but the user may already be
            # typing - keep the keystrokes rather than dropping them.
            if event.key() == Qt.Key_Escape:
                self.returnToRing()
            elif self.isTyping(event):
                self.prompt_bar.appendSeed(event.text())
            return

        if self.phase not in (OPENING, OPEN):
            return

        key = event.key()
        if key == Qt.Key_Escape:
            self.beginClose()
        elif key in ACTIVATE_WIDGET_KEYS:
            self.activateHoveredWedge()
        elif key in CYCLE_STEP_BY_KEY:
            self.setHovered(cycle_wedge(self.hovered_wedge, len(self.wedges), CYCLE_STEP_BY_KEY[key]))
        elif self.isTyping(event):
            self.jumpToPrompt(event.text())

    def isTyping(self, event):
        text = event.text()
        return bool(text) and text.isprintable() and not text.isspace()

    def jumpToPrompt(self, seed):
        """A printable keypress while the ring is up goes straight into the
        prompt, carrying the character that started it."""
        index = next((i for i, wedge in enumerate(self.wedges) if wedge.placeholder is not None), None)
        if index is None:
            return
        self.chosen_wedge = index
        self.beginHandoff(self.wedges[index], seed)

    # --- painting ---

    def paintEvent(self, event):
        if self.phase == HIDDEN:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        close_scale, close_alpha = pie_anim.close_pose(self.close_ms)

        scrim = QColor(style.SCRIM)
        scrim.setAlphaF(style.SCRIM_ALPHA * pie_anim.scrim_progress(self.open_ms) * close_alpha)
        painter.fillRect(self.rect(), scrim)

        # Hovered wedge last so its glow sits above its neighbours.
        order = [i for i in range(len(self.wedges)) if i != self.hovered_wedge]
        if self.hovered_wedge is not None:
            order.append(self.hovered_wedge)
        for i in order:
            self.paintWedge(painter, i, close_scale, close_alpha)

    def paintWedge(self, painter, index, close_scale, close_alpha):
        count = len(self.wedges)
        span = 360 / count
        t = self.hover_t[index]
        chosen = index == self.chosen_wedge

        # Each exit sits at its resting pose until its own clock runs, so
        # they compose without caring which one is actually in play.
        open_scale, open_alpha = pie_anim.open_pose(self.open_ms, index)
        select_scale, select_alpha, select_push = pie_anim.select_pose(self.select_ms, chosen)
        exit_scale, exit_alpha = pie_anim.ring_exit_pose(self.handoff_ms, chosen)
        hover_push, outer, label_scale = pie_anim.hover_pose(t)

        alpha = open_alpha * select_alpha * exit_alpha * close_alpha
        if alpha <= 0:
            return
        scale = open_scale * select_scale * exit_scale * close_scale
        bx, by = pie_anim.bisector(index, count)
        push = hover_push + select_push

        painter.save()
        painter.setOpacity(alpha)
        painter.translate(self.anchor)
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
        painter.drawText(QRectF(-50, -15, 100, 30), Qt.AlignCenter, self.wedges[index].label)
        painter.restore()
