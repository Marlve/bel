# Entry point. Runs quietly in the background; Ctrl+Shift+Space summons the pie menu.

import sys
from PySide6.QtWidgets import QApplication

from pieMenu import PieMenu
from hotkey import HotkeyListener
from claude import resetClaudeHistory

PIE_MENU_HOTKEY = "ctrl+shift+space"


def main():
    resetClaudeHistory()
    app = QApplication(sys.argv)

    pie_menu = PieMenu()
    hotkey = HotkeyListener(PIE_MENU_HOTKEY)
    hotkey.triggered.connect(pie_menu.onKeyPress)
    hotkey.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
