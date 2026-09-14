import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtCore import QRectF

import style
from anims.pose import (
    bisector,
    open_pose,
    open_total_ms,
    scrim_progress,
    hover_pose,
    select_pose,
    select_total_ms,
    close_pose,
    ring_exit_pose,
    grow_progress,
    crossfade_progress,
    field_progress,
    geometry_rest_ms,
    handoff_total_ms,
    lerp_rect,
    card_flight_progress,
    card_radius,
    typing_dot_pose,
)

R = style.RING_RADIUS


class BisectorTests(unittest.TestCase):
    # Unit vector pointing out through the middle of a wedge, in screen
    # space (y grows downward). Wedge 0 is up, winding clockwise.

    def test_up(self):
        bx, by = bisector(0, 4)
        self.assertAlmostEqual(bx, 0)
        self.assertAlmostEqual(by, -1)

    def test_right(self):
        bx, by = bisector(1, 4)
        self.assertAlmostEqual(bx, 1)
        self.assertAlmostEqual(by, 0)

    def test_down(self):
        bx, by = bisector(2, 4)
        self.assertAlmostEqual(bx, 0)
        self.assertAlmostEqual(by, 1)

    def test_left(self):
        bx, by = bisector(3, 4)
        self.assertAlmostEqual(bx, -1)
        self.assertAlmostEqual(by, 0)


class OpenPoseTests(unittest.TestCase):
    def test_starts_small_and_invisible(self):
        scale, alpha = open_pose(0)
        self.assertAlmostEqual(scale, style.OPEN_SCALE_FROM)
        self.assertAlmostEqual(alpha, 0)

    def test_ends_at_rest(self):
        scale, alpha = open_pose(style.OPEN_MS)
        self.assertAlmostEqual(scale, 1)
        self.assertAlmostEqual(alpha, 1)

    def test_clamps_past_the_end(self):
        self.assertEqual(open_pose(style.OPEN_MS * 3), (1, 1))

    def test_opacity_lands_before_scale(self):
        scale, alpha = open_pose(style.OPEN_FADE_MS)
        self.assertAlmostEqual(alpha, 1)
        self.assertNotAlmostEqual(scale, 1)

    def test_scale_overshoots_before_settling(self):
        peak = max(open_pose(t)[0] for t in range(0, style.OPEN_MS))
        self.assertGreater(peak, 1)

    def test_total_is_just_the_open_duration(self):
        self.assertEqual(open_total_ms(), style.OPEN_MS)


class ScrimTests(unittest.TestCase):
    def test_linear_fade(self):
        self.assertAlmostEqual(scrim_progress(0), 0)
        self.assertAlmostEqual(scrim_progress(style.SCRIM_MS / 2), 0.5)
        self.assertAlmostEqual(scrim_progress(style.SCRIM_MS), 1)
        self.assertAlmostEqual(scrim_progress(style.SCRIM_MS * 2), 1)


class HoverPoseTests(unittest.TestCase):
    def test_idle(self):
        push, outer, label_scale = hover_pose(0)
        self.assertAlmostEqual(push, 0)
        self.assertAlmostEqual(outer, R)
        self.assertAlmostEqual(label_scale, 1)

    def test_fully_hovered(self):
        push, outer, label_scale = hover_pose(1)
        self.assertAlmostEqual(push, style.HOVER_PUSH * R)
        self.assertAlmostEqual(outer, style.HOVER_GROW * R)
        self.assertAlmostEqual(label_scale, style.LABEL_HOVER_SCALE)

    def test_halfway(self):
        push, outer, _ = hover_pose(0.5)
        self.assertAlmostEqual(push, style.HOVER_PUSH * R / 2)
        self.assertAlmostEqual(outer, (1 + style.HOVER_GROW) / 2 * R)


class SelectPoseTests(unittest.TestCase):
    def test_others_start_untouched(self):
        self.assertEqual(select_pose(0, chosen=False), (1, 1, 0))

    def test_others_drop_away_quickly(self):
        scale, alpha, push = select_pose(style.SELECT_OTHERS_MS, chosen=False)
        self.assertAlmostEqual(scale, style.SELECT_OTHERS_SCALE)
        self.assertAlmostEqual(alpha, style.SELECT_OTHERS_ALPHA)
        self.assertAlmostEqual(push, 0)

    def test_others_stay_dropped(self):
        self.assertEqual(select_pose(select_total_ms(), chosen=False), select_pose(style.SELECT_OTHERS_MS, chosen=False))

    def test_chosen_starts_untouched(self):
        self.assertEqual(select_pose(0, chosen=True), (1, 1, 0))

    def test_chosen_pushes_out_and_stays_opaque(self):
        scale, alpha, push = select_pose(select_total_ms(), chosen=True)
        self.assertAlmostEqual(scale, style.SELECT_SCALE)
        self.assertAlmostEqual(alpha, 1)
        self.assertAlmostEqual(push, style.SELECT_PUSH * R)

    def test_chosen_is_still_moving_when_others_are_gone(self):
        _, _, push = select_pose(style.SELECT_OTHERS_MS, chosen=True)
        self.assertGreater(push, 0)
        self.assertLess(push, style.SELECT_PUSH * R)

    def test_total_is_drop_plus_hold(self):
        self.assertEqual(select_total_ms(), style.SELECT_OTHERS_MS + style.SELECT_HOLD_MS)


class ClosePoseTests(unittest.TestCase):
    def test_starts_at_rest(self):
        self.assertEqual(close_pose(0), (1, 1))

    def test_ends_small_and_gone(self):
        scale, alpha = close_pose(style.CLOSE_MS)
        self.assertAlmostEqual(scale, style.CLOSE_SCALE_TO)
        self.assertAlmostEqual(alpha, 0)

    def test_never_bounces(self):
        scales = [close_pose(t)[0] for t in range(0, style.CLOSE_MS + 1)]
        self.assertEqual(scales, sorted(scales, reverse=True))


class RingExitPoseTests(unittest.TestCase):
    # The prompt bar's handoff replaces the ordinary select: the ring leaves
    # faster, and the chosen wedge stays put until the rect takes over.

    def test_nothing_moves_during_the_hold(self):
        self.assertEqual(ring_exit_pose(0, chosen=False), (1, 1))
        self.assertEqual(ring_exit_pose(style.RING_EXIT_HOLD_MS, chosen=False), (1, 1))

    def test_others_collapse_by_the_end_of_the_exit(self):
        scale, alpha = ring_exit_pose(style.RING_EXIT_MS, chosen=False)
        self.assertAlmostEqual(scale, style.RING_EXIT_SCALE)
        self.assertAlmostEqual(alpha, 0)

    def test_others_stay_gone(self):
        self.assertEqual(ring_exit_pose(handoff_total_ms(), chosen=False), ring_exit_pose(style.RING_EXIT_MS, chosen=False))

    def test_chosen_holds_its_pose_through_the_exit(self):
        self.assertEqual(ring_exit_pose(style.RING_EXIT_MS, chosen=True), (1, 1))

    def test_chosen_crossfades_out_under_the_growing_rect(self):
        _, alpha = ring_exit_pose(style.RING_EXIT_MS + style.CROSSFADE_MS / 2, chosen=True)
        self.assertAlmostEqual(alpha, 0.5)

    def test_chosen_is_gone_once_the_crossfade_ends(self):
        self.assertEqual(ring_exit_pose(style.RING_EXIT_MS + style.CROSSFADE_MS, chosen=True), (1, 0))


class HandoffTimelineTests(unittest.TestCase):
    def test_rect_waits_for_the_ring_to_leave(self):
        self.assertAlmostEqual(grow_progress(0), 0)
        self.assertAlmostEqual(grow_progress(style.RING_EXIT_MS), 0)

    def test_rect_is_at_rest_when_the_grow_ends(self):
        self.assertAlmostEqual(grow_progress(geometry_rest_ms()), 1)

    def test_rect_fades_in_over_the_start_of_the_grow(self):
        self.assertAlmostEqual(crossfade_progress(style.RING_EXIT_MS), 0)
        self.assertAlmostEqual(crossfade_progress(style.RING_EXIT_MS + style.CROSSFADE_MS), 1)

    def test_field_chrome_waits_for_the_geometry(self):
        self.assertAlmostEqual(field_progress(geometry_rest_ms() - 1), 0)
        self.assertAlmostEqual(field_progress(handoff_total_ms()), 1)

    def test_total_is_the_three_phases(self):
        self.assertEqual(handoff_total_ms(), style.RING_EXIT_MS + style.GROW_MS + style.FIELD_ARRIVE_MS)


class LerpRectTests(unittest.TestCase):
    def setUp(self):
        self.a = QRectF(0, 0, 100, 100)
        self.b = QRectF(200, 50, 500, 60)

    def test_ends(self):
        self.assertEqual(lerp_rect(self.a, self.b, 0), self.a)
        self.assertEqual(lerp_rect(self.a, self.b, 1), self.b)

    def test_halfway(self):
        self.assertEqual(lerp_rect(self.a, self.b, 0.5), QRectF(100, 25, 300, 80))


class TypingDotPoseTests(unittest.TestCase):
    PERIOD = style.CHAT_TYPING_PERIOD_MS

    def test_values_stay_in_unit_range(self):
        for ms in range(0, self.PERIOD * 2, 17):
            for brightness in typing_dot_pose(ms, self.PERIOD):
                self.assertGreaterEqual(brightness, 0)
                self.assertLessEqual(brightness, 1)

    def test_dots_are_out_of_phase_with_each_other(self):
        # The whole point of a sequential pulse: the 3 dots shouldn't all
        # be at the same brightness at some arbitrary point mid-cycle.
        a, b, c = typing_dot_pose(self.PERIOD / 6, self.PERIOD)
        self.assertNotAlmostEqual(a, b)
        self.assertNotAlmostEqual(b, c)

    def test_repeats_every_period(self):
        start = typing_dot_pose(0, self.PERIOD)
        wrapped = typing_dot_pose(self.PERIOD, self.PERIOD)
        for a, b in zip(start, wrapped):
            self.assertAlmostEqual(a, b)


class CardFlightTests(unittest.TestCase):
    BORN_RADIUS = style.FIELD_HEIGHT / 2

    def test_ends(self):
        self.assertAlmostEqual(card_flight_progress(0), 0)
        self.assertAlmostEqual(card_flight_progress(style.CHAT_FLIGHT_MS), 1)

    def test_never_overshoots(self):
        # Overshoot next to a screen corner reads as an error, not as polish.
        self.assertLessEqual(max(card_flight_progress(ms) for ms in range(style.CHAT_FLIGHT_MS + 1)), 1)

    def test_radius_squares_off_before_the_flight_lands(self):
        self.assertAlmostEqual(card_radius(0, self.BORN_RADIUS), self.BORN_RADIUS)
        self.assertAlmostEqual(card_radius(style.CHAT_RADIUS_MS, self.BORN_RADIUS), style.CHAT_RADIUS)
        self.assertAlmostEqual(card_radius(style.CHAT_FLIGHT_MS, self.BORN_RADIUS), style.CHAT_RADIUS)


if __name__ == "__main__":
    unittest.main()
