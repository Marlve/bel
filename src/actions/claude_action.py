from PySide6.QtCore import QObject, QThread, QTimer
from PySide6.QtWidgets import QApplication

from claude import ClaudeWorker

CLAUDE_TIMEOUT_MS = 60_000  # give up on a hung request rather than staying stuck forever
DEFAULT_PROMPT = "Can you make a todo for, ETW assignment, meet a friend"  # placeholder until wedges have real input


class ClaudeAction(QObject):
    """Callable wedge action for "Claude". Runs askBel() on a background
    QThread (mirroring HotkeyListener's cross-thread pattern in hotkey.py)
    so the slow, blocking CLI call doesn't freeze the Qt main thread/UI.

    Two edge cases could otherwise leave the `claude` subprocess (and its
    QThread) running past when they should: a request that never returns
    (hung CLI), and the app quitting while a request is in flight. Both are
    routed through `cancel()`, which terminates the subprocess so it can't
    outlive this app.
    """

    def __init__(self, prompt=DEFAULT_PROMPT):
        super().__init__()
        self.prompt = prompt
        self.thread = None
        self.worker = None

        self.timeout_timer = QTimer(self)
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.timeout.connect(self.cancel)

        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.cancel)

    def __call__(self):
        if self.thread is not None:
            # A request is already in flight - reassigning these attributes
            # would drop the only Python reference to that QThread/worker,
            # letting Qt garbage-collect a thread that's still running.
            print("selected: Claude -> still waiting on the previous request")
            return

        self.thread = QThread()
        self.worker = ClaudeWorker(self.prompt)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.chunk.connect(self.on_chunk)
        self.worker.finished.connect(self.on_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        print("selected: Claude -> ", end="", flush=True)
        self.thread.start()
        self.timeout_timer.start(CLAUDE_TIMEOUT_MS)

    def cancel(self):
        # Terminates the subprocess so askBel()'s blocking read unblocks and
        # run() can finish normally instead of leaving the thread running
        # forever. Then quit()+wait() so the QThread is confirmed stopped
        # before this returns - matters most when called from aboutToQuit,
        # since the app may not get another event loop turn afterward.
        if self.worker is not None:
            self.worker.cancel()
        if self.thread is not None:
            self.thread.quit()
            self.thread.wait(2000)

    def on_chunk(self, text):
        print(text, end="", flush=True)

    def on_finished(self):
        print()
        self.timeout_timer.stop()
        self.thread = None
        self.worker = None
