from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from backgroundRequest import BackgroundRequest
from claude import ClaudeWorker

CLAUDE_TIMEOUT_MS = 60_000  # give up on a hung request rather than staying stuck forever
DEFAULT_PROMPT = "Can you make a todo for, ETW assignment, meet a friend"  # used when a wedge asks for no input


class ClaudeRequest(BackgroundRequest):
    """One call to the CLI, start to finish, streaming its response as it
    arrives.

    Runs askBel() on a background QThread (via BackgroundRequest) so the
    slow, blocking CLI call doesn't freeze the Qt main thread/UI.

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

    def __init__(self, prompt, session_id=None, parent=None, system_prompt=None):
        super().__init__(ClaudeWorker(prompt, session_id, system_prompt), parent)
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
        super().start()
        self.timeout_timer.start(CLAUDE_TIMEOUT_MS)

    def onWorkerFinished(self):
        # Runs on the main thread - the worker emits this from its own thread
        # as run() returns, so by now there is nothing left to wait for.
        self.timeout_timer.stop()
        self.stopThread()
        self.finished.emit()

    def cancel(self):
        # Terminates the subprocess so askBel()'s blocking read unblocks and
        # run() can finish normally instead of leaving the thread running
        # forever.
        self.worker.cancel()
        self.stopThread()


class ClaudeQuery:
    """A plain callback-based class that asks one ClaudeRequest and hands
    the whole answer to `answered(text, failed)`, which subclasses define.
    ExplainQuery and TriageQuery (vaultSearch.py) build on it. The cancel and
    aboutToQuit handling lives here once, so a fix to it can't reach only
    some of them (issue 14)."""

    def __init__(self, request_factory=ClaudeRequest):
        self.request_factory = request_factory  # swappable in tests, so a query never spawns a real `claude` subprocess
        self.text = ""
        self.request = None
        self.cancelled = False

        # Mirrors ClaudeAction's own aboutToQuit wiring so an in-flight
        # request can't outlive the app.
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.cancel)

    def ask(self, prompt):
        self.request = self.request_factory(prompt)
        self.request.chunk.connect(self.onChunk)
        self.request.finished.connect(self.onFinished)
        self.request.start()

    def onChunk(self, text):
        self.text += text

    def onFinished(self):
        # `finished` still fires after cancel() (ClaudeWorker's own
        # guarantee, see claude.py) - without this guard a cancelled query
        # would still hand the caller a stale or cut-off answer.
        self.disconnectAboutToQuit()
        if self.cancelled:
            return
        self.answered(self.text, self.request.failed)

    def answered(self, text, failed):
        raise NotImplementedError

    def cancel(self):
        self.cancelled = True
        if self.request is not None:
            self.request.cancel()

    def disconnectAboutToQuit(self):
        # Undoes the __init__ wiring once this query resolves. aboutToQuit
        # holds a strong reference to the connected bound method, so leaving
        # it connected would keep every past query alive for the rest of the
        # app's life - unbounded growth proportional to query count (issue 06).
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.disconnect(self.cancel)


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

    def __call__(self, prompt=None, session_id=None, system_prompt=None):
        request = ClaudeRequest(prompt or self.prompt, session_id, self, system_prompt=system_prompt)
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
