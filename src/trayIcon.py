# Notification-area icon: the one visible sign Bel is running, and how to quit it.

import sys
import winreg
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

import autostart
from assets import assetPath


def taskbarIsLight():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            return winreg.QueryValueEx(key, "SystemUsesLightTheme")[0] == 1
    except OSError:
        return False


class TrayIcon:
    def __init__(self, app):
        self.tray = QSystemTrayIcon()
        self.menu = QMenu()

        # Only the packaged exe has a stable path worth registering to run at logon.
        if getattr(sys, "frozen", False):
            self.startup = QAction("Start with Windows")
            self.startup.setCheckable(True)
            self.startup.setChecked(autostart.isEnabled())
            self.startup.toggled.connect(autostart.setEnabled)
            self.menu.addAction(self.startup)

        self.menu.addAction("Quit Bel", app.quit)
        self.tray.setContextMenu(self.menu)
        self.tray.setToolTip("Bel")

        self.refreshIcon()
        # Fires when the apps theme flips, which is the usual moment the taskbar's does too.
        app.styleHints().colorSchemeChanged.connect(self.refreshIcon)
        self.tray.show()

    def refreshIcon(self, *_):
        mark = "dark" if taskbarIsLight() else "light"
        self.tray.setIcon(QIcon(assetPath(f"bel-mark-{mark}-1024.png")))
