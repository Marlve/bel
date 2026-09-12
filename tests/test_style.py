import importlib
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import style


class ApplyScaleTests(unittest.TestCase):
    def tearDown(self):
        importlib.reload(style)  # undo apply_scale's in-place mutation for later tests

    def test_reference_resolution_leaves_constants_unchanged(self):
        style.apply_scale(1.0)
        self.assertEqual(style.RING_RADIUS, 152)
        self.assertEqual(style.CARD_MIN_WIDTH, 200)
        self.assertEqual(style.SPACE_1, 4)
        self.assertEqual(style.SPACE_2, 8)
        self.assertEqual(style.SPACE_3, 12)
        self.assertEqual(style.SPACE_4, 16)

    def test_scales_a_size_constant_by_the_given_factor(self):
        style.apply_scale(0.5)  # e.g. 1280x720 vs. the 2560x1440 reference
        self.assertEqual(style.RING_RADIUS, 76)
        self.assertEqual(style.CARD_MIN_WIDTH, 100)
        self.assertEqual(style.SPACE_1, 2)
        self.assertEqual(style.SPACE_2, 4)
        self.assertEqual(style.SPACE_3, 6)
        self.assertEqual(style.SPACE_4, 8)

    def test_keeps_already_float_constants_as_floats(self):
        style.apply_scale(2.0)
        self.assertAlmostEqual(style.CHAT_BODY_SIZE, 25.0)
        self.assertAlmostEqual(style.CARD_RESIZE_GRIP_STROKE, 2.8)

    def test_scales_each_element_of_a_tuple_constant(self):
        style.apply_scale(2.0)
        self.assertEqual(style.CHAT_BUBBLE_RADIUS, (16, 16, 4, 16))

    def test_derived_constant_scales_by_the_same_factor(self):
        original = style.SETTINGS_HEIGHT
        style.apply_scale(2.0)
        self.assertEqual(style.SETTINGS_HEIGHT, round(original * 2.0))

    def test_leaves_colors_alphas_durations_ratios_counts_and_angles_untouched(self):
        before = (
            style.SCRIM_ALPHA,
            style.OPEN_MS,
            style.RING_INNER,
            style.SETTINGS_ROWS,
            style.DOCK_TAB_ROTATION_DEG,
            style.WEDGE_IDLE,
        )
        style.apply_scale(5120 / style.REFERENCE_WIDTH)
        after = (
            style.SCRIM_ALPHA,
            style.OPEN_MS,
            style.RING_INNER,
            style.SETTINGS_ROWS,
            style.DOCK_TAB_ROTATION_DEG,
            style.WEDGE_IDLE,
        )
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
