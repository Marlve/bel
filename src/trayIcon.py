# Notification-area icon: the one visible sign Bel is running, and how to quit it.

import sys
import winreg
from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

import autostart
import updater
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

            self.update = QAction()
            self.update.setVisible(False)
            self.update.triggered.connect(self.installUpdate)
            self.menu.addAction(self.update)
            self.updateUrl = None
            self.requests = []
            QTimer.singleShot(5000, self.checkForUpdate)
            self.checkTimer = QTimer()
            self.checkTimer.timeout.connect(self.checkForUpdate)
            self.checkTimer.start(24 * 60 * 60 * 1000)

        self.menu.addAction("Quit Bel", app.quit)
        self.tray.setContextMenu(self.menu)
        self.tray.setToolTip("Bel")

        self.refreshIcon()
        # Fires when the apps theme flips, which is the usual moment the taskbar's does too.
        app.styleHints().colorSchemeChanged.connect(self.refreshIcon)
        self.tray.show()

    def run(self, job, on_done, on_failed, *args):
        request = updater.JobRequest(job, *args)
        self.requests.append(request)
        request.done.connect(on_done)
        request.failed.connect(on_failed)
        request.start()

    def checkForUpdate(self):
        # A failed check (offline, rate limited) just waits for the next one.
        self.run(updater.findUpdate, self.onUpdateFound, lambda message: None)

    def onUpdateFound(self, found):
        if found:
            version, self.updateUrl = found
            self.update.setText(f"Update to v{version}")
            self.update.setVisible(True)
            self.tray.setToolTip(f"Bel - v{version} available")

    def installUpdate(self):
        self.update.setEnabled(False)
        self.update.setText("Downloading update...")
        self.run(updater.downloadInstaller, self.onDownloaded, self.onDownloadFailed, self.updateUrl)

    def onDownloaded(self, path):
        updater.runInstaller(path)
        QApplication.quit()

    def onDownloadFailed(self, message):
        self.update.setEnabled(True)
        self.update.setText("Update failed - retry")

    def refreshIcon(self, *_):
        mark = "dark" if taskbarIsLight() else "light"
        self.tray.setIcon(QIcon(assetPath(f"bel-mark-{mark}-1024.png")))
