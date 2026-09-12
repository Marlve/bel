# Qt-facing half of the chat card: owns every Clock/Tween (the flight from
# the prompt bar, the dismiss fade, the TAB tilt) plus the edge-dock
# driver/trigger, and the tick-fed values (radius/tilt) the view paints
# from. Writes into ChatCardState the same way EdgeDockDriver reads/writes
# EdgeDock - never painted directly, reaches back into the view (parent)
# only for the handful of things that are genuinely its job: moving/sizing
# the window, and the couple of named view methods (setCompactVisual,
# focusComposerIfPending, onLanded, onFaded) that a landed/faded/dock-state
# transition needs to trigger.

import math

from PySide6.QtCore import QPointF, QRectF, QVariantAnimation
from PySide6.QtGui import QTransform

import style
from anims import curves, pose
from anims.clock import Clock, Tween
from claudeEdgeDockState import OPEN, HIDDEN, TAB
from claudeEdgeDockAnimation import EdgeDockDriver
from claudeEdgeTrigger import EdgeTrigger


def _tabFootprint():
    """The window footprint TAB needs to show the puck rotated without
    clipping it. claude-chat-flow.md hinges the tilt on the puck's own right
    edge, not its centre, so the swept bounding box is asymmetric - a plain
    size*(|cos|+|sin|) square (correct only for a centre-pivot rotation) and
    a symmetric inset clips the far corner (the bottom edge, at -9deg)."""
    size = style.DOCK_COMPACT_SIZE
    pivot = QPointF(size, size / 2)  # right-edge midpoint, puck's own top-left as local origin
    transform = QTransform().translate(pivot.x(), pivot.y()).rotate(style.DOCK_TAB_ROTATION_DEG).translate(
        -pivot.x(), -pivot.y()
    )
    swept = transform.mapRect(QRectF(0, 0, size, size))
    return math.ceil(swept.width()), math.ceil(swept.height()), math.ceil(-swept.left()), math.ceil(-swept.top())


TAB_WIDTH, TAB_HEIGHT, TAB_LEFT_INSET, TAB_TOP_INSET = _tabFootprint()


class ChatCardAnimation:
    def __init__(self, parent, state, born, screen, motion):
        self.parent = parent
        self.state = state
        self.born = born  # the prompt bar's rect the flight starts from
        self.screen = screen
        self.motion = motion

        self.radius = min(born.width(), born.height()) / 2
        self.tilt = 0.0  # degrees, animated separately from the dock slide (claude-chat-flow.md's "260 ms rotation")

        self.flight = Clock(parent, self.onFlightTick, parent.onLanded)
        self.fade = Tween(parent, self.onFadeTick, parent.onFaded)
        self.tilt_tween = Tween(parent, self.onTiltTick)

        self.edge_driver = None
        self.edge_trigger = None

    # --- the flight from the prompt bar ---

    def flying(self):
        return self.flight.state() == QVariantAnimation.Running

    def onFlightTick(self, ms):
        self.parent.setGeometry(pose.lerp_rect(self.born, self.state.dock_rect, pose.card_flight_progress(ms)).toRect())
        self.radius = pose.card_radius(ms, min(self.born.width(), self.born.height()) / 2)
        self.parent.update()

    def land(self):
        """Called once the flight (or, with motion off, ChatCard.fly()
        itself) reaches the dock - starts tracking the right-edge dock
        state now that there's a real docked geometry to animate between."""
        self.radius = style.CHAT_RADIUS
        self.edge_driver = EdgeDockDriver(
            self.parent, self.geometryFor, self.onDockMoved, self.onDockStateChanged, self.motion,
            on_landed=self.onDockLanded,
        )
        self.edge_trigger = EdgeTrigger(self.onEdgeDistance, self.screen)

    # --- the edge dock ---

    def geometryFor(self, dock_state):
        r = self.state.dock_rect
        area = self.screen.availableGeometry()
        edge = area.x() + area.width()
        size = style.DOCK_COMPACT_SIZE
        if dock_state == OPEN:
            return QRectF(r)
        if dock_state == HIDDEN:
            return QRectF(edge, r.top(), size, size)
        return QRectF(
            edge - style.DOCK_TAB_VISIBLE_PX - TAB_LEFT_INSET,
            r.top() - TAB_TOP_INSET,
            TAB_WIDTH,
            TAB_HEIGHT,
        )

    def onDockMoved(self, rect):
        self.parent.setGeometry(rect.toRect())

    def onDockStateChanged(self, dock_state):
        # Reaching OPEN is the one transition where content becomes visible
        # rather than hidden - deferred to onDockLanded() so the labels don't
        # reflow every frame while the window is still growing from a
        # HIDDEN/TAB-sized footprint up to full size (same reasoning as
        # onChunk() buffering text until the flight animation is done).
        if dock_state != OPEN or not self.motion:
            self.parent.setCompactVisual(dock_state in (TAB, HIDDEN))
        self.radius = style.CHAT_RADIUS
        target_tilt = style.DOCK_TAB_ROTATION_DEG if dock_state == TAB else 0.0
        if self.motion:
            self.tilt_tween.run(self.tilt, target_tilt, style.DOCK_TAB_ROTATE_MS, curves.CHAT_FLIGHT)
        else:
            self.tilt = target_tilt
        self.parent.update()

    def onDockLanded(self):
        if self.edge_driver and self.edge_driver.dock.state == OPEN:
            self.parent.setCompactVisual(False)
            self.parent.focusComposerIfPending()

    def onTiltTick(self, value):
        self.tilt = value
        self.parent.update()

    def onEdgeDistance(self, px):
        if self.edge_driver:
            self.edge_driver.cursorDistance(px)

    def stopDynamics(self):
        """Cancel the edge-dock timer and tween - shared by ChatCard.dismiss()
        and ChatSlot.retire(), the two teardown paths, so a stray poll or a
        reveal's still-running tween can't land after teardown starts."""
        if self.edge_trigger:
            self.edge_trigger.stop()
        if self.edge_driver:
            self.edge_driver.stop()

    def isTabbed(self):
        return self.edge_driver is not None and self.edge_driver.dock.state == TAB

    def isOpen(self):
        return self.edge_driver is not None and self.edge_driver.dock.state == OPEN

    def puckRect(self):
        """The puck's own rect within the card. Scales the TAB insets by
        how far the geometry tween has grown from HIDDEN's bare size*size
        window towards TAB's full (asymmetric) footprint, so the
        puck tracks smoothly mid-transition instead of jumping to its final
        offset the instant TAB is reached."""
        size = style.DOCK_COMPACT_SIZE
        span = TAB_WIDTH - size
        t = max(0.0, min(1.0, (self.parent.width() - size) / span)) if span else 1.0
        return QRectF(TAB_LEFT_INSET * t, TAB_TOP_INSET * t, size, size)

    def tabPivot(self):
        """claude-chat-flow.md: TAB is 'hinged on its right edge' - the pivot
        is the puck's own right-edge midpoint, not the window centre."""
        puck = self.puckRect()
        return QPointF(puck.right(), puck.center().y())

    def tabContains(self, pos):
        pivot = self.tabPivot()
        inverse, ok = QTransform().translate(pivot.x(), pivot.y()).rotate(-style.DOCK_TAB_ROTATION_DEG).translate(
            -pivot.x(), -pivot.y()
        ).inverted()
        local = inverse.map(pos) if ok else pos
        return self.puckRect().contains(local)

    # --- leaving ---

    def onFadeTick(self, t):
        self.parent.setWindowOpacity(t)
        travelled = round((1 - t) * style.CHAT_DISMISS_SLIDE)
        rect = self.state.dock_rect.toRect()
        self.parent.move(rect.x() + travelled, rect.y())
