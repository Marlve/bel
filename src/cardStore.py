# Small persistent store for the todo/note/chat/wedge cards - one JSON file
# per key under ~/.bel/cards/, rather than one shared file, so a given key
# (e.g. note or todo) can later be exposed to something else (Bel's Claude
# subprocess) without exposing the rest. Payloads are a handful of items
# long, never worth a database.

import json
from pathlib import Path

STORE_DIR = Path.home() / ".bel" / "cards"
LEGACY_STORE_PATH = Path.home() / ".bel" / "cards.json"


def key_path(key):
    return STORE_DIR / f"{key}.json"


def migrate_legacy():
    """One-time move from the old single shared cards.json into the new
    per-key files, so switching formats doesn't drop whatever was already
    saved there. Renames the legacy file out of the way as soon as it's
    read, so every call after the first is a cheap no-op (missing file)."""
    try:
        data = json.loads(LEGACY_STORE_PATH.read_text())
    except (OSError, ValueError):
        return
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    for key, value in data.items():
        path = key_path(key)
        if not path.exists():
            path.write_text(json.dumps(value))
    LEGACY_STORE_PATH.rename(LEGACY_STORE_PATH.with_suffix(".json.bak"))


def load(key, default):
    migrate_legacy()
    try:
        data = json.loads(key_path(key).read_text())
    except (OSError, ValueError):
        return default
    return data


def save(key, value):
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    key_path(key).write_text(json.dumps(value))
