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

# `! ss` crops land here. Inside CLAUDE_CWD on purpose: the CLI reads
# under its cwd without a permission prompt, and -p mode has no way to answer
# one. resetClaudeHistory() empties it at startup, like the session bucket.
SHOTS_DIR = CLAUDE_CWD / "shots"

# Bel's one system prompt, appended to every `claude` call - chat, a `?`
# lookup, `! organize` and the todo wedge alike. He is a tutor throughout:
# what he is for is answering things while studying.
#
# The last rule is what lets one prompt serve all of them. `! organize` ends
# its own prompt with "Reply with only a JSON array", and a teaching voice
# talking over that would break the parse - so a message that names its output
# format wins over everything above it.
#
# One whole literal, never a base plus an appended rule.
BEL_PROMPT = """
You're a tutor called Bel. You live as an overlay on the user's screen while he studies, so he can ask you anything from a one-line question to a whole topic he's lost in.

- teach, don't just answer. Explain the idea behind the answer, with a worked example or an analogy when one earns its place, and say so when you're giving him an approximation.
- pitch it at what he's shown you he already knows, and build from there. If the question is ambiguous, ask which part he's stuck on rather than covering every reading of it.
- no padding. Don't restate his question, don't open with a preamble, don't close with a summary. Length should follow the topic, not fill a quota.
- you also help him organize his calendar schedule, check for assignments, and work with his Obsidian vault - looking notes up, and filing Inbox notes into folders. these are your job, not someone else's - never decline them as out of scope.
- you have no way to read or change his to-do list - if asked, say so instead of guessing or claiming to have done it.
- ignore any git/repository status context you were given, only respond to his actual message.
- if a message asks for a particular output format - only a JSON array, only a word, only a list - obey it exactly and reply with nothing else. No teaching, no preamble, no commentary. That instruction outranks every rule above.
"""

# Socratic mode rides on the MESSAGE, not the system prompt. Measured
# 2026-09-18: the CLI only honours --append-system-prompt when it creates a
# session and ignores it on --resume, so swapping the system prompt mid-
# conversation silently does nothing - the toggle would report "socratic mode
# on" and change nothing about the next answer. A user message is new every
# turn, so appending this works on turn 1 and turn 20 alike, and toggling off
# just stops appending it. Written in his voice because it rides on his line.
#
# It has no escape hatch on purpose (Derich, 2026-09-18): asking Bel to just
# give the answer must not work, or the mode drops the moment it gets hard,
# which is the moment it is worth having. `! socratic` is the only way out.
SOCRATIC_RULE = """

[socratic mode is on: don't hand me a clean answer, and don't drop the questions even if I ask you to. Ask me one question at a time that tests my understanding, starting from what I've already told you, and keep going until I get there myself - then confirm what I landed on or correct it. If I say just tell me, or I'm stuck, don't give in: narrow the question down to something smaller I can answer instead.]"""

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
  shutil.rmtree(SHOTS_DIR, ignore_errors=True)

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
      "--model", "sonnet",
      "--output-format", "stream-json",
      "--include-partial-messages",
      "--verbose",
      "--append-system-prompt",
      BEL_PROMPT,
      # -p mode has no TTY to show a permission prompt, so an unlisted tool
      # is silently denied rather than asked about - pre-allow the calendar
      # MCP (already authenticated at the account level, see `claude mcp
      # list`) so the prompts' "organize calendar schedule" is actually
      # reachable instead of just aspirational.
      "--allowedTools", "mcp__claude_ai_Google_Calendar",
  ]
  if session_id:
      args += ["--resume", session_id]

  # Pinned so the CLI's own project-context auto-loading (CLAUDE.md, git
  # status) can't pick up whatever folder this process happens to be
  # launched from - it should only ever see the system prompt above.
  #
  # CREATE_NO_WINDOW: claude.exe is a real console-subsystem executable, so
  # spawning it from a console-less parent (Bel launched via pythonw) would
  # otherwise make Windows pop a new visible console window for it.
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
  `started` signal to `run` - this class never touches Qt widgets directly, it
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
      # True once run() ends on an error or a non-zero CLI exit (including a
      # cancel's terminate()) - the streamed text is then not a whole answer.
      self.failed = False

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
          self.failed = self.process is not None and self.process.returncode != 0
      except Exception as error:
          self.failed = True
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
