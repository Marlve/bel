# The ring's editable wedges - the ones the Settings card lets you relabel,
# reorder, or reassign - plus the placement rule for the Settings wedge
# itself. Kept out of pieMenu.py so settingsCard.py can read the same
# defaults and action list without importing pieMenu, which imports the
# actions registry, which is what builds the Settings wedge in the first
# place - that path back to pieMenu would be circular.

import cardStore

STORE_KEY = "wedges"

# How many messages a Claude chat card lets its session accumulate before
# starting over fresh - not a per-wedge field, but kept here alongside the
# other settings-editable config for the same reason (claudeChatCard.py needs it
# without importing pieMenu/settingsCard).
CHAT_CONTEXT_LIMIT_KEY = "claude_context_limit"
DEFAULT_CHAT_CONTEXT_LIMIT = 4

# Extra per-action config merged into a slot's entry alongside the id/label
# the user edits (e.g. the prompt bar placeholder Claude needs).
ACTION_EXTRAS = {
    "todo": {},
    "note": {},
    "claude": {"placeholder": "Ask Bel anything…"},
}

# (id, display name), in the order offered in the settings dropdown.
ACTION_CHOICES = [("todo", "Todo"), ("note", "Note"), ("claude", "Claude")]

DEFAULT_OTHER_WEDGES = [
    {"id": "todo", "label": "Todo"},
    {"id": "note", "label": "Note"},
    {"id": "claude", "label": "Claude"},
]

SETTINGS_ENTRY = {"id": "settings", "label": "Settings"}


def load_other_wedges():
    saved = cardStore.load(STORE_KEY, None)
    return saved if saved else [dict(entry) for entry in DEFAULT_OTHER_WEDGES]


def save_other_wedges(entries):
    cardStore.save(STORE_KEY, entries)


def load_chat_context_limit():
    return cardStore.load(CHAT_CONTEXT_LIMIT_KEY, DEFAULT_CHAT_CONTEXT_LIMIT)


def save_chat_context_limit(limit):
    cardStore.save(CHAT_CONTEXT_LIMIT_KEY, limit)


def bottom_pin_index(count):
    """Index closest to compass-down (180°) for a ring of this many wedges -
    see wedge_index() in pieMenu.py for the same 0=up, clockwise
    convention. Exact whenever count is even; for an odd count no wedge
    sits exactly at 180° so this picks whichever of the two neighbors is
    nearer (ties round to the lower index)."""
    return round(count / 2) % count


def full_config(other_entries):
    """The complete, ordered wedge list: the editable wedges plus Settings
    pinned as close to the bottom as the current count allows, wherever the
    editable wedges themselves land."""
    count = len(other_entries) + 1
    config = list(other_entries)
    config.insert(bottom_pin_index(count), dict(SETTINGS_ENTRY))
    return config


def resolve(entries):
    """Editable entries (just id + label) with each action's own extra
    config merged in, ready for pieMenu.build_wedges()."""
    return [{**entry, **ACTION_EXTRAS.get(entry["id"], {})} for entry in entries]
