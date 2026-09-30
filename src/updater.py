# Update check against GitHub releases, and the download-and-run of the newer installer.

import json
import os
import subprocess
import tempfile
import urllib.request

from PySide6.QtCore import QObject, Signal

from backgroundRequest import BackgroundRequest
from version import VERSION

LATEST_URL = "https://api.github.com/repos/Marlve/bel/releases/latest"
TIMEOUT_SECONDS = 15


def versionTuple(text):
    return tuple(int(part) for part in text.lstrip("v").split("."))


def findUpdate():
    """(version, installer url) of a newer release, else None. Raises on network errors."""
    with urllib.request.urlopen(LATEST_URL, timeout=TIMEOUT_SECONDS) as response:
        release = json.load(response)
    version = release["tag_name"].lstrip("v")
    if versionTuple(version) <= versionTuple(VERSION):
        return None
    for asset in release["assets"]:
        if asset["name"].endswith(".exe"):
            return version, asset["browser_download_url"]
    return None


def downloadInstaller(url):
    path = os.path.join(tempfile.gettempdir(), url.rsplit("/", 1)[-1])
    with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response, open(path, "wb") as out:
        out.write(response.read())
    return path


def runInstaller(path):
    # Setup quits Bel, upgrades in place and relaunches it.
    subprocess.Popen([path, "/SILENT"])


class JobWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, job, *args):
        super().__init__()
        self.job = job
        self.args = args

    def run(self):
        try:
            self.finished.emit(self.job(*self.args))
        except Exception as error:
            self.failed.emit(str(error))


class JobRequest(BackgroundRequest):
    """One blocking call off the UI thread; `done(result)` or `failed(message)`."""

    done = Signal(object)
    failed = Signal(str)

    def __init__(self, job, *args, parent=None):
        super().__init__(JobWorker(job, *args), parent)
        self.worker.finished.connect(self.onFinished)
        self.worker.failed.connect(self.onFailed)

    def onFinished(self, result):
        self.stopThread()
        self.done.emit(result)

    def onFailed(self, message):
        self.stopThread()
        self.failed.emit(message)
