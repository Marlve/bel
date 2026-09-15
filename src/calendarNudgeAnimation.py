# Qt-facing half of the calendar nudge card: owns the slide Tween, reading/
# writing CalendarNudgeState the same way EdgeDockDriver reads/writes
# EdgeDock (claudeEdgeDockAnimation.py).
#
# `geometry_for(state)` is supplied by the caller (it needs the card's own
# screen-anchored position) rather than computed here, so this class stays
# about *when* to move, not *where*.

import style
from anims import curves
from anims.clock import Tween
from calendarNudgeState import CalendarNudgeState, QUIET, NUDGE, EXPANDED


class CalendarNudgeDriver:
    def __init__(self, parent, geometry_for, on_moved, on_state_changed=None, motion=True, on_landed=None):
        self.state = CalendarNudgeState()
        self.geometry_for = geometry_for
        self.on_moved = on_moved
        self.on_state_changed = on_state_changed
        self.on_landed = on_landed  # fires once a geometry tween reaches its target, not on every tick
        self.motion = motion
        self.current_rect = geometry_for(QUIET)

        def tick(rect):
            self.current_rect = rect
            on_moved(rect)

        self.tween = Tween(parent, tick, self._onTweenFinished)

    def show(self, items, sentence, source):
        before = self.state.state
        self.state.show(items, sentence, source)
        if self.state.state != before:
            self._moveTo(NUDGE)
            self._notify()

    def hover(self):
        before = self.state.state
        self.state.hover()
        if self.state.state != before:
            self._moveTo(EXPANDED)
            self._notify()

    def dismiss(self):
        before = self.state.state
        self.state.dismiss()
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

    def _onTweenFinished(self):
        if self.on_landed:
            self.on_landed()

    def _notify(self):
        if self.on_state_changed:
            self.on_state_changed(self.state.state)
