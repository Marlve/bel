import subprocess
import json
import sys
import tempfile

from PySide6.QtCore import QObject, Signal

SYSTEM_PROMPT = """
You're a personal helper tool called Bel.

- answer as short and concise as you can, if its a command, don't put too much details except needed.
- you live as an overlay that could help the user organize calender schedule, check for assignments, remind certain todo list.
- ignore any git/repository status context you were given, only respond to the user's actual message.
"""

if hasattr(sys.stdout, "reconfigure"):
  # sys.stdout can be None (no console, e.g. launched via pythonw) or lack
  # this method (e.g. a test runner's captured stdout) now that pieMenu.py
  # imports this module rather than only running it as a standalone script.
  sys.stdout.reconfigure(encoding="utf-8")

def askBel(prompt, session_id=None, on_process=None, on_session=None):
  """Yields each text delta as Claude streams its response, instead of
  returning the full response at once - callers can react to partial
  output rather than waiting for the whole thing.

  `session_id`, if given, is passed as `--resume` so this call continues an
  earlier conversation instead of starting a fresh one - what lets the chat
  card's composer send real follow-ups, not just independent questions.

  `on_process`, if given, is called with the spawned subprocess as soon as
  it starts, so a caller (e.g. ClaudeWorker) can terminate it from outside
  this generator - otherwise a hung or abandoned request has no way to be
  cancelled short of killing the whole app.

  `on_session`, if given, is called once with the CLI's own session id, read
  off the first event of the stream - a caller keeps it and passes it back
  as `session_id` on the conversation's next turn.
  """
  args = [
      "claude", "-p", prompt,
      "--output-format", "stream-json",
      "--include-partial-messages",
      "--verbose",
      "--append-system-prompt",
      SYSTEM_PROMPT,
  ]
  if session_id:
      args += ["--resume", session_id]

  # Pinned so the CLI's own project-context auto-loading (CLAUDE.md, git
  # status) can't pick up whatever folder this process happens to be
  # launched from - it should only ever see SYSTEM_PROMPT above.
  process = subprocess.Popen(
      args, stdout=subprocess.PIPE, text=True, encoding="utf-8", cwd=tempfile.gettempdir()
  )
  if on_process is not None:
      on_process(process)

  seen_session = False
  try:
      for line in process.stdout:
          line = line.strip()
          if not line:
              continue

          event = json.loads(line)

          if not seen_session:
              new_session_id = event.get("session_id")
              if new_session_id and on_session is not None:
                  on_session(new_session_id)
              seen_session = True

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
  session_started = Signal(str)

  def __init__(self, prompt, session_id=None):
      super().__init__()
      self.prompt = prompt
      self.session_id = session_id
      self.process = None

  def run(self):
      # `finished` must always fire, even on error - it's what tells the
      # caller the request is over (see ClaudeAction's in-flight guard in
      # actions/claudeAction.py); otherwise a failed request leaves the wedge
      # permanently stuck and leaks this thread for the app's lifetime.
      try:
          for text in askBel(
              self.prompt,
              session_id=self.session_id,
              on_process=self.track_process,
              on_session=self.session_started.emit,
          ):
              self.chunk.emit(text)
      except Exception as error:
          self.chunk.emit(f"[error: {error}]")
      finally:
          self.finished.emit()

  def track_process(self, process):
      self.process = process

  def cancel(self):
      """Terminates the underlying `claude` subprocess if one is running,
      unblocking askBel()'s blocking read so run() can finish normally
      instead of hanging forever. Safe to call from another thread -
      subprocess.Popen.terminate()/poll() don't touch Qt/Python threading
      state, just the OS process handle.
      """
      if self.process is not None and self.process.poll() is None:
          self.process.terminate()
