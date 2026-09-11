# Qt-facing half of the edge dock: owns the real countdown QTimer and the
# one retargeted Tween that animates the card between the state machine's
# four targets - "one QPropertyAnimation, four targets", so an interrupted
# retreat moves on from wherever it actually is rather than snapping. Turns
# EdgeTrigger/ChatCard events into calls on an EdgeDock, reading/writing it
# the same way PieMenuAnimation reads/writes PieMenuState.

from PySide6.QtCore import QTimer

import style
from anims import curves
from anims.clock import Tween
from claudeEdgeDockState import EdgeDock, OPEN, COMPACT, HIDDEN, TAB


class EdgeDockDriver:
    """Qt-facing half: owns the real countdown timer and the one retargeted
    Tween that animates the card between this state machine's four targets -
    "one QPropertyAnimation, four targets", so an interrupted retreat moves
    on from wherever it actually is rather than snapping.

    `geometry_for(state)` is supplied by the caller (it needs the card's own
    stacked slot position) rather than computed here, so this class stays
    about *when* to move, not *where*.
    """

    TIMEOUT_METHOD = {
        "idle": "idle_timeout",
        "leave": "leave_timeout",
        "compact_hide": "compact_hide_timeout",
    }

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
        self.timer = QTimer(parent)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._onTimeout)
        self._armed_timer = None
        self._syncTimer()  # EdgeDock starts with its own idle timer already pending

    # --- events, one per EdgeDock input - each re-syncs the timer and,
    # if the state actually changed, re-targets the animation ---

    def enterCard(self):
        self._apply(self.dock.enter_card)

    def leaveCard(self):
        self._apply(self.dock.leave_card)

    def setStreaming(self, active):
        self._apply(self.dock.start_streaming if active else self.dock.stop_streaming)

    def setComposerFocused(self, active):
        self._apply(self.dock.focus_composer if active else self.dock.blur_composer)

    def cursorDistance(self, px):
        self._apply(lambda: self.dock.cursor_distance(px))

    def clickTab(self):
        self._apply(self.dock.click_tab)

    def clickCompact(self):
        self._apply(self.dock.click_compact)

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

    def _onTimeout(self):
        name, _ = self._armed_timer
        self._apply(getattr(self.dock, self.TIMEOUT_METHOD[name]))

    def _apply(self, mutate):
        before = self.dock.state
        mutate()
        if self.dock.state != before:
            self._moveTo(self.dock.state)
            if self.on_state_changed:
                self.on_state_changed(self.dock.state)
        self._syncTimer()

    def _moveTo(self, state):
        """Re-target the animation at `state`'s geometry, from wherever the
        card is right now - "one QPropertyAnimation, four targets", so an
        interrupted retreat moves on from where it actually is instead of
        snapping."""
        target = self.geometry_for(state)
        if not self.motion:
            self.tween.stop()
            self.current_rect = target
            return
        self.tween.run(self.current_rect, target, self._durationFor(state), curves.CHAT_FLIGHT)

    def _syncTimer(self):
        # These are idle-detection timeouts, not visual motion - they keep
        # running even with reduced motion on; only the state transitions
        # they trigger snap instead of animating.
        #
        # Called after every event, including EdgeTrigger's cursor poll
        # every 50ms while OPEN - if the pending timer hasn't actually
        # changed, leave it running. Restarting it unconditionally would
        # tear down and re-arm the 6s idle countdown on every single poll,
        # so it could never reach zero and the card would never retreat.
        armed = self.dock.pending_timer
        if armed == self._armed_timer:
            return
        self._armed_timer = armed
        self.timer.stop()
        if armed is not None:
            self.timer.start(armed[1])

    def _durationFor(self, state):
        return {
            OPEN: style.DOCK_COMPACT_MS,
            COMPACT: style.DOCK_COMPACT_MS,
            HIDDEN: style.DOCK_HIDE_MS,
            TAB: style.DOCK_TAB_SLIDE_MS,
        }[state]
