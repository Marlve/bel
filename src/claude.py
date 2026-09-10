import subprocess
import json
import sys

from PySide6.QtCore import QObject, Signal

SYSTEM_PROMPT = """
You're a personal helper tool called Bel.

- you live as an overlay that could help the user organize calender schedule, check for assignments, remind certain todo list.
- ignore any git/repository status context you were given, only respond to the user's actual message.
- whenever the user asks to create a todo, write it to C:\\Users\\deric\\Code\\bel\\extra\\todo.md
"""

if hasattr(sys.stdout, "reconfigure"):
  # sys.stdout can be None (no console, e.g. launched via pythonw) or lack
  # this method (e.g. a test runner's captured stdout) now that pie_menu.py
  # imports this module rather than only running it as a standalone script.
  sys.stdout.reconfigure(encoding="utf-8")

def askBel(prompt, on_process=None):
  """Yields each text delta as Claude streams its response, instead of
  returning the full response at once - callers can react to partial
  output rather than waiting for the whole thing.

  `on_process`, if given, is called with the spawned subprocess as soon as
  it starts, so a caller (e.g. ClaudeWorker) can terminate it from outside
  this generator - otherwise a hung or abandoned request has no way to be
  cancelled short of killing the whole app.
  """
  process = subprocess.Popen(
      [
          "claude", "-p", prompt,
          "--output-format", "stream-json",
          "--include-partial-messages",
          "--verbose",
          "--append-system-prompt",
          SYSTEM_PROMPT,
          "--allowedTools", "Write",
          "--permission-mode", "acceptEdits",
      ],
      stdout=subprocess.PIPE,
      text=True,
      encoding="utf-8",
  )
  if on_process is not None:
      on_process(process)

  try:
      for line in process.stdout:
          line = line.strip()
          if not line:
              continue

          event = json.loads(line)
          if event.get("type") != "stream_event":
              continue

          delta = event["event"].get("delta")
          if delta and delta.get("type") == "text_delta":
              yield delta["text"]
  finally:
      # Guarantees the child process is reaped even if a stream line is
      # malformed and raises mid-loop - without this, an unhandled parse
      # error here would leave `process` orphaned instead of waited-on,
      # and PieMenu/ClaudeAction being long-lived app singletons means
      # each occurrence leaks a `claude` process for the app's lifetime.
      process.wait()


class ClaudeWorker(QObject):
  """Runs askBel() on a background thread so callers on the Qt main thread
  (e.g. a pie menu action) don't block while the CLI call streams its
  response. Move an instance to a QThread and connect the thread's
  `started` signal to `run`, mirroring HotkeyListener's cross-thread
  pattern in hotkey.py - this class never touches Qt widgets directly, it
  re-emits each streamed piece via `chunk` (and `finished` once the
  response is done) and leaves the receiving slots to run on the main
  thread.
  """

  chunk = Signal(str)
  finished = Signal()

  def __init__(self, prompt):
      super().__init__()
      self._prompt = prompt
      self._process = None

  def run(self):
      # `finished` must always fire, even on error - it's what tells the
      # caller the request is over (see ClaudeAction's in-flight guard in
      # wedge_actions.py); otherwise a failed request leaves the wedge
      # permanently stuck and leaks this thread for the app's lifetime.
      try:
          for text in askBel(self._prompt, on_process=self._track_process):
              self.chunk.emit(text)
      except Exception as error:
          self.chunk.emit(f"[error: {error}]")
      finally:
          self.finished.emit()

  def _track_process(self, process):
      self._process = process

  def cancel(self):
      """Terminates the underlying `claude` subprocess if one is running,
      unblocking askBel()'s blocking read so run() can finish normally
      instead of hanging forever. Safe to call from another thread -
      subprocess.Popen.terminate()/poll() don't touch Qt/Python threading
      state, just the OS process handle.
      """
      if self._process is not None and self._process.poll() is None:
          self._process.terminate()
