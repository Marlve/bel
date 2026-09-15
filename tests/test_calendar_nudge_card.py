import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontMetricsF

from calendarNudgeCard import CalendarNudgeCard, elidedTitle, wrappedTextHeight, buildFont
from calendarNudgeState import QUIET, NUDGE, EXPANDED
import style

ITEMS = [{"title": "Essay draft", "due": "Fri"}]


class CalendarNudgeCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.card = CalendarNudgeCard(motion=False)
        self.addCleanup(self.card.deleteLater)

    def test_starts_quiet_at_rail_width(self):
        self.assertEqual(self.card.driver.state.state, QUIET)
        self.assertEqual(self.card.width(), style_rail_size())

    def test_show_nudge_builds_the_default_tone_sentence_and_widens(self):
        self.card.showNudge(ITEMS, "Friday")
        self.assertEqual(self.card.driver.state.state, NUDGE)
        self.assertEqual(self.card.driver.state.sentence, "One assignment is due before Friday.")
        self.assertEqual(self.card.driver.state.source, "from calendar · 1 item")
        self.assertGreater(self.card.width(), 5)

    def test_hover_expands_and_grows_taller(self):
        self.card.showNudge(ITEMS, "Friday")
        nudge_height = self.card.height()
        self.card.enterEvent(None)
        self.assertEqual(self.card.driver.state.state, EXPANDED)
        self.assertGreater(self.card.height(), nudge_height)

    def test_leave_after_hover_does_not_collapse(self):
        self.card.showNudge(ITEMS, "Friday")
        self.card.enterEvent(None)
        self.card.leaveEvent(None)
        self.assertEqual(self.card.driver.state.state, EXPANDED)

    def test_click_on_expanded_body_does_not_dismiss(self):
        self.card.showNudge(ITEMS, "Friday")
        self.card.enterEvent(None)
        self.card.mousePressEvent(None)
        self.assertEqual(self.card.driver.state.state, EXPANDED)

    def test_click_on_a_bare_nudge_body_does_not_dismiss(self):
        self.card.showNudge(ITEMS, "Friday")
        self.card.mousePressEvent(None)
        self.assertEqual(self.card.driver.state.state, NUDGE)

    def test_close_button_hidden_while_quiet(self):
        self.assertFalse(self.card.close_button.isVisible())

    def test_close_button_shown_on_nudge(self):
        self.card.showNudge(ITEMS, "Friday")
        self.assertTrue(self.card.close_button.isVisible())

    def test_close_button_click_dismisses_to_quiet(self):
        self.card.showNudge(ITEMS, "Friday")
        self.card.close_button.click()
        self.assertEqual(self.card.driver.state.state, QUIET)
        self.assertFalse(self.card.close_button.isVisible())

    def test_expanded_height_leaves_a_bottom_margin_after_the_last_item(self):
        # Independently derives the expected height from raw font metrics and
        # style constants, rather than re-calling the code under test, so it
        # actually catches the pad-before-items swallowing the pad-after-items.
        self.card.showNudge(ITEMS, "Friday")
        self.card.enterEvent(None)
        font = buildFont()
        pad = style.SPACE_2
        content_width = style.NUDGE_WIDTH - 2 * pad
        sentence_h = wrappedTextHeight(self.card.driver.state.sentence, content_width, font)
        source_h = QFontMetricsF(font).height()
        top = pad + self.card.close_button.height() + style.SPACE_1  # close button's row
        expected = (
            top + sentence_h + style.SPACE_1 + source_h  # top through the source line
            + pad  # gap before the item list
            + len(ITEMS) * style.NUDGE_ITEM_ROW_HEIGHT  # item rows
            + pad  # bottom margin after the last item
        )
        self.assertEqual(self.card.height(), expected)

    def test_nudge_height_grows_to_fit_a_longer_wrapped_sentence(self):
        self.card.showNudge(ITEMS, "Fri")
        short_height = self.card.height()
        self.card.driver.dismiss()
        long_before = "a date so far in the future this sentence needs three whole lines to fit"
        self.card.showNudge(ITEMS, long_before)
        self.assertGreater(self.card.height(), short_height)


class CalendarNudgeCardRetreatAnimationTests(unittest.TestCase):
    """Dismiss must keep painting the card's last content while the slide
    back to the rail is in flight (calendar-nudge.md's "Gone" step) - it
    used to go blank the instant the close button was clicked, well before
    the geometry tween finished, per .scratch/calendar-nudge/issues/06."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.card = CalendarNudgeCard(motion=True)
        self.addCleanup(self.card.deleteLater)

    def test_dismiss_snapshots_the_live_content_for_the_retreat_tween(self):
        self.card.showNudge(ITEMS, "Friday")
        live = self.card.driver.state
        expected = (NUDGE, live.items, live.sentence, live.source)

        self.card.close_button.click()

        self.assertEqual(self.card.driver.state.state, QUIET)  # logical state lands immediately
        self.assertEqual(self.card.retreat_snapshot, expected)  # but the snapshot keeps the old content around

    def test_dismiss_from_expanded_snapshots_the_expanded_state_too(self):
        self.card.showNudge(ITEMS, "Friday")
        self.card.enterEvent(None)

        self.card.close_button.click()

        self.assertEqual(self.card.retreat_snapshot[0], EXPANDED)
        self.assertEqual(self.card.retreat_snapshot[1], ITEMS)

    def test_landing_at_quiet_drops_the_snapshot(self):
        self.card.showNudge(ITEMS, "Friday")
        self.card.close_button.click()
        self.assertIsNotNone(self.card.retreat_snapshot)

        self.card.onLanded()  # simulates the retreat tween reaching QUIET's geometry

        self.assertIsNone(self.card.retreat_snapshot)

    def test_landing_while_still_showing_does_not_touch_the_snapshot(self):
        # onLanded also fires for the entrance tween reaching NUDGE - it must
        # only clear the snapshot once the state is actually back to QUIET.
        self.card.showNudge(ITEMS, "Friday")

        self.card.onLanded()

        self.assertIsNone(self.card.retreat_snapshot)  # nothing to drop yet, and no crash

    def test_dismiss_with_motion_off_never_snapshots(self):
        quiet_card = CalendarNudgeCard(motion=False)
        self.addCleanup(quiet_card.deleteLater)
        quiet_card.showNudge(ITEMS, "Friday")

        quiet_card.close_button.click()

        self.assertIsNone(quiet_card.retreat_snapshot)


class ElidedTitleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_a_title_too_long_to_share_the_row_with_its_due_label_is_elided(self):
        font = QFont(style.FONT_FAMILY)
        font.setPointSizeF(style.FONT_SIZE)
        content_width = style.NUDGE_WIDTH - 2 * style.SPACE_2
        title = "Software Engineering Group Project Report"
        due = "tomorrow"
        elided = elidedTitle(title, due, content_width, font)
        self.assertNotEqual(elided, title)
        fm = QFontMetricsF(font)
        available = content_width - fm.horizontalAdvance(due) - style.SPACE_1
        self.assertLessEqual(fm.horizontalAdvance(elided), available)

    def test_a_short_title_is_left_untouched(self):
        font = QFont(style.FONT_FAMILY)
        font.setPointSizeF(style.FONT_SIZE)
        content_width = style.NUDGE_WIDTH - 2 * style.SPACE_2
        elided = elidedTitle("Essay draft", "Fri", content_width, font)
        self.assertEqual(elided, "Essay draft")


def style_rail_size():
    import style
    return style.NUDGE_RAIL_SIZE


if __name__ == "__main__":
    unittest.main()
