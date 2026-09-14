# Entry point Bel's Claude subprocess calls via its Bash tool to read and
# update the todo list (see askBel()'s --allowedTools in claude.py) - the
# subprocess is a separate OS process with no reference to the running
# TodoCard, so this is the only thing it can actually reach. Goes through
# cardStore like TodoCard itself does, so size/pos survive untouched.

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cardStore

STORE_KEY = "todo"


def list_todos():
    todo = cardStore.load(STORE_KEY, {"items": []})
    print(json.dumps(todo["items"]))


def add_todo(text):
    text = text.strip()
    if not text:
        print("usage: cardTool.py add-todo <task text>", file=sys.stderr)
        sys.exit(1)
    todo = cardStore.load(STORE_KEY, {"items": []})
    todo["items"].append({"text": text, "done": False})
    cardStore.save(STORE_KEY, todo)
    print(json.dumps(todo["items"]))


def toggle_todo(text):
    # Matches by text rather than list position: the caller (Bel's Claude
    # subprocess) only ever has the text from its own earlier list-todos
    # call, and a position can drift out from under it if the user ticks a
    # different item locally in between (TodoList.finishRemoval splices the
    # list). Only matches a not-yet-done item, so re-running this after the
    # item's already been toggled (and is just waiting on its removal
    # animation) errors instead of silently un-toggling it.
    text = text.strip()
    if not text:
        print("usage: cardTool.py toggle-todo <task text>", file=sys.stderr)
        sys.exit(1)
    todo = cardStore.load(STORE_KEY, {"items": []})
    items = todo["items"]
    for item in items:
        if not item["done"] and item["text"] == text:
            item["done"] = True
            cardStore.save(STORE_KEY, todo)
            print(json.dumps(items))
            return
    print(f"error: no open todo matching {text!r}", file=sys.stderr)
    sys.exit(1)


COMMANDS = {
    "list-todos": lambda args: list_todos(),
    "add-todo": lambda args: add_todo(" ".join(args)),
    "toggle-todo": lambda args: toggle_todo(" ".join(args)),
}


def main(argv):
    if not argv or argv[0] not in COMMANDS:
        print(f"usage: cardTool.py {{{'|'.join(COMMANDS)}}} [args]", file=sys.stderr)
        return 1
    COMMANDS[argv[0]](argv[1:])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
