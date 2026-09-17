from PySide6.QtCore import QObject, QThread


class BackgroundRequest(QObject):
    """Runs a worker's `run()` on its own QThread. The shared lifecycle behind
    ClaudeRequest (actions/claudeAction.py) and SearchRequest (vaultSearch.py),
    kept in one place so a fix to the teardown can't reach only one of them
    (issue 21). Each subclass wires its own worker signals and `cancel()`."""

    def __init__(self, worker, parent=None):
        super().__init__(parent)
        self.thread = QThread()
        self.worker = worker
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)

    def start(self):
        self.thread.start()

    def stopThread(self):
        # quit()+wait() so the QThread is confirmed stopped before this
        # returns - matters most when called from aboutToQuit, since the app
        # may not get another event loop turn afterward.
        self.thread.quit()
        self.thread.wait(2000)
