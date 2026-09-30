# `! read`: the text in a screenshot crop, via Windows' built-in OCR (offline, no AI).
# The engine lives in assets/ocr.ps1 because only Windows PowerShell 5.1 can reach it without a new dependency.

import subprocess
from pathlib import Path
from PySide6.QtCore import QObject, Signal

from assets import assetPath
from backgroundRequest import BackgroundRequest


def recognize(image_path, language="ko"):
    """The text in the image with line breaks collapsed to spaces, so a wrapped sentence
    reads as one. Raises OSError when there is no engine or the image can't be read."""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         assetPath("ocr.ps1"), str(Path(image_path).resolve()), language],
        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=30,
    )
    if result.returncode == 2:  # the script's "no language pack" exit
        raise OSError(result.stderr.decode("utf-8", "replace").strip())
    if result.returncode != 0:
        raise OSError("couldn't read that image")
    return " ".join(result.stdout.decode("utf-8").split())


class OcrWorker(QObject):
    finished = Signal(str, str)  # text, error - one of them is empty

    def __init__(self, image_path):
        super().__init__()
        self.image_path = image_path

    def run(self):
        # `finished` must always fire, or the card would wait on it forever.
        try:
            self.finished.emit(recognize(self.image_path), "")
        except (OSError, subprocess.SubprocessError) as error:
            self.finished.emit("", str(error))


class OcrRequest(BackgroundRequest):
    finished = Signal(str, str)

    def __init__(self, image_path, parent=None):
        super().__init__(OcrWorker(image_path), parent)
        self.worker.finished.connect(self.onWorkerFinished)

    def onWorkerFinished(self, text, error):
        self.stopThread()
        self.finished.emit(text, error)

    def cancel(self):
        self.stopThread()
