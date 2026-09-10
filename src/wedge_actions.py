# What each pie menu wedge does when selected. Kept separate from
# pie_menu.py so the menu's geometry/rendering code doesn't have to know
# about action-specific concerns (e.g. the Claude wedge's background thread).

from PySide6.QtCore import QObject, QThread, QTimer
from PySide6.QtWidgets import QApplication

from claude import ClaudeWorker

CLAUDE_TIMEOUT_MS = 60_000  # give up on a hung request rather than staying stuck forever


def announce(label):
    return lambda: print(f"selected: {label}")


class ClaudeAction(QObject):
    """Callable wedge action for "Claude". Runs askBel() on a background
    QThread (mirroring HotkeyListener's cross-thread pattern in hotkey.py)
    so the slow, blocking CLI call doesn't freeze the Qt main thread/UI.

    Two edge cases could otherwise leave the `claude` subprocess (and its
    QThread) running past when they should: a request that never returns
    (hung CLI), and the app quitting while a request is in flight. Both are
    routed through `_cancel()`, which terminates the subprocess so it can't
    outlive this app.
    """

    def __init__(self):
        super().__init__()
        self._thread = None
        self._worker = None

        self._timeout = QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.timeout.connect(self._cancel)

        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._cancel)

    def __call__(self):
        if self._thread is not None:
            # A request is already in flight - reassigning these attributes
            # would drop the only Python reference to that QThread/worker,
            # letting Qt garbage-collect a thread that's still running.
            print("selected: Claude -> still waiting on the previous request")
            return

        prompt = "Could you generate me a 200 word poem"  # placeholder until wedges have real input

        self._thread = QThread()
        self._worker = ClaudeWorker(prompt)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.chunk.connect(self._on_chunk)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        print("selected: Claude -> ", end="", flush=True)
        self._thread.start()
        self._timeout.start(CLAUDE_TIMEOUT_MS)

    def _cancel(self):
        # Terminates the subprocess so askBel()'s blocking read unblocks and
        # run() can finish normally instead of leaving the thread running
        # forever. Then quit()+wait() so the QThread is confirmed stopped
        # before this returns - matters most when called from aboutToQuit,
        # since the app may not get another event loop turn afterward.
        if self._worker is not None:
            self._worker.cancel()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(2000)

    def _on_chunk(self, text):
        print(text, end="", flush=True)

    def _on_finished(self):
        print()
        self._timeout.stop()
        self._thread = None
        self._worker = None
