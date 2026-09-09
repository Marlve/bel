# Entry point. For now just shows the bare overlay shell so we can confirm it renders.

import sys
from PySide6.QtWidgets import QApplication

from overlay_window import OverlayWindow


def main():
    app = QApplication(sys.argv)
    overlay = OverlayWindow()
    overlay.resize(300, 150)
    overlay.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
