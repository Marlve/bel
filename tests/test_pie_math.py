import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pie_menu import wedge_index


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


if __name__ == "__main__":
    unittest.main()
