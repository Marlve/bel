# Pure state machine for the calendar nudge card - calendar-nudge.md's own
# flow: Quiet (rail, nothing visible) -> Nudge (slides out, times out after
# style.NUDGE_RETIRE_MS if untouched) -> Expand (hovering reveals the item
# list) -> Gone, which collapses back to the same rail Quiet already is -
# "snoozed and ignored both end here" per the spec, so there's no separate
# terminal state to track: both retire() (timeout) and leave() (mouse
# leaving an expanded nudge) land back on QUIET.
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

    def leave(self):
        """Mouse leaving an expanded nudge closes it outright -
        calendar-nudge.md has no accept flow, so there's nothing left to do
        with a nudge once it's been looked at."""
        if self.state == EXPANDED:
            self._retreat()

    def retire(self):
        """The 12s untouched timeout - a no-op once EXPANDED, since hovering
        already stops the timer on the animation side."""
        if self.state == NUDGE:
            self._retreat()

    def _retreat(self):
        self.state = QUIET
        self.items = []
        self.sentence = ""
        self.source = ""
