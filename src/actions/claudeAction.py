from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtWidgets import QApplication

from claude import ClaudeWorker

CLAUDE_TIMEOUT_MS = 60_000  # give up on a hung request rather than staying stuck forever
DEFAULT_PROMPT = "Can you make a todo for, ETW assignment, meet a friend"  # used when a wedge asks for no input


class ClaudeRequest(QObject):
    """One call to the CLI, start to finish, streaming its response as it
    arrives.

    Runs askBel() on a background QThread (mirroring HotkeyListener's
    cross-thread pattern in hotkey.py) so the slow, blocking CLI call doesn't
    freeze the Qt main thread/UI.

    The signals belong to this one request rather than to the wedge, so a
    listener - a chat card, say - follows the answer to its own question
    and nothing else. Two requests can be in flight at once, each feeding its
    own card.

    Two edge cases could otherwise leave the `claude` subprocess (and its
    QThread) running past when they should: a request that never returns
    (hung CLI), and the app quitting while a request is in flight. Both are
    routed through `cancel()`, which terminates the subprocess so it can't
    outlive this app.
    """

    chunk = Signal(str)
    finished = Signal()
    session_started = Signal(str)

    def __init__(self, prompt, session_id=None, parent=None):
        super().__init__(parent)
        self.thread = QThread()
        self.worker = ClaudeWorker(prompt, session_id)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.chunk.connect(self.chunk)
        self.worker.session_started.connect(self.session_started)
        self.worker.finished.connect(self.onWorkerFinished)

        self.timeout_timer = QTimer(self)
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.timeout.connect(self.cancel)

    @property
    def failed(self):
        """Whether the answer ended on an error, a timeout or a cancel rather
        than completing - only meaningful once `finished` has fired."""
        return self.worker.failed

    def start(self):
        self.thread.start()
        self.timeout_timer.start(CLAUDE_TIMEOUT_MS)

    def onWorkerFinished(self):
        # Runs on the main thread - the worker emits this from its own thread
        # as run() returns, so by now there is nothing left to wait for.
        self.timeout_timer.stop()
        self.thread.quit()
        self.thread.wait(2000)
        self.finished.emit()

    def cancel(self):
        # Terminates the subprocess so askBel()'s blocking read unblocks and
        # run() can finish normally instead of leaving the thread running
        # forever. Then quit()+wait() so the QThread is confirmed stopped
        # before this returns - matters most when called from aboutToQuit,
        # since the app may not get another event loop turn afterward.
        self.worker.cancel()
        self.thread.quit()
        self.thread.wait(2000)


class ClaudeAction(QObject):
    """Callable wedge action for "Claude". Each call starts a ClaudeRequest
    and returns it, so whoever asked can follow that answer alone.

    In-flight requests are held here because dropping the last reference to
    one would let Qt garbage-collect a QThread that is still running; they're
    released once finished, and all of them are cancelled on app quit.
    """

    def __init__(self, prompt=DEFAULT_PROMPT):
        super().__init__()
        self.prompt = prompt
        self.requests = []

        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.cancel)

    def __call__(self, prompt=None, session_id=None):
        request = ClaudeRequest(prompt or self.prompt, session_id, self)
        self.requests.append(request)
        request.chunk.connect(self.onChunk)
        request.finished.connect(lambda: self.forget(request))

        print("selected: Claude -> ", end="", flush=True)
        request.start()
        return request

    def forget(self, request):
        print()
        if request in self.requests:
            self.requests.remove(request)
        request.deleteLater()

    def onChunk(self, text):
        print(text, end="", flush=True)

    def cancel(self):
        for request in list(self.requests):
            request.cancel()
