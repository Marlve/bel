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

    def test_dismiss_closes_an_expanded_nudge_back_to_quiet(self):
        state = CalendarNudgeState()
        state.show(ITEMS, "sentence", "source")
        state.hover()
        state.dismiss()
        self.assertEqual(state.state, QUIET)
        self.assertEqual(state.items, [])

    def test_dismiss_closes_a_bare_nudge_back_to_quiet(self):
        # A click on an un-hovered nudge (not yet expanded) also dismisses it -
        # there's no separate timeout path any more, only a click.
        state = CalendarNudgeState()
        state.show(ITEMS, "sentence", "source")
        state.dismiss()
        self.assertEqual(state.state, QUIET)
        self.assertEqual(state.items, [])

    def test_dismiss_is_a_no_op_from_quiet(self):
        state = CalendarNudgeState()
        state.dismiss()
        self.assertEqual(state.state, QUIET)


if __name__ == "__main__":
    unittest.main()
