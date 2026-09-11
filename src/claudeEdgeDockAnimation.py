# Qt-facing half of the edge dock: owns the one retargeted Tween that
# animates the card between the state machine's targets - "one
# QPropertyAnimation, three targets", so an interrupted move continues from
# wherever it actually is rather than snapping. Turns EdgeTrigger/ChatCard
# events into calls on an EdgeDock, reading/writing it the same way
# PieMenuAnimation reads/writes PieMenuState.

import style
from anims import curves
from anims.clock import Tween
from claudeEdgeDockState import EdgeDock, OPEN, HIDDEN, TAB


class EdgeDockDriver:
    """Qt-facing half: owns the one retargeted Tween that animates the card
    between this state machine's targets - "one QPropertyAnimation, three
    targets", so an interrupted move continues from wherever it actually is
    rather than snapping.

    `geometry_for(state)` is supplied by the caller (it needs the card's own
    stacked slot position) rather than computed here, so this class stays
    about *when* to move, not *where*.
    """

    def __init__(self, parent, geometry_for, on_moved, on_state_changed=None, motion=True, on_landed=None):
        self.dock = EdgeDock()
        self.geometry_for = geometry_for
        self.on_state_changed = on_state_changed
        self.on_landed = on_landed  # fires once a geometry tween reaches its target, not on every tick
        self.motion = motion
        self.current_rect = geometry_for(OPEN)

        def tick(rect):
            self.current_rect = rect
            on_moved(rect)

        self.tween = Tween(parent, tick, self._onTweenFinished)

    # --- events, one per EdgeDock input - each re-targets the animation if
    # the state actually changed ---

    def cursorDistance(self, px):
        self._apply(lambda: self.dock.cursor_distance(px))

    def clickTab(self):
        self._apply(self.dock.click_tab)

    def minimize(self):
        self._apply(self.dock.minimize)

    def reveal(self):
        self._apply(self.dock.reveal)

    def refresh(self, duration_ms):
        """The current state's own geometry moved (e.g. a restack changed
        this card's slot) without the state itself changing - retarget the
        animation at the new geometry rather than snapping to it."""
        target = self.geometry_for(self.dock.state)
        if not self.motion:
            self.tween.stop()
            self.current_rect = target
            return
        self.tween.run(self.current_rect, target, duration_ms, curves.CHAT_FLIGHT)

    def _onTweenFinished(self):
        if self.on_landed:
            self.on_landed()

    def _apply(self, mutate):
        before = self.dock.state
        mutate()
        if self.dock.state != before:
            self._moveTo(self.dock.state)
            if self.on_state_changed:
                self.on_state_changed(self.dock.state)

    def _moveTo(self, state):
        """Re-target the animation at `state`'s geometry, from wherever the
        card is right now - "one QPropertyAnimation, three targets", so an
        interrupted move continues from where it actually is instead of
        snapping."""
        target = self.geometry_for(state)
        if not self.motion:
            self.tween.stop()
            self.current_rect = target
            return
        self.tween.run(self.current_rect, target, self._durationFor(state), curves.CHAT_FLIGHT)

    def _durationFor(self, state):
        return {
            OPEN: style.DOCK_OPEN_MS,
            HIDDEN: style.DOCK_HIDE_MS,
            TAB: style.DOCK_TAB_SLIDE_MS,
        }[state]
