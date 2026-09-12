import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication, QWidget

import style
from promptFlow import PromptFlow


class PromptFlowFieldRectTests(unittest.TestCase):
    """fieldRect()'s edge-growth behavior (screen-boundaries/01) - vertical
    placement is untested here since PieMenu.clampedAnchor() already
    guarantees room above/below before a handoff can start."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.parent = QWidget()
        self.parent.setGeometry(QApplication.primaryScreen().virtualGeometry())
        self.flow = PromptFlow(self.parent, wedge_count=4, on_tick=lambda: None, on_arrived=lambda: None)

    def tearDown(self):
        self.parent.close()
        self.parent.deleteLater()
        QApplication.processEvents()

    def test_field_centers_on_the_anchor_away_from_any_edge(self):
        area = QApplication.primaryScreen().availableGeometry()
        anchor = QPointF(area.x() + area.width() / 2, area.y() + area.height() / 2)
        rect = self.flow.fieldRect(anchor)
        self.assertAlmostEqual(rect.center().x(), anchor.x(), delta=1)
        self.assertEqual(rect.width(), style.FIELD_WIDTH)

    def test_field_grows_rightward_from_the_left_edge_instead_of_clipping(self):
        area = QApplication.primaryScreen().availableGeometry()
        anchor = QPointF(area.x(), area.y() + area.height() / 2)
        rect = self.flow.fieldRect(anchor)
        self.assertAlmostEqual(rect.left(), anchor.x(), delta=1)
        self.assertEqual(rect.width(), style.FIELD_WIDTH)

    def test_field_grows_leftward_from_the_right_edge_instead_of_clipping(self):
        area = QApplication.primaryScreen().availableGeometry()
        anchor = QPointF(area.x() + area.width(), area.y() + area.height() / 2)
        rect = self.flow.fieldRect(anchor)
        self.assertAlmostEqual(rect.right(), anchor.x(), delta=1)
        self.assertEqual(rect.width(), style.FIELD_WIDTH)


if __name__ == "__main__":
    unittest.main()
