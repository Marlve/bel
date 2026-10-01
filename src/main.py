# Entry point. Runs quietly in the background; a hotkey (Ctrl+Shift+Space by default) summons the pie menu, another (Ctrl+Alt+Space) refocuses the chat.

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QLockFile, QDir
from PySide6.QtGui import QIcon

from pieMenu import PieMenu
from hotkey import HotkeyListener
from claude import resetClaudeHistory
from trayIcon import TrayIcon
from assets import assetPath
import hotkey
import style
import vaultIndex


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
    saved = hotkey.load_hotkeys()
    pie_hotkey = HotkeyListener(saved["pie"])
    # Queued: WM_HOTKEY arrives inside Qt's native event filter, and the
    # ring shouldn't open (grab the mouse, force foreground) mid-dispatch.
    pie_hotkey.triggered.connect(pie_menu.onKeyPress, Qt.QueuedConnection)
    pie_hotkey.start()

    chat_hotkey = HotkeyListener(saved["chat"], hotkey_id=2)  # brings the open chat back under the keyboard
    chat_hotkey.triggered.connect(pie_menu.chat.focus, Qt.QueuedConnection)
    chat_hotkey.start()

    hotkey.listeners.update(pie=pie_hotkey, chat=chat_hotkey)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
