# `! today` and `! week` (.scratch/today-week/issues/01): every event in
# the user's timetable for today or the next 7 days, read straight from the
# timetable's iCal link. No Google Calendar MCP and no Claude call, so the
# answer is a fetch plus a date filter. Nothing is cached, since a fresh
# timetable is the point.
#
# The link is private (anyone holding it can read the timetable), so it
# lives only in a local file under ~/.bel/, never in the repo.

import urllib.request
from datetime import date, datetime, time, timedelta
from pathlib import Path

import icalendar
import recurring_ical_events
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from backgroundRequest import BackgroundRequest

URL_PATH = Path.home() / ".bel" / "timetable.ical-url"
FETCH_TIMEOUT_SECONDS = 10

COMMANDS = ("today", "week")


def command_range(command, today):
    """The days a command covers, as (first day, day after the last)."""
    days = 7 if command == "week" else 1
    return today, today + timedelta(days=days)


def events_between(ics, start, end, tz=None):
    """Every event occurring from `start` up to (not including) `end`, with
    weekly classes expanded into their real occurrences (cancelled weeks
    left out), in local time and time order. An all-day event has no
    start/end time."""
    tz = tz or datetime.now().astimezone().tzinfo
    calendar = icalendar.Calendar.from_ical(ics)
    occurrences = recurring_ical_events.of(calendar).between(
        datetime.combine(start, time(), tzinfo=tz),
        datetime.combine(end, time(), tzinfo=tz),
    )
    events = []
    for occurrence in occurrences:
        begins = occurrence["DTSTART"].dt
        title = str(occurrence.get("SUMMARY", "")).strip() or "(untitled)"
        if isinstance(begins, datetime):
            begins = begins.astimezone(tz) if begins.tzinfo else begins.replace(tzinfo=tz)
            ends = occurrence["DTEND"].dt.astimezone(tz) if "DTEND" in occurrence else begins
            events.append({"day": begins.date(), "start": begins.time(), "end": ends.time(), "title": title})
        else:
            # An all-day event that began before the range belongs to its
            # first day inside it.
            events.append({"day": max(begins, start), "start": None, "end": None, "title": title})
    return sorted(events, key=lambda event: (event["day"], event["start"] is not None, event["start"] or time()))


def event_label(event):
    if event["start"] is None:
        return "all day"
    return f"{event['start']:%H:%M}–{event['end']:%H:%M}"


def due_boxes(command, events):
    """The "what is due" boxes (.scratch/command-styling/issues/01): one
    box of (title, time) rows for `! today`, or one per day under its
    heading for `! week`. No events is no boxes."""
    if command == "today":
        return [(None, [(event["title"], event_label(event)) for event in events])] if events else []
    boxes = []
    for event in events:
        heading = f"{event['day']:%a} {event['day'].day} {event['day']:%b}"
        if not boxes or boxes[-1][0] != heading:
            boxes.append((heading, []))
        boxes[-1][1].append((event["title"], event_label(event)))
    return boxes


def format_reply(command, events):
    """Bel's reply as text: one line per event, grouped under a day heading
    for `! week`. Kept as the turn's text behind the boxes."""
    if not events:
        return "nothing on today" if command == "today" else "nothing in the next 7 days"
    return "\n\n".join(
        (f"**{heading}**\n" if heading else "") + "\n".join(f"{label}  {title}" for title, label in rows)
        for heading, rows in due_boxes(command, events)
    )


def fetch(url):
    with urllib.request.urlopen(url, timeout=FETCH_TIMEOUT_SECONDS) as response:
        return response.read()


def saved_link(url_path=None):
    """The timetable link Settings holds, or "" when none is set."""
    try:
        return (url_path or URL_PATH).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def save_link(link, url_path=None):
    """Stores the link, or forgets it when `link` is blank."""
    url_path = url_path or URL_PATH
    link = link.strip()
    if link:
        url_path.parent.mkdir(parents=True, exist_ok=True)
        url_path.write_text(link, encoding="utf-8")
    else:
        url_path.unlink(missing_ok=True)


def answer(command, today=None, url_path=None, fetch=fetch, tz=None):
    """The whole command, start to finish: read the link, fetch the feed,
    list the range's events. Returns {"text", "boxes"}; every failure is
    answered in words with no boxes rather than raised."""
    today = today or date.today()
    url_path = url_path or URL_PATH
    url = saved_link(url_path)
    if not url:
        return {"text": "no timetable link set — add your calendar's iCal link in Settings", "boxes": []}
    if url.startswith("webcal://"):
        # A subscription link is the same feed over https.
        url = "https://" + url[len("webcal://"):]
    try:
        ics = fetch(url)
    except (OSError, ValueError):
        return {"text": "couldn't reach the timetable", "boxes": []}
    try:
        events = events_between(ics, *command_range(command, today), tz=tz)
    except Exception:
        return {"text": "couldn't read the timetable", "boxes": []}
    return {"text": format_reply(command, events), "boxes": due_boxes(command, events)}


class TimetableWorker(QObject):
    finished = Signal(object)

    def __init__(self, command):
        super().__init__()
        self.command = command

    def run(self):
        self.finished.emit(answer(self.command))


class TimetableRequest(BackgroundRequest):
    """One answer(), off the UI thread since the fetch is network I/O."""

    finished = Signal(object)

    def __init__(self, command, parent=None):
        super().__init__(TimetableWorker(command), parent)
        self.worker.finished.connect(self.onWorkerFinished)

    def onWorkerFinished(self, reply):
        self.stopThread()
        self.finished.emit(reply)

    def cancel(self):
        # Nothing to interrupt mid-fetch - urlopen's own timeout bounds it.
        self.stopThread()


class CalendarQuery:
    """Drives one `! today` / `! week` for ChatCard, the same start/cancel
    shape as vaultSearch.ExplainQuery. `on_result` gets answer()'s reply."""

    def __init__(self, command, on_result, request_factory=TimetableRequest):
        self.command = command
        self.on_result = on_result
        self.request_factory = request_factory  # swappable in tests, so no real thread or fetch
        self.request = None
        self.cancelled = False
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.cancel)

    def start(self):
        self.request = self.request_factory(self.command)
        self.request.finished.connect(self.onFinished)
        self.request.start()

    def onFinished(self, reply):
        self.disconnectAboutToQuit()
        if not self.cancelled:
            self.on_result(reply)

    def cancel(self):
        self.cancelled = True
        if self.request is not None:
            self.request.cancel()

    def disconnectAboutToQuit(self):
        # See ClaudeQuery.disconnectAboutToQuit - a connected bound method
        # would keep every past query alive (issue 06).
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.disconnect(self.cancel)
