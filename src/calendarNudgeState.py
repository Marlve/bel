# Pure state machine for the calendar nudge card: Quiet (rail, nothing
# visible) -> Nudge (slides out) -> Expand (hovering reveals the item list)
# -> Gone, which collapses back to the same rail Quiet already is. The card
# stays on screen (nudge or expanded, whichever it's in) until dismiss()
# fires - a click - so there's no timeout and hovering away doesn't close it.
#
# No Qt import, no timers of its own - CalendarNudgeAnimation is the Qt half
# that reads/writes this, mirroring claudeEdgeDockState.py's split.

QUIET, NUDGE, EXPANDED = "quiet", "nudge", "expanded"


class CalendarNudgeState:
    def __init__(self):
        self.state = QUIET
        self.items = []
        self.sentence = ""
        self.source = ""

    def show(self, items, sentence, source):
        """Only fires from QUIET - a nudge already on screen keeps running
        rather than being restarted or swapped out underneath whoever is
        looking at it."""
        if self.state != QUIET:
            return
        self.items = items
        self.sentence = sentence
        self.source = source
        self.state = NUDGE

    def hover(self):
        if self.state == NUDGE:
            self.state = EXPANDED

    def dismiss(self):
        """A click, from either NUDGE or EXPANDED - calendar-nudge.md has no
        accept flow, so there's nothing left to do with a nudge once the
        user has clicked it away."""
        if self.state != QUIET:
            self._retreat()

    def _retreat(self):
        self.state = QUIET
        self.items = []
        self.sentence = ""
        self.source = ""
