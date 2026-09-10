# Concept for ADR-0006: hotkey opens a ring around the cursor, split into
# wedges; moving the mouse toward one highlights it, clicking runs that
# wedge's action. A wedge whose action needs typed input hands off to the
# prompt bar instead of firing straight away.

import math
from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPainter, QColor, QCursor, QPainterPath, QPen, QRadialGradient
from PySide6.QtCore import Qt, QPointF, QRectF

import style
import wedge_config
from anims import pose
from anims.clock import Clock, HoverClock
from overlay import OverlayWindow
from prompt_flow import PromptFlow
from chat_card import ChatStack
from actions import ACTIONS
from util import force_foreground, reduced_motion

INNER_RADIUS = style.RING_INNER * style.RING_RADIUS  # hollow center doubles as the dead zone
HIT_RADIUS = style.RING_HIT_OUTER * style.RING_RADIUS

# Furthest a wedge's ink can land from the anchor: grown by hover, pushed out
# by hover and select together, plus half the glow's stroke, all at the peak
# scale the open overshoot and select reach. Sizes dirty rects only - how far
# out the cursor still counts as pointing at a wedge is HIT_RADIUS, a
# separate question with a separate answer.
OPEN_PEAK_SCALE = max(pose.open_pose(ms)[0] for ms in range(style.OPEN_MS + 1))
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
        pose.lerp(a.redF(), b.redF(), t),
        pose.lerp(a.greenF(), b.greenF(), t),
        pose.lerp(a.blueF(), b.blueF(), t),
    )


@dataclass
class Wedge:
    id: str
    label: str
    action: Callable[..., None]
    placeholder: Optional[str] = None  # set = ask for text first, and pass it to the action


# Which wedges the menu shows, in order. Todo/Note/Claude are user-editable
# via the Settings wedge (see wedge_config.py for persistence and
# defaults); Settings itself is always pinned as close to the bottom of the
# ring as the current wedge count allows, wherever the editable wedges land.
# Each entry's "id" picks an action factory from ACTIONS; any other key is
# that action's own config (e.g. "claude" reads "prompt", "settings" reads
# "on_change"). A "placeholder" sends the wedge through the prompt bar first.
def current_config(on_settings_change):
    others = wedge_config.resolve(wedge_config.load_other_wedges())
    config = wedge_config.full_config(others)
    for entry in config:
        if entry["id"] == "settings":
            entry["on_change"] = on_settings_change
    return config


def build_wedges(config, previous=()):
    """Wedges for `config`, in order. A slot whose action id matches one in
    `previous` reuses that Wedge's existing action object instead of
    calling its factory again - a fresh call would build a brand new toggle
    closure with no memory of an already-open Note/Todo card, silently
    orphaning it. Only label/placeholder refresh on a reused wedge; those
    are cheap to swap in place."""
    by_id = {wedge.id: wedge for wedge in previous}
    wedges = []
    for entry in config:
        existing = by_id.get(entry["id"])
        if existing is not None:
            existing.label = entry["label"]
            existing.placeholder = entry.get("placeholder")
            wedges.append(existing)
        else:
            wedges.append(Wedge(entry["id"], entry["label"], ACTIONS[entry["id"]](entry), entry.get("placeholder")))
    return wedges


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
        self.born_rect = None  # the prompt bar's last rect, which a card is born as
        self.wedges = build_wedges(current_config(self.applySettings))
        self.motion = not reduced_motion()

        # Elapsed ms into each phase. A phase that hasn't run sits at 0,
        # where its pose is the resting one, so they all just multiply
        # together in paintWedge without any "has this started yet" branches.
        self.open_ms = 0
        self.select_ms = 0
        self.close_ms = 0
        self.open_clock = Clock(self, self.onOpenTick, self.onOpened)
        self.select_clock = Clock(self, self.onSelectTick, self.beginClose)
        self.close_clock = Clock(self, self.onCloseTick, self.onClosed)

        # One 0..1 float per wedge drives every hover property, so a wedge
        # caught mid-retreat animates from wherever it actually is.
        self.hover_t = [0.0] * len(self.wedges)
        self.hover_anims = [HoverClock(self, self.makeHoverTick(i)) for i in range(len(self.wedges))]

        self.prompt_flow = PromptFlow(self, len(self.wedges), self.onHandoffTick, self.onHandoffDone)
        self.prompt_bar = self.prompt_flow.bar
        self.prompt_bar.submitted.connect(self.onPromptSubmitted)
        self.prompt_bar.cancelled.connect(self.returnToRing)
        self.clocks = (self.open_clock, self.select_clock, self.prompt_flow.clock, self.close_clock)
        self.cards = ChatStack()  # cards are top-level windows; this is what keeps them alive

        self.setWindowOpacity(0)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setGeometry(QApplication.primaryScreen().virtualGeometry())
        self.show()

    def applySettings(self, other_entries):
        """Called by the Settings card after a relabel/reorder/reassign is
        saved. The ring is always closed while that card is up - settings
        is itself a wedge pick - so nothing keyed to len(self.wedges)
        (hover_anims, prompt_flow) needs touching, only the wedges list."""
        self.wedges = build_wedges(current_config(self.applySettings), self.wedges)

    # --- hover wiring ---

    def stopClocks(self):
        # Every phase change calls this. A clock left running would keep
        # ticking into the new phase and, worse, still fire its finished
        # handler - which for select_clock means running the chosen wedge's
        # action a second time.
        for clock in self.clocks:
            clock.stop()

    def makeHoverTick(self, index):
        return lambda t: self.onHoverTick(index, t)

    def onHoverTick(self, index, t):
        self.hover_t[index] = t
        self.update(self.ringRect())

    def animateHover(self, index, target):
        self.hover_anims[index].animateTo(self.hover_t[index], target, self.motion)

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
        self.open_ms = self.select_ms = self.close_ms = self.prompt_flow.ms = 0
        self.clearHover()
        self.prompt_bar.hide()

        self.repaint()  # bake the new anchor's frame in before revealing the window
        self.setWindowOpacity(1)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        force_foreground(int(self.winId()))
        self.activateWindow()
        self.setFocus()
        self.grabMouse()
        self.open_clock.run(pose.open_total_ms(), self.motion)

    def onOpenTick(self, ms):
        self.open_ms = ms
        self.update(self.ringRect())

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
        self.select_clock.run(pose.select_total_ms(), self.motion)

    def onSelectTick(self, ms):
        self.select_ms = ms
        self.update(self.ringRect())

    def beginHandoff(self, wedge, seed=""):
        """Hand the ring off to the prompt bar: the ring clears out, then a
        rounded rect grows from the chosen wedge into the text field."""
        self.stopClocks()
        self.phase = HANDOFF
        self.releaseMouse()  # the field has to be able to receive its own clicks

        # However the wedge was picked, it holds a full hover pose while the
        # rest of the ring leaves - that hold is what makes the pick register.
        self.hover_anims[self.chosen_wedge].stop()
        self.hover_t[self.chosen_wedge] = 1.0
        self.hovered_wedge = self.chosen_wedge

        self.prompt_flow.begin(self.anchor, self.chosen_wedge, wedge, seed, self.motion)

    def onHandoffTick(self):
        self.update(self.ringRect())

    def onHandoffDone(self):
        self.phase = PROMPTING

    def returnToRing(self):
        """Escape out of the prompt bar steps back to the ring, not straight
        to hidden."""
        self.stopClocks()
        self.phase = OPENING
        self.prompt_bar.hide()
        self.chosen_wedge = None
        self.prompt_text = None
        self.open_ms = self.prompt_flow.ms = 0
        self.clearHover()
        self.setFocus()
        self.grabMouse()
        self.open_clock.run(pose.open_total_ms(), self.motion)

    def onPromptSubmitted(self, text):
        self.prompt_text = text
        self.born_rect = self.prompt_bar.screenRect()  # capture before anything hides it
        self.beginClose()

    def cancelPrompt(self):
        self.chosen_wedge = None  # nothing runs
        self.beginClose()

    def beginClose(self):
        self.stopClocks()
        self.phase = CLOSING
        self.releaseMouse()
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        # Fire at the start of the close, not the end - the user shouldn't
        # wait on the fade. A prompt wedge's answer goes to a card born as
        # the bar's own rect, so the card has to exist before the bar goes.
        if self.chosen_wedge is not None:
            wedge = self.wedges[self.chosen_wedge]
            if wedge.placeholder is None:
                wedge.action()
            else:
                self.cards.open(self.born_rect, self.prompt_text, wedge.action)
        self.prompt_bar.hide()

        self.close_ms = 0
        self.close_clock.run(style.CLOSE_MS, self.motion)

    def onCloseTick(self, ms):
        self.close_ms = ms
        self.update(self.ringRect())

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
        elif key == Qt.Key_Up:
            self.setHovered(0)  # wedge 0 is compass-up by wedge_index()'s own convention
        elif key == Qt.Key_Down:
            self.setHovered(wedge_config.bottom_pin_index(len(self.wedges)))
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

        close_scale, close_alpha = pose.close_pose(self.close_ms)
        open_scale, open_alpha = pose.open_pose(self.open_ms)
        self.paintRingShadow(painter, open_scale * close_scale, open_alpha * close_alpha)

        # Hovered wedge last so its glow sits above its neighbours.
        order = [i for i in range(len(self.wedges)) if i != self.hovered_wedge]
        if self.hovered_wedge is not None:
            order.append(self.hovered_wedge)
        for i in order:
            self.paintWedge(painter, i, close_scale, close_alpha)

    def paintRingShadow(self, painter, scale, alpha):
        """A soft ambient shadow under the ring as a whole, echoing
        shadow.py's card look (offset down, blurred) - approximated with a
        radial gradient since a QGraphicsDropShadowEffect can't target a
        shape hand-painted inside this full-screen overlay window."""
        if alpha <= 0:
            return
        radius = style.RING_RADIUS * scale
        outer = radius + style.CARD_SHADOW_BLUR
        painter.save()
        painter.translate(self.anchor.x(), self.anchor.y() + style.CARD_SHADOW_OFFSET_Y * scale)
        color = QColor(0, 0, 0, round(style.CARD_SHADOW_ALPHA * alpha))
        gradient = QRadialGradient(0, 0, outer)
        gradient.setColorAt(radius / outer, color)
        gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(QPointF(0, 0), outer, outer)
        painter.restore()

    def paintWedge(self, painter, index, close_scale, close_alpha):
        count = len(self.wedges)
        span = 360 / count
        t = self.hover_t[index]
        chosen = index == self.chosen_wedge

        # Each exit sits at its resting pose until its own clock runs, so
        # they compose without caring which one is actually in play.
        open_scale, open_alpha = pose.open_pose(self.open_ms)
        select_scale, select_alpha, select_push = pose.select_pose(self.select_ms, chosen)
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
