# The chat card's right-edge proximity behaviour: claude-chat-flow.md's
# OPEN / COMPACT / HIDDEN / TAB state machine.
#
# EdgeDock is pure Python - no Qt import, no timers of its own - so it's
# testable without a GUI, per the spec's own deliverable list. It only
# tracks state and says which timer (if any) ought to be running; it never
# starts one. EdgeDockDriver is the Qt half: it owns the real QTimer and the
# single retargeted geometry Tween, and turns EdgeTrigger/ChatCard events
# into calls on an EdgeDock.

from PySide6.QtCore import QTimer

import style
from anims import curves
from anims.clock import Tween

OPEN, COMPACT, HIDDEN, TAB = "open", "compact", "hidden", "tab"


class EdgeDock:
    """Decides which of the four states the card is in. Three booleans -
    hovered, streaming, composer-focused - make up "busy"; the retreat
    timer never runs while any of them is true, matching claude-chat-flow.md
    ("A card that hides itself mid-sentence is indistinguishable from a
    crash."). `pending_timer` is (name, duration_ms) for whichever timer
    should currently be running, or None - the driver reads this after every
    call and starts/stops its QTimer to match.
    """

    def __init__(self):
        self.state = OPEN
        self.hovering = False
        self.streaming = False
        self.composer_focused = False
        self.ever_interacted = False  # picks the 6s idle timer vs the faster 2.5s leave timer
        self.pending_timer = None
        self._busyChanged()  # arms the initial 6s idle timer - a freshly landed card is already "idle"

    def busy(self):
        return self.hovering or self.streaming or self.composer_focused

    # --- inputs the driver feeds in ---

    def enter_card(self):
        self.hovering = True
        self._busyChanged()

    def leave_card(self):
        self.hovering = False
        self._busyChanged()

    def start_streaming(self):
        self.streaming = True
        self._busyChanged()

    def stop_streaming(self):
        self.streaming = False
        self._busyChanged()

    def focus_composer(self):
        self.composer_focused = True
        self._busyChanged()

    def blur_composer(self):
        self.composer_focused = False
        self._busyChanged()

    def cursor_distance(self, px):
        """Distance from the cursor to the dock's right edge, in px. Only
        meaningful while HIDDEN (arms the tab) or TAB (disarms it) - the
        180/260 gap between the two thresholds is the hysteresis that keeps
        a cursor resting near the boundary from flickering the tab."""
        if self.state == HIDDEN and px <= style.DOCK_ARM_PX:
            self.state = TAB
        elif self.state == TAB and px >= style.DOCK_DISARM_PX:
            self.state = HIDDEN

    def click_tab(self):
        """Hover never opens the tab - only a click does."""
        if self.state == TAB:
            self._reopen()

    def click_compact(self):
        """Same click-to-reopen affordance as the tab, for a folded puck
        left by idle retreat."""
        if self.state == COMPACT:
            self._reopen()

    def minimize(self):
        """Header button: retreat all the way to HIDDEN immediately - the
        same end state, and the same TAB-peek-then-click way back, that the
        idle/leave autohide eventually reaches on its own. Skips straight
        past COMPACT (and the busy-reopen it's subject to) since this is an
        explicit "get it out of my sight" rather than a passing idle fold."""
        if self.state == OPEN:
            self.state = HIDDEN
            self.pending_timer = None

    def reveal(self):
        """Picking the wedge again while this card's session is still alive
        resurfaces it from whatever fold state it's in - unlike click_tab()/
        click_compact(), the cursor isn't necessarily on the card afterward
        (it's wherever the ring was), so this doesn't claim hovering the way
        a real click does; enter_card()/cursor_distance() pick up the real
        position on their own once the cursor actually gets there."""
        if self.state != OPEN:
            self.state = OPEN
            self._busyChanged()

    # --- timers, fired by the driver once its QTimer elapses ---

    def idle_timeout(self):
        self._retreat()

    def leave_timeout(self):
        self._retreat()

    def compact_hide_timeout(self):
        if self.state == COMPACT and not self.busy():
            self.state = HIDDEN
            self.pending_timer = None

    # --- internals ---

    def _reopen(self):
        self.state = OPEN
        self.hovering = True  # the click landed on the card; the cursor is right there
        self._busyChanged()

    def _foldToCompact(self):
        self.state = COMPACT
        self.pending_timer = ("compact_hide", style.DOCK_COMPACT_TO_HIDE_DELAY_MS)

    def _retreat(self):
        if self.state == OPEN and not self.busy():
            self._foldToCompact()

    def _busyChanged(self):
        if self.busy():
            self.ever_interacted = True
            if self.state == COMPACT and (self.streaming or self.composer_focused):
                # Genuinely busy, not just a passing hover - reopen it rather
                # than let it finish retreating out from under a live reply.
                self.state = OPEN
            self.pending_timer = None  # a plain hover still pauses the hide countdown
            return

        if self.state == OPEN:
            duration = style.DOCK_LEAVE_MS if self.ever_interacted else style.DOCK_IDLE_MS
            self.pending_timer = ("leave" if self.ever_interacted else "idle", duration)
        elif self.state == COMPACT:
            # A hover that didn't turn out to be genuine business (streaming,
            # composer focus) just grazed the puck - resume the countdown to
            # HIDDEN rather than sitting compact forever.
            self.pending_timer = ("compact_hide", style.DOCK_COMPACT_TO_HIDE_DELAY_MS)
        # HIDDEN/TAB don't run this timer at all.
  

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
