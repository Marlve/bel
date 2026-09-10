import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pie_menu import wedge_index, cycle_wedge


class WedgeIndexTests(unittest.TestCase):
    # 4 wedges, index 0 = up, going clockwise (up, right, down, left).
    # Screen coordinates: dy grows downward.

    def test_up(self):
        self.assertEqual(wedge_index(0, -50, 4), 0)

    def test_right(self):
        self.assertEqual(wedge_index(50, 0, 4), 1)

    def test_down(self):
        self.assertEqual(wedge_index(0, 50, 4), 2)

    def test_left(self):
        self.assertEqual(wedge_index(-50, 0, 4), 3)

    def test_inside_deadzone_is_undecided(self):
        self.assertIsNone(wedge_index(1, 1, 4, deadzone=20))

    def test_outside_deadzone_resolves(self):
        self.assertEqual(wedge_index(0, -50, 4, deadzone=20), 0)

    def test_outside_radius_is_undecided(self):
        self.assertIsNone(wedge_index(0, -150, 4, radius=90))

    def test_inside_radius_resolves(self):
        self.assertEqual(wedge_index(0, -50, 4, radius=90), 0)


class CycleWedgeTests(unittest.TestCase):
    # step=+1 (right) moves to the next wedge, step=-1 (left) to the previous.

    def test_right_from_none_selects_first(self):
        self.assertEqual(cycle_wedge(None, 4, 1), 0)

    def test_left_from_none_selects_last(self):
        self.assertEqual(cycle_wedge(None, 4, -1), 3)

    def test_right_advances(self):
        self.assertEqual(cycle_wedge(1, 4, 1), 2)

    def test_left_retreats(self):
        self.assertEqual(cycle_wedge(1, 4, -1), 0)

    def test_right_wraps_past_end(self):
        self.assertEqual(cycle_wedge(3, 4, 1), 0)

    def test_left_wraps_past_start(self):
        self.assertEqual(cycle_wedge(0, 4, -1), 3)


if __name__ == "__main__":
    unittest.main()
