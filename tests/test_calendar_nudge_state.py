import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from calendarNudgeState import CalendarNudgeState, QUIET, NUDGE, EXPANDED


ITEMS = [{"title": "Essay draft", "due": "Fri"}]


class CalendarNudgeStateTests(unittest.TestCase):
    def test_a_fresh_state_starts_quiet(self):
        state = CalendarNudgeState()
        self.assertEqual(state.state, QUIET)

    def test_show_moves_to_nudge_and_stores_the_content(self):
        state = CalendarNudgeState()
        state.show(ITEMS, "sentence", "source")
        self.assertEqual(state.state, NUDGE)
        self.assertEqual(state.items, ITEMS)
        self.assertEqual(state.sentence, "sentence")
        self.assertEqual(state.source, "source")

    def test_show_is_a_no_op_once_already_showing(self):
        # A second startup query result should never yank the currently
        # displayed nudge out from under whoever is looking at it.
        state = CalendarNudgeState()
        state.show(ITEMS, "sentence", "source")
        state.show([{"title": "Other", "due": "Mon"}], "other", "other source")
        self.assertEqual(state.items, ITEMS)
        self.assertEqual(state.sentence, "sentence")

    def test_hover_expands_from_nudge(self):
        state = CalendarNudgeState()
        state.show(ITEMS, "sentence", "source")
        state.hover()
        self.assertEqual(state.state, EXPANDED)

    def test_hover_is_a_no_op_from_quiet(self):
        state = CalendarNudgeState()
        state.hover()
        self.assertEqual(state.state, QUIET)

    def test_leave_closes_an_expanded_nudge_back_to_quiet(self):
        state = CalendarNudgeState()
        state.show(ITEMS, "sentence", "source")
        state.hover()
        state.leave()
        self.assertEqual(state.state, QUIET)
        self.assertEqual(state.items, [])

    def test_leave_is_a_no_op_from_nudge(self):
        # Only expand (hover) is closed by leaving - a bare nudge (not yet
        # hovered) only ever ends via retire(), never leave().
        state = CalendarNudgeState()
        state.show(ITEMS, "sentence", "source")
        state.leave()
        self.assertEqual(state.state, NUDGE)

    def test_retire_closes_an_untouched_nudge_back_to_quiet(self):
        state = CalendarNudgeState()
        state.show(ITEMS, "sentence", "source")
        state.retire()
        self.assertEqual(state.state, QUIET)
        self.assertEqual(state.items, [])

    def test_retire_is_a_no_op_once_expanded(self):
        # Hovering already stops the timeout on the animation side; this
        # guards the state machine itself against a stray retire() call
        # arriving after that.
        state = CalendarNudgeState()
        state.show(ITEMS, "sentence", "source")
        state.hover()
        state.retire()
        self.assertEqual(state.state, EXPANDED)


if __name__ == "__main__":
    unittest.main()
