import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QFrame, QWidget

import style
from claudeChatCardAnimation import PopEffect


class PopEffectTests(unittest.TestCase):
    """Checks real pixels - drawSource() silently ignores the painter's
    opacity and offset, so a progress value alone proves nothing."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def render(self, progress):
        outer = QWidget()
        outer.resize(200, 200)
        outer.setStyleSheet("background: #000000;")
        self.addCleanup(outer.deleteLater)
        frame = QFrame(outer)
        frame.setGeometry(10, 10, 100, 100)
        frame.setStyleSheet("background: #ffffff;")
        effect = PopEffect()
        frame.setGraphicsEffect(effect)
        effect.setProgress(progress)
        outer.show()
        QApplication.processEvents()
        return outer.grab().toImage()

    def color(self, image, x, y):
        return QColor(image.pixel(x, y)).name()

    def test_at_the_start_the_widget_is_invisible(self):
        self.assertEqual(self.color(self.render(0.0), 50, 50), "#000000")

    def test_halfway_it_is_half_faded_and_still_below_its_place(self):
        image = self.render(0.5)

        self.assertEqual(self.color(image, 50, 50), "#7f7f7f")
        self.assertEqual(self.color(image, 50, 10), "#000000")  # its top edge hasn't risen into place yet

    def test_at_the_end_it_paints_normally(self):
        image = self.render(1.0)

        self.assertEqual(self.color(image, 50, 10), "#ffffff")
        self.assertEqual(self.color(image, 50, 110 + style.PICKER_POP_RISE // 2), "#000000")


if __name__ == "__main__":
    unittest.main()
