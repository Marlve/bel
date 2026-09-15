# Qt-facing half of the calendar nudge card: owns the slide Tween and the
# 12s auto-retire QTimer, reading/writing CalendarNudgeState the same way
# EdgeDockDriver reads/writes EdgeDock (claudeEdgeDockAnimation.py).
#
# `geometry_for(state)` is supplied by the caller (it needs the card's own
# screen-anchored position) rather than computed here, so this class stays
# about *when* to move, not *where*.

from PySide6.QtCore import QTimer

import style
from anims import curves
from anims.clock import Tween
from calendarNudgeState import CalendarNudgeState, QUIET, NUDGE, EXPANDED


class CalendarNudgeDriver:
    def __init__(self, parent, geometry_for, on_moved, on_state_changed=None, motion=True):
        self.state = CalendarNudgeState()
        self.geometry_for = geometry_for
        self.on_moved = on_moved
        self.on_state_changed = on_state_changed
        self.motion = motion
        self.current_rect = geometry_for(QUIET)

        def tick(rect):
            self.current_rect = rect
            on_moved(rect)

        self.tween = Tween(parent, tick)

        self.retire_timer = QTimer(parent)
        self.retire_timer.setSingleShot(True)
        self.retire_timer.timeout.connect(self._onRetireTimeout)

    def show(self, items, sentence, source):
        before = self.state.state
        self.state.show(items, sentence, source)
        if self.state.state != before:
            self._moveTo(NUDGE)
            self.retire_timer.start(style.NUDGE_RETIRE_MS)
            self._notify()

    def hover(self):
        before = self.state.state
        self.state.hover()
        if self.state.state != before:
            self.retire_timer.stop()  # being looked at - no time limit
            self._moveTo(EXPANDED)
            self._notify()

    def leave(self):
        before = self.state.state
        self.state.leave()
        if self.state.state != before:
            self._moveTo(QUIET)
            self._notify()

    def _onRetireTimeout(self):
        before = self.state.state
        self.state.retire()
        if self.state.state != before:
            self._moveTo(QUIET)
            self._notify()

    def _moveTo(self, state):
        target = self.geometry_for(state)
        if not self.motion:
            self.tween.stop()
            self.current_rect = target
            self.on_moved(target)  # no animation to tick through, so apply the target directly
            return
        self.tween.run(self.current_rect, target, style.NUDGE_SLIDE_MS, curves.NUDGE_SLIDE)

    def _notify(self):
        if self.on_state_changed:
            self.on_state_changed(self.state.state)
