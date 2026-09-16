# Entry point. Runs quietly in the background; Ctrl+Shift+Space summons the pie menu.

import sys
from PySide6.QtWidgets import QApplication

from pieMenu import PieMenu
from hotkey import HotkeyListener
from claude import resetClaudeHistory
import style

PIE_MENU_HOTKEY = "ctrl+shift+space"


def main():
    resetClaudeHistory()
    app = QApplication(sys.argv)

    screen = app.primaryScreen()
    # size() is in logical (DPI-scaled) pixels; multiply back to physical
    # pixels so the OS's own display-scaling setting (e.g. Windows' 150%)
    # doesn't get double-counted on top of this resolution-based scale.
    physical_width = screen.size().width() * screen.devicePixelRatio()
    physical_height = screen.size().height() * screen.devicePixelRatio()
    scale = min(physical_width / style.REFERENCE_WIDTH, physical_height / style.REFERENCE_HEIGHT)
    style.apply_scale(scale)

    pie_menu = PieMenu()
    hotkey = HotkeyListener(PIE_MENU_HOTKEY)
    hotkey.triggered.connect(pie_menu.onKeyPress)
    hotkey.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
