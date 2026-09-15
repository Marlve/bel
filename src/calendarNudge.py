# Startup trigger for the calendar nudge card (calendar-nudge.md): builds
# the one-off prompt asking Bel to look at the next NUDGE_WINDOW_DAYS days of
# calendar, excluding recurring classes/coursework and anything that repeats
# weekly or more often, and parses its JSON-only reply into the plain items
# CalendarNudgeCard displays.
#
# Reuses ClaudeRequest (actions/claudeAction.py) - the existing generic
# "stream one CLI call on a background QThread" wrapper - rather than
# duplicating askBel's threading dance for this one extra call site.

import json
from datetime import date

from PySide6.QtWidgets import QApplication

import cardStore
from actions.claudeAction import ClaudeRequest

STORE_KEY = "calendar_nudge"
NUDGE_WINDOW_DAYS = 7

PROMPT = f"""Look at my Google Calendar for the next {NUDGE_WINDOW_DAYS} days.
List only upcoming, non-repeating items worth a heads-up (assignments due,
one-time events) - exclude recurring class/coursework sessions entirely, and
exclude anything that repeats weekly or more often (treat those as routine,
not worth a nudge).

Respond with ONLY raw JSON, no markdown fences, no commentary, in exactly
this shape:
{{"items": [{{"title": "...", "due": "..."}}], "before": "..."}}
`due` should be a short human string for that one item (e.g. "Fri",
"tomorrow"). `before` should be a short human string covering every item
returned (e.g. "Friday"), for a one-line summary.
If nothing qualifies, respond with {{"items": [], "before": ""}}.
"""


def parse_response(text):
    """Best-effort JSON parse of Bel's reply - a stray code fence or a
    leading/trailing sentence (the model doesn't always follow "no
    commentary" exactly) shouldn't crash the nudge, just suppress it.
    Returns None on anything unparseable or shaped wrong."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        newline = text.find("\n")
        if newline != -1:
            text = text[newline + 1:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    items = data.get("items")
    if not isinstance(items, list):
        return None
    items = [item for item in items if isinstance(item, dict) and item.get("title")]
    return {"items": items, "before": data.get("before") or "soon"}


class CalendarNudgeQuery:
    """Runs the startup query at most once per day and reports parsed items
    when done - or nothing at all on any failure or empty result, since a
    broken/quiet startup nudge should never be visible as an error
    (calendar-nudge.md's card has no error state, only quiet/nudge/expand).

    A same-day result (items or the legitimate "nothing due" empty list) is
    cached via cardStore so a later restart the same day reuses it instead
    of firing another live query. The cache only records the query result,
    not whether the card was dismissed - a restart always shows the day's
    cached items again, since the point of caching is to let the user see
    them again without re-asking Bel."""

    def __init__(self, on_items):
        self.on_items = on_items
        self.text = ""
        self.request = ClaudeRequest(PROMPT)
        self.request.chunk.connect(self.onChunk)
        self.request.finished.connect(self.onFinished)

        # Mirrors ClaudeAction's own aboutToQuit wiring (actions/claudeAction.py)
        # so this one-off request's subprocess/QThread can't outlive the app if
        # it quits while the startup query is still in flight.
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.request.cancel)

    def start(self):
        cached = cardStore.load(STORE_KEY, None)
        if isinstance(cached, dict) and cached.get("date") == date.today().isoformat():
            items = cached.get("items")
            if items:
                self.on_items(items, cached.get("before"))
            return
        self.request.start()

    def onChunk(self, text):
        self.text += text

    def onFinished(self):
        data = parse_response(self.text)
        if data is None:
            return
        cardStore.save(STORE_KEY, {"date": date.today().isoformat(), **data})
        if data["items"]:
            self.on_items(data["items"], data["before"])
