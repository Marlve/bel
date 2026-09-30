# Entry point. Runs quietly in the background; Ctrl+Shift+Space summons the pie menu, Ctrl+Alt+Space refocuses the chat.

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QLockFile, QDir
from PySide6.QtGui import QIcon

from pieMenu import PieMenu
from hotkey import HotkeyListener
from claude import resetClaudeHistory
from trayIcon import TrayIcon
from assets import assetPath
import style
import vaultIndex

PIE_MENU_HOTKEY = "ctrl+shift+space"
CHAT_FOCUS_HOTKEY = "ctrl+alt+space"  # brings the open chat back under the keyboard


def main():
    app = QApplication(sys.argv)

    # One instance only: a second copy would run with dead hotkeys, since the first already owns them.
    lock = QLockFile(QDir.tempPath() + "/bel.lock")
    if not lock.tryLock(0):
        sys.exit(0)

    resetClaudeHistory()
    app.setWindowIcon(QIcon(assetPath("bel.ico")))
    tray = TrayIcon(app)

    screen = app.primaryScreen()
    # size() is in logical (DPI-scaled) pixels; multiply back to physical
    # pixels so the OS's own display-scaling setting (e.g. Windows' 150%)
    # doesn't get double-counted on top of this resolution-based scale.
    physical_width = screen.size().width() * screen.devicePixelRatio()
    physical_height = screen.size().height() * screen.devicePixelRatio()
    scale = min(physical_width / style.REFERENCE_WIDTH, physical_height / style.REFERENCE_HEIGHT)
    style.apply_scale(scale)
    style.load_chat_size_scale()
    style.load_accent()
    vaultIndex.load_vault_path()

    pie_menu = PieMenu()
    hotkey = HotkeyListener(PIE_MENU_HOTKEY)
    # Queued: WM_HOTKEY arrives inside Qt's native event filter, and the
    # ring shouldn't open (grab the mouse, force foreground) mid-dispatch.
    hotkey.triggered.connect(pie_menu.onKeyPress, Qt.QueuedConnection)
    hotkey.start()

    chat_hotkey = HotkeyListener(CHAT_FOCUS_HOTKEY, hotkey_id=2)
    chat_hotkey.triggered.connect(pie_menu.chat.focus, Qt.QueuedConnection)
    chat_hotkey.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
