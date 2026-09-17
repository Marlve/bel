# `! today` and `! week` (.scratch/today-week/issues/01): every event in
# Derich's timetable for today or the next 7 days, read straight from the
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


def event_line(event):
    if event["start"] is None:
        return f"all day  {event['title']}"
    return f"{event['start']:%H:%M}–{event['end']:%H:%M}  {event['title']}"


def format_reply(command, events):
    """Bel's reply text: one line per event, grouped under a day heading for
    `! week`."""
    if not events:
        return "nothing on today" if command == "today" else "nothing in the next 7 days"
    if command == "today":
        return "\n".join(event_line(event) for event in events)
    days = []
    for event in events:
        if not days or days[-1][0] != event["day"]:
            days.append((event["day"], []))
        days[-1][1].append(event_line(event))
    return "\n\n".join(
        f"**{day:%a} {day.day} {day:%b}**\n" + "\n".join(lines) for day, lines in days
    )


def fetch(url):
    with urllib.request.urlopen(url, timeout=FETCH_TIMEOUT_SECONDS) as response:
        return response.read()


def answer(command, today=None, url_path=None, fetch=fetch, tz=None):
    """The whole command, start to finish: read the link, fetch the feed,
    list the range's events. Every failure is answered in words rather than
    raised."""
    today = today or date.today()
    url_path = url_path or URL_PATH
    try:
        url = url_path.read_text(encoding="utf-8").strip()
    except OSError:
        url = ""
    if not url:
        return f"no timetable link set — put the iCal link in {url_path}"
    if url.startswith("webcal://"):
        # A subscription link is the same feed over https.
        url = "https://" + url[len("webcal://"):]
    try:
        ics = fetch(url)
    except (OSError, ValueError):
        return "couldn't reach the timetable"
    try:
        events = events_between(ics, *command_range(command, today), tz=tz)
    except Exception:
        return "couldn't read the timetable"
    return format_reply(command, events)


class TimetableWorker(QObject):
    finished = Signal(str)

    def __init__(self, command):
        super().__init__()
        self.command = command

    def run(self):
        self.finished.emit(answer(self.command))


class TimetableRequest(BackgroundRequest):
    """One answer(), off the UI thread since the fetch is network I/O."""

    finished = Signal(str)

    def __init__(self, command, parent=None):
        super().__init__(TimetableWorker(command), parent)
        self.worker.finished.connect(self.onWorkerFinished)

    def onWorkerFinished(self, text):
        self.stopThread()
        self.finished.emit(text)

    def cancel(self):
        # Nothing to interrupt mid-fetch - urlopen's own timeout bounds it.
        self.stopThread()


class CalendarQuery:
    """Drives one `! today` / `! week` for ChatCard, the same start/cancel
    shape as vaultSearch.ExplainQuery. `on_result` gets the reply text."""

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

    def onFinished(self, text):
        self.disconnectAboutToQuit()
        if not self.cancelled:
            self.on_result(text)

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
