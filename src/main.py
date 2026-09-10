# Entry point. Runs quietly in the background; Ctrl+Shift+Space summons the pie menu.

import sys
from PySide6.QtWidgets import QApplication

from pie_menu import PieMenu
from hotkey import HotkeyListener

PIE_MENU_HOTKEY = "ctrl+shift+space"


def main():
    app = QApplication(sys.argv)

    pie_menu = PieMenu()
    hotkey = HotkeyListener(PIE_MENU_HOTKEY)
    hotkey.triggered.connect(pie_menu.open_at_cursor)
    hotkey.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
