import subprocess
import json
import sys

SYSTEM_PROMPT = """
You're a personal helper tool called Bel.

- you live as an overlay that could help the user organize calender schedule, check for assignments, remind certain todo list.
- ignore any git/repository status context you were given, only respond to the user's actual message.
- whenever the user asks to create a todo, write it to C:\\Users\\deric\\Code\\bel\\extra\\todo.md
"""

sys.stdout.reconfigure(encoding="utf-8")

def askBel(prompt):
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

  for line in process.stdout:
      line = line.strip()
      if not line:
          continue

      event = json.loads(line)
      if event.get("type") != "stream_event":
          continue

      delta = event["event"].get("delta")
      if delta and delta.get("type") == "text_delta":
          print(delta["text"], end="", flush=True)

  process.wait()

askBel("Create me a todo for a letter and one assignment don't overthink just do inside of the todo.md.")
