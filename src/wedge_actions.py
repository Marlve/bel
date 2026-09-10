# What each pie menu wedge does when selected. Kept separate from
# pie_menu.py so the menu's geometry/rendering code doesn't have to know
# about action-specific concerns (e.g. the Claude wedge's background thread).

from PySide6.QtCore import QObject, QThread

from claude import ClaudeWorker


def announce(label):
    return lambda: print(f"selected: {label}")


class ClaudeAction(QObject):
    """Callable wedge action for "Claude". Runs askBel() on a background
    QThread (mirroring HotkeyListener's cross-thread pattern in hotkey.py)
    so the slow, blocking CLI call doesn't freeze the Qt main thread/UI.
    """

    def __init__(self):
        super().__init__()
        self._thread = None
        self._worker = None

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

    def _on_chunk(self, text):
        print(text, end="", flush=True)

    def _on_finished(self):
        print()
        self._thread = None
        self._worker = None
