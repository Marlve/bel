import subprocess
import json
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Signal

# A dedicated, permanent cwd for the claude CLI subprocess (see askBel) -
# never a git repo or somewhere a stray CLAUDE.md could live, so the CLI's
# own project-context auto-loading has nothing to pick up. Because it's the
# same path every launch, the CLI always buckets its session transcripts
# under the same ~/.claude/projects/<encoded-cwd> folder rather than a new
# one per run; resetClaudeHistory() wipes that bucket at startup so it can't
# grow unbounded, since Bel never resumes a session across app restarts
# anyway (ChatCard's session_id lives only in memory).
CLAUDE_CWD = Path.home() / ".bel" / "claude-cwd"

# The only file access the CLI subprocess gets (see askBel()'s --allowedTools
# below) - a script, not the raw todo.json, so a bad index or malformed edit
# can't corrupt the store; see cardTool.py.
CARD_TOOL_PATH = Path(__file__).resolve().parent / "cardTool.py"

# A short, fixed, path-free command name for the model to invoke cardTool.py
# through, so --allowedTools below can be a strict "starts with this exact
# literal" prefix match with nothing before it - live-tested: a pattern like
# "Bash(python *cardTool.py*)" (leading wildcard, to tolerate the model
# quoting the real path differently each time) let an unrelated
# `python -c "..."` one-liner through as long as it merely mentioned
# cardTool.py in a trailing comment, since the CLI's glob matching lets `*`
# span anything, including shell metacharacters. ~/.local/bin is already on
# PATH here (it's where claude.exe itself lives); ensure_card_tool_shim()
# (re)writes this every startup so it stays correct if the repo moves.
CARD_TOOL_SHIM_PATH = Path.home() / ".local" / "bin" / "cardtool.cmd"
CARD_TOOL_SHIM_COMMAND = "cardtool.cmd"

SYSTEM_PROMPT = f"""
You're Bel, a personal assistant overlay for calendar, tasks, and reminders.

- Keep responses short. For actions/commands, just confirm what happened. No extra explanation unless asked.
- You can check/manage calendar events, track assignments and to-dos, and send reminders.
- To read or change the to-do list, run one of these via the Bash tool (no other file access exists):
  - `{CARD_TOOL_SHIM_COMMAND} list-todos`
  - `{CARD_TOOL_SHIM_COMMAND} add-todo "task text"`
  - `{CARD_TOOL_SHIM_COMMAND} toggle-todo "task text"` (the exact text of an open item, from list-todos)
  - There's no delete - if asked to delete/remove/clear a to-do, toggle-todo it done instead; it disappears from the list on its own shortly after.
- If something can't be found or done, say so directly instead of guessing.
- Stay focused on organization/productivity help; for unrelated questions, decline, answer briefly and redirect back to what you can help with.
"""

if hasattr(sys.stdout, "reconfigure"):
  # sys.stdout can be None (no console, e.g. launched via pythonw) or lack
  # this method (e.g. a test runner's captured stdout) now that pieMenu.py
  # imports this module rather than only running it as a standalone script.
  sys.stdout.reconfigure(encoding="utf-8")

def resetClaudeHistory():
  """Call once at app startup. Deletes the claude CLI's own session
  bucket for CLAUDE_CWD (transcripts + memory/) so it can't accumulate
  across launches - the CLI never cleans these up itself. The encoding is
  the CLI's own undocumented scheme; verified by actually invoking `claude`
  with cwd=CLAUDE_CWD and inspecting the resulting ~/.claude/projects/ entry
  rather than guessing - the drive colon, both slash kinds, and '.' (from
  the leading dot in ".bel") all become '-', every other character
  (including a literal '-') is left as-is.

  If the CLI ever changes this encoding, `bucket` silently stops matching
  the real directory and rmtree() just no-ops - no error, nothing to catch
  it. Left unguarded on purpose: a new session file only lands here once per
  app restart (session_id lives in memory only, never resumed across
  launches), so even years of daily use tops out at a slow trickle - not
  worth extra machinery for a failure mode whose worst case is "grows a
  little," never a crash.
  """
  CLAUDE_CWD.mkdir(parents=True, exist_ok=True)
  encoded = str(CLAUDE_CWD).translate(str.maketrans(":\\/.", "----"))
  bucket = Path.home() / ".claude" / "projects" / encoded
  shutil.rmtree(bucket, ignore_errors=True)

def ensure_card_tool_shim():
  """Call once at app startup, alongside resetClaudeHistory(). Writes the
  .cmd shim CARD_TOOL_SHIM_PATH points at, so the model has a stable bare
  command to invoke cardTool.py through - see CARD_TOOL_SHIM_PATH's comment
  for why the exact command name matters for --allowedTools' security, not
  just convenience."""
  CARD_TOOL_SHIM_PATH.parent.mkdir(parents=True, exist_ok=True)
  CARD_TOOL_SHIM_PATH.write_text(f'@python "{CARD_TOOL_PATH}" %*\n')

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
      # -p mode has no TTY to show a permission prompt, so an unlisted tool
      # is silently denied rather than asked about - pre-allow the calendar
      # MCP (already authenticated at the account level, see `claude mcp
      # list`) so SYSTEM_PROMPT's "organize calendar schedule" is actually
      # reachable instead of just aspirational.
      "--allowedTools", "mcp__claude_ai_Google_Calendar",
      f"Bash({CARD_TOOL_SHIM_COMMAND} *)",
  ]
  if session_id:
      args += ["--resume", session_id]

  # Pinned so the CLI's own project-context auto-loading (CLAUDE.md, git
  # status) can't pick up whatever folder this process happens to be
  # launched from - it should only ever see SYSTEM_PROMPT above.
  #
  # CREATE_NO_WINDOW: claude.exe is a real console-subsystem executable, so
  # spawning it from a console-less parent (Bel launched via pythonw) would
  # otherwise make Windows pop a new visible console window for it - and
  # anything it shells out to internally (e.g. a Bash tool call) just
  # attaches to that same console rather than opening its own.
  creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
  process = subprocess.Popen(
      args, stdout=subprocess.PIPE, text=True, encoding="utf-8", cwd=CLAUDE_CWD,
      creationflags=creationflags,
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
