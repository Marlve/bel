# Registry of wedge action factories, keyed by a stable id. Each factory
# takes a wedge's config dict and returns a callable - pie_menu.py only ever
# calls that callable, it never touches these classes or configs directly.
# Add a new action by writing it in its own module here, then adding one
# entry below.
#
# A wedge whose config carries a "placeholder" is asked for text first, and
# its action is called with that text. Such an action must return a request
# object exposing `chunk(str)` and `finished()` signals, one per call - that
# is what a chat card wires itself to in order to show the answer. An action
# that supports real multi-turn (currently only "claude") also accepts a
# `session_id` kwarg and emits `session_started(str)` once per request, so a
# card can resume the same conversation on its next send.

from actions.announce import announce
from actions.claude_action import ClaudeAction, DEFAULT_PROMPT
from actions.todo_action import todo
from actions.note_action import note

ACTIONS = {
    "announce": lambda config: announce(config["label"]),
    "claude": lambda config: ClaudeAction(prompt=config.get("prompt", DEFAULT_PROMPT)),
    "todo": todo,
    "note": note,
}
