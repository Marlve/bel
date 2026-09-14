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
from PySide6.QtWidgets import QApplication

import dockCorner
import screenBounds
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
        self.typing_clock = Clock(parent, self.onTypingTick, lambda: None)
        self.typing_label = None

        self.edge_driver = None
        self.edge_trigger = None

        self.drag_press_pos = None
        self.drag_window_pos = None
        self.drag_active = False

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
        self.edge_trigger = EdgeTrigger(self.onEdgeDistance, self.screen, left=dockCorner.is_left(self.state.corner))

    # --- the pre-reply typing indicator: fills the gap between send() and
    # the first onChunk(), see chat-bubble-polish/01 ---

    def startTyping(self, label):
        self.typing_label = label
        if self.motion:
            self.typing_clock.run(style.CHAT_TYPING_PERIOD_MS, loop=True)
        else:
            self.renderTypingDots((1.0, 1.0, 1.0))

    def stopTyping(self):
        if self.typing_label is None:
            return
        self.typing_clock.stop()
        self.typing_label = None

    def onTypingTick(self, ms):
        self.renderTypingDots(pose.typing_dot_pose(ms, style.CHAT_TYPING_PERIOD_MS))

    def renderTypingDots(self, brightnesses):
        if self.typing_label is None:
            return
        dots = " ".join(
            f'<span style="color:{pose.mix(style.MUTED, style.CHAT_ACCENT, b).name()};">•</span>'
            for b in brightnesses
        )
        self.typing_label.setText(dots)

    # --- the edge dock ---

    def geometryFor(self, dock_state):
        r = self.state.dock_rect
        area = self.screen.availableGeometry()
        left = dockCorner.is_left(self.state.corner)
        edge = area.x() if left else area.x() + area.width()
        size = style.DOCK_COMPACT_SIZE
        if dock_state == OPEN:
            return QRectF(r)
        if dock_state == HIDDEN:
            # Slides fully past its own edge either way - off the left side
            # of the screen for a left-docked corner, off the right for a
            # right-docked one.
            x = edge - size if left else edge
            return QRectF(x, r.top(), size, size)
        # TAB: the same peek math as the right-edge case, mirrored about
        # `edge` for a left-docked corner - see dockCorner.py's docstring
        # and puckRect()/tabPivot() below for the matching paint-side mirror.
        x = (
            edge + style.DOCK_TAB_VISIBLE_PX + TAB_LEFT_INSET - TAB_WIDTH
            if left
            else edge - style.DOCK_TAB_VISIBLE_PX - TAB_LEFT_INSET
        )
        return QRectF(x, r.top() - TAB_TOP_INSET, TAB_WIDTH, TAB_HEIGHT)

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
        if dock_state == TAB:
            # Mirrored for a left-docked corner so the tab visually leans
            # into its own edge, not the right edge's direction.
            sign = -1.0 if dockCorner.is_left(self.state.corner) else 1.0
            target_tilt = style.DOCK_TAB_ROTATION_DEG * sign
        else:
            target_tilt = 0.0
        if self.motion:
            self.tilt_tween.run(self.tilt, target_tilt, style.DOCK_TAB_ROTATE_MS, curves.CHAT_FLIGHT)
        else:
            self.tilt = target_tilt
        self.parent.update()

    def onDockLanded(self):
        if self.edge_driver and self.edge_driver.dock.state == OPEN:
            self.parent.setCompactVisual(False)
            # Showing scroll/composer invalidates the layout but Qt doesn't
            # relayout synchronously - without forcing it here, the next
            # paintFrame() can read their pre-relayout position (same
            # stale-layout hazard onLanded() already guards against for the
            # first-ever open).
            self.parent.layout().activate()
            self.parent.focusComposerIfPending()
            self.parent.update()

    def onTiltTick(self, value):
        self.tilt = value
        self.parent.update()

    def onEdgeDistance(self, px):
        if self.edge_driver:
            self.edge_driver.cursorDistance(px)

    # --- drag-and-snap: dragging the header magnetically re-docks the card
    # to whichever of the 4 corners it's released nearest to, rather than
    # free placement like the todo/note cards - see chat-dock-corners/01. ---

    def dragPress(self, global_pos):
        self.drag_press_pos = global_pos
        self.drag_window_pos = QPointF(self.parent.pos())
        self.drag_active = False

    def dragMove(self, global_pos):
        """Follows the cursor 1:1 like a normal window drag, clamped to
        whichever screen it's over - the actual corner isn't picked until
        release (dragRelease), unlike WindowDrag's own free-placement clamp
        (draggable.py), so this is deliberately a new, smaller gesture
        rather than a reuse of that class."""
        if self.drag_press_pos is None:
            return
        delta = global_pos - self.drag_press_pos
        if not self.drag_active and delta.x() ** 2 + delta.y() ** 2 < style.CARD_DRAG_THRESHOLD_PX ** 2:
            return
        self.drag_active = True
        target = (self.drag_window_pos + delta).toPoint()
        area = screenBounds.available_area(global_pos.toPoint(), margin=style.CHAT_MARGIN)
        x = screenBounds.clamp(target.x(), area.x(), area.x() + area.width() - self.parent.width())
        y = screenBounds.clamp(target.y(), area.y(), area.y() + area.height() - self.parent.height())
        self.parent.move(x, y)

    def dragRelease(self, global_pos):
        was_dragging = self.drag_active
        self.drag_press_pos = None
        self.drag_active = False
        if not was_dragging:
            return
        # dragMove() already re-resolves the screen under the cursor on
        # every move (via screenBounds) to clamp correctly on whatever
        # monitor it's over - keep self.screen in step too, or the corner
        # pick, dockToCorner()'s geometry, and the new EdgeTrigger would all
        # silently stay pinned to whichever monitor the card started on.
        self.screen = QApplication.screenAt(global_pos.toPoint()) or self.screen
        area = self.screen.availableGeometry()
        # The card's own (clamped) center, not the raw cursor - dragMove()
        # lets the cursor run ahead of a clamped card near an edge, so
        # picking by cursor alone could lock a corner the card no longer
        # visually looks closest to.
        self.dockToCorner(dockCorner.nearest(self.parent.geometry().center(), area))

    def dockToCorner(self, corner):
        """Re-targets OPEN's own resting geometry at `corner` and animates
        (or, with motion off, jumps) there from wherever the card actually
        is - reuses EdgeDockDriver.refresh() (until now an unused escape
        hatch for exactly this "the current state's geometry moved" case)
        rather than a second tween class."""
        area = self.screen.availableGeometry()
        self.state.corner = corner
        self.state.dock_rect = dockCorner.rect(corner, area, style.CHAT_SIZE, style.CHAT_MARGIN)
        self.parent.onCornerChanged(corner)

        if self.edge_trigger:
            self.edge_trigger.stop()
            self.edge_trigger = EdgeTrigger(self.onEdgeDistance, self.screen, left=dockCorner.is_left(corner))
        if self.edge_driver:
            # The live drag (dragMove) moved the window directly, bypassing
            # the driver entirely - its own current_rect bookkeeping is
            # still wherever OPEN last was before the drag, not the actual
            # drop point. Sync it first or refresh() below tweens from that
            # stale rect, visibly snapping back to the old corner an instant
            # before animating out to the new one.
            self.edge_driver.current_rect = QRectF(self.parent.geometry())
            self.edge_driver.refresh(style.CHAT_DOCK_SNAP_MS, curves.CHAT_DOCK_SNAP)
            if not self.motion:
                # refresh() only updates its own bookkeeping when motion is
                # off, without moving the window (it was never called with
                # motion off before this) - land it explicitly.
                self.parent.setGeometry(self.state.dock_rect.toRect())

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
        offset the instant TAB is reached.

        For a right-docked corner the window grows to the left while the
        puck stays flush with the window's own right edge (local x grows
        with `t`). Mirrored for a left-docked corner: the window's own
        local origin already sits on the hinge side, so the puck stays
        flush at local x=0 for every `t` - see claudeChatCardAnimation.py's
        geometryFor() docstring for the matching window-rect mirror this
        keeps in step with."""
        size = style.DOCK_COMPACT_SIZE
        span = TAB_WIDTH - size
        t = max(0.0, min(1.0, (self.parent.width() - size) / span)) if span else 1.0
        x = 0.0 if dockCorner.is_left(self.state.corner) else TAB_LEFT_INSET * t
        return QRectF(x, TAB_TOP_INSET * t, size, size)

    def tabPivot(self):
        """claude-chat-flow.md: TAB is 'hinged on its own edge' - the pivot
        is the puck's own edge-side midpoint (right for a right-docked
        corner, left for a left-docked one), not the window centre."""
        puck = self.puckRect()
        x = puck.left() if dockCorner.is_left(self.state.corner) else puck.right()
        return QPointF(x, puck.center().y())

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
