# The chat card's right-edge proximity behaviour: claude-chat-flow.md's
# OPEN / HIDDEN / TAB state machine. Pure Python - no Qt import, no timers
# of its own - so it's testable without a GUI, per the spec's own
# deliverable list. claudeEdgeDockAnimation.py's EdgeDockDriver is the Qt
# half that reads/writes this and turns EdgeTrigger/ChatCard events into
# calls on it.

import style

OPEN, HIDDEN, TAB = "open", "hidden", "tab"


class EdgeDock:
    """Decides which of the three states the card is in. There is no
    automatic retreat - OPEN only ever becomes HIDDEN via an explicit
    minimize(); TAB is just a peek of the puck while HIDDEN and the cursor
    is near the edge, and only a click on it reopens the card."""

    def __init__(self):
        self.state = OPEN

    # --- inputs the driver feeds in ---

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
            self.state = OPEN

    def minimize(self):
        """Header button: the only way OPEN becomes HIDDEN."""
        if self.state == OPEN:
            self.state = HIDDEN

    def reveal(self):
        """Picking the wedge again while this card's session is still alive
        resurfaces it from HIDDEN/TAB."""
        if self.state != OPEN:
            self.state = OPEN
