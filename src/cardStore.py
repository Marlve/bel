# Small persistent store for the todo and note cards - just enough for
# either to survive an app restart. One JSON file, read whole and rewritten
# whole; these payloads are a handful of items long, never worth a database.

import json
from pathlib import Path

STORE_PATH = Path.home() / ".bel" / "cards.json"


def load(key, default):
    try:
        data = json.loads(STORE_PATH.read_text())
    except (OSError, ValueError):
        return default
    return data.get(key, default)


def save(key, value):
    try:
        data = json.loads(STORE_PATH.read_text())
    except (OSError, ValueError):
        data = {}
    data[key] = value
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps(data))
