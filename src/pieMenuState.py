# The ring's phase machine and its tracked data - which wedge is
# hovered/chosen, the prompt text and rect it will be born from, and the
# wedges list itself. No Qt widgets: PieMenu (the view) and
# PieMenuAnimation read and write these fields directly, the same way
# EdgeDockDriver reads/writes EdgeDock.

import math
from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtCore import QPointF

import style
import wedgeConfig
from actions import ACTIONS

INNER_RADIUS = style.RING_INNER * style.RING_RADIUS  # hollow center doubles as the dead zone
HIT_RADIUS = style.RING_HIT_OUTER * style.RING_RADIUS

# The menu's life cycle. Input only counts while opening or open (or, once
# the prompt bar has arrived, while prompting); the exits play out untouched
# once started.
HIDDEN, OPENING, OPEN, SELECTING, HANDOFF, PROMPTING, CLOSING = (
    "hidden", "opening", "open", "selecting", "handoff", "prompting", "closing",
)


def wedge_index(dx, dy, count, deadzone=0, radius=None):
    """Index of the wedge (0 = up, going clockwise) that (dx, dy) points
    into, or None if the point is inside the deadzone or outside radius.
    dx/dy are a screen space offset from the menu's center - y grows
    downward.
    """
    dist = math.hypot(dx, dy)
    if dist < deadzone:
        return None
    if radius is not None and dist > radius:
        return None

    math_angle = math.degrees(math.atan2(-dy, dx)) % 360  # 0=right, 90=up
    compass_angle = (90 - math_angle) % 360  # 0=up, 90=right, clockwise
    wedge_width = 360 / count
    shifted = (compass_angle + wedge_width / 2) % 360
    return int(shifted // wedge_width)


def cycle_wedge(current, count, step):
    """Index of the wedge step (+1 = right/next, -1 = left/previous) away
    from current, wrapping around. current=None starts from just before the
    first wedge (step=+1) or just after the last (step=-1).
    """
    if current is None:
        current = -1 if step > 0 else 0
    return (current + step) % count


@dataclass
class Wedge:
    id: str
    label: str
    action: Callable[..., None]
    placeholder: Optional[str] = None  # set = ask for text first, and pass it to the action


# Which wedges the menu shows, in order. Todo/Note/Claude are user-editable
# via the Settings wedge (see wedgeConfig.py for persistence and
# defaults); Settings itself is always pinned as close to the bottom of the
# ring as the current wedge count allows, wherever the editable wedges land.
# Each entry's "id" picks an action factory from ACTIONS; any other key is
# that action's own config (e.g. "claude" reads "prompt", "settings" reads
# "on_change"). A "placeholder" sends the wedge through the prompt bar first.
def current_config(on_settings_change):
    others = wedgeConfig.resolve(wedgeConfig.load_other_wedges())
    config = wedgeConfig.full_config(others)
    for entry in config:
        if entry["id"] == "settings":
            entry["on_change"] = on_settings_change
    return config


def build_wedges(config, previous=()):
    """Wedges for `config`, in order. A slot whose action id matches one in
    `previous` reuses that Wedge's existing action object instead of
    calling its factory again - a fresh call would build a brand new toggle
    closure with no memory of an already-open Note/Todo card, silently
    orphaning it. Only label/placeholder refresh on a reused wedge; those
    are cheap to swap in place."""
    by_id = {wedge.id: wedge for wedge in previous}
    wedges = []
    for entry in config:
        existing = by_id.get(entry["id"])
        if existing is not None:
            existing.label = entry["label"]
            existing.placeholder = entry.get("placeholder")
            wedges.append(existing)
        else:
            wedges.append(Wedge(entry["id"], entry["label"], ACTIONS[entry["id"]](entry), entry.get("placeholder")))
    return wedges


class PieMenuState:
    """The ring's phase, which wedge is hovered/chosen, the prompt text and
    rect it will be born from, and the wedges list itself."""

    def __init__(self, on_settings_change):
        self.phase = HIDDEN
        self.anchor = QPointF(0, 0)
        self.hovered_wedge = None
        self.chosen_wedge = None
        self.prompt_text = None
        self.born_rect = None  # the prompt bar's last rect, which a card is born as
        self.wedges = build_wedges(current_config(on_settings_change))

    def applySettings(self, on_settings_change):
        """Called by the Settings card after a relabel/reorder/reassign is
        saved. The ring is always closed while that card is up - settings
        is itself a wedge pick - so nothing keyed to len(self.wedges)
        (hover_anims, prompt_flow) needs touching, only the wedges list."""
        self.wedges = build_wedges(current_config(on_settings_change), self.wedges)
