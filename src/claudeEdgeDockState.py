# The chat card's right-edge proximity behaviour: claude-chat-flow.md's
# OPEN / COMPACT / HIDDEN / TAB state machine. Pure Python - no Qt import,
# no timers of its own - so it's testable without a GUI, per the spec's own
# deliverable list. It only tracks state and says which timer (if any)
# ought to be running; it never starts one. claudeEdgeDockAnimation.py's
# EdgeDockDriver is the Qt half that reads/writes this and turns
# EdgeTrigger/ChatCard events into calls on it.

import style

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
