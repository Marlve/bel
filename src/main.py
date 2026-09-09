# Entry point. For now just shows the bare overlay shell so we can confirm it renders.

import sys
from PySide6.QtWidgets import QApplication

from overlay import OverlayWindow
from pie_menu import PieMenu
from hotkey import HotkeyListener

PIE_MENU_HOTKEY = "ctrl+shift+space"


def main():
    app = QApplication(sys.argv)

    overlay = OverlayWindow()
    overlay.resize(300, 150)
    overlay.show()

    pie_menu = PieMenu()
    hotkey = HotkeyListener(PIE_MENU_HOTKEY)
    hotkey.triggered.connect(pie_menu.open_at_cursor)
    hotkey.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
