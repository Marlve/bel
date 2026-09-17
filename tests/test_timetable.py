import sys
import tempfile
import unittest
from datetime import date, time
from pathlib import Path
from zoneinfo import ZoneInfo

from PySide6.QtCore import QObject, Signal

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import timetable

MELBOURNE = ZoneInfo("Australia/Melbourne")

# A weekly Thursday lecture with one cancelled week, a one-off timed event
# stored in UTC, and an all-day assignment deadline.
FEED = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//EN
BEGIN:VEVENT
UID:lecture@test
DTSTART;TZID=Australia/Melbourne:20260903T100000
DTEND;TZID=Australia/Melbourne:20260903T120000
RRULE:FREQ=WEEKLY;COUNT=10
EXDATE;TZID=Australia/Melbourne:20260924T100000
SUMMARY:FIT3143 Lecture
END:VEVENT
BEGIN:VEVENT
UID:consult@test
DTSTART:20260917T230000Z
DTEND:20260918T000000Z
SUMMARY:Consultation
END:VEVENT
BEGIN:VEVENT
UID:due@test
DTSTART;VALUE=DATE:20260919
DTEND;VALUE=DATE:20260920
SUMMARY:ETW Assignment due
END:VEVENT
END:VCALENDAR
"""

THURSDAY = date(2026, 9, 17)


class CommandRangeTests(unittest.TestCase):
    def test_today_is_just_today(self):
        self.assertEqual(timetable.command_range("today", THURSDAY), (THURSDAY, date(2026, 9, 18)))

    def test_week_is_the_next_seven_days_starting_today(self):
        self.assertEqual(timetable.command_range("week", THURSDAY), (THURSDAY, date(2026, 9, 24)))


class EventsBetweenTests(unittest.TestCase):
    def events(self, start, end):
        return timetable.events_between(FEED, start, end, tz=MELBOURNE)

    def test_a_weekly_class_shows_up_on_the_day_it_repeats(self):
        events = self.events(THURSDAY, date(2026, 9, 18))

        self.assertEqual(
            events[0],
            {"day": THURSDAY, "start": time(10, 0), "end": time(12, 0), "title": "FIT3143 Lecture"},
        )

    def test_a_cancelled_week_is_left_out(self):
        events = self.events(date(2026, 9, 24), date(2026, 9, 25))

        self.assertEqual(events, [])

    def test_a_utc_event_is_shown_in_local_time_on_its_local_day(self):
        # 23:00 UTC Thursday is 09:00 Friday in Melbourne.
        events = self.events(date(2026, 9, 18), date(2026, 9, 19))

        self.assertEqual(events, [{"day": date(2026, 9, 18), "start": time(9, 0), "end": time(10, 0), "title": "Consultation"}])

    def test_an_all_day_event_has_no_times(self):
        events = self.events(date(2026, 9, 19), date(2026, 9, 20))

        self.assertEqual(events, [{"day": date(2026, 9, 19), "start": None, "end": None, "title": "ETW Assignment due"}])

    def test_events_come_back_in_time_order_across_the_range(self):
        events = self.events(THURSDAY, date(2026, 9, 24))

        self.assertEqual([event["title"] for event in events], ["FIT3143 Lecture", "Consultation", "ETW Assignment due"])


class FormatReplyTests(unittest.TestCase):
    LECTURE = {"day": THURSDAY, "start": time(10, 0), "end": time(12, 0), "title": "FIT3143 Lecture"}
    DUE = {"day": date(2026, 9, 19), "start": None, "end": None, "title": "ETW Assignment due"}

    def test_today_lists_one_line_per_event(self):
        reply = timetable.format_reply("today", [self.LECTURE, {**self.DUE, "day": THURSDAY}])

        self.assertEqual(reply, "10:00–12:00  FIT3143 Lecture\nall day  ETW Assignment due")

    def test_week_groups_events_under_a_day_heading(self):
        reply = timetable.format_reply("week", [self.LECTURE, self.DUE])

        self.assertEqual(
            reply,
            "**Thu 17 Sep**\n10:00–12:00  FIT3143 Lecture\n\n**Sat 19 Sep**\nall day  ETW Assignment due",
        )

    def test_an_empty_today_says_so(self):
        self.assertEqual(timetable.format_reply("today", []), "nothing on today")

    def test_an_empty_week_says_so(self):
        self.assertEqual(timetable.format_reply("week", []), "nothing in the next 7 days")


class DueBoxesTests(unittest.TestCase):
    LECTURE = FormatReplyTests.LECTURE
    DUE = FormatReplyTests.DUE

    def test_today_is_one_box_of_title_and_time_rows(self):
        boxes = timetable.due_boxes("today", [self.LECTURE, {**self.DUE, "day": THURSDAY}])

        self.assertEqual(boxes, [(None, [("FIT3143 Lecture", "10:00–12:00"), ("ETW Assignment due", "all day")])])

    def test_week_is_one_box_per_day_under_its_heading(self):
        boxes = timetable.due_boxes("week", [self.LECTURE, self.DUE])

        self.assertEqual(
            boxes,
            [("Thu 17 Sep", [("FIT3143 Lecture", "10:00–12:00")]), ("Sat 19 Sep", [("ETW Assignment due", "all day")])],
        )

    def test_nothing_on_is_no_boxes(self):
        self.assertEqual(timetable.due_boxes("week", []), [])


class AnswerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.url_path = Path(self.tmp.name) / "timetable.ical-url"
        self.fetched = []

    def fetch(self, url):
        self.fetched.append(url)
        return FEED

    def answer(self, command, fetch=None):
        return timetable.answer(command, THURSDAY, url_path=self.url_path, fetch=fetch or self.fetch, tz=MELBOURNE)

    def test_fetches_the_link_from_the_url_file_and_answers(self):
        self.url_path.write_text("https://example.com/timetable.ics\n", encoding="utf-8")

        reply = self.answer("today")

        self.assertEqual(self.fetched, ["https://example.com/timetable.ics"])
        self.assertEqual(
            reply,
            {"text": "10:00–12:00  FIT3143 Lecture", "boxes": [(None, [("FIT3143 Lecture", "10:00–12:00")])]},
        )

    def test_nothing_on_is_answered_in_words_with_no_boxes(self):
        self.url_path.write_text("https://example.com/timetable.ics", encoding="utf-8")

        reply = timetable.answer("today", date(2026, 9, 24), url_path=self.url_path, fetch=self.fetch, tz=MELBOURNE)

        self.assertEqual(reply, {"text": "nothing on today", "boxes": []})

    def test_a_webcal_link_is_fetched_over_https(self):
        self.url_path.write_text("webcal://example.com/timetable.ics", encoding="utf-8")

        self.answer("today")

        self.assertEqual(self.fetched, ["https://example.com/timetable.ics"])

    def test_a_missing_url_file_says_no_link_is_set(self):
        reply = self.answer("today")

        self.assertEqual(self.fetched, [])
        self.assertIn("no timetable link set", reply["text"])
        self.assertEqual(reply["boxes"], [])

    def test_a_failed_fetch_says_the_timetable_could_not_be_reached(self):
        self.url_path.write_text("https://example.com/timetable.ics", encoding="utf-8")

        def fail(url):
            raise OSError("timed out")

        self.assertEqual(self.answer("week", fetch=fail), {"text": "couldn't reach the timetable", "boxes": []})

    def test_a_feed_that_is_not_ical_says_it_could_not_be_read(self):
        self.url_path.write_text("https://example.com/timetable.ics", encoding="utf-8")

        self.assertEqual(
            self.answer("week", fetch=lambda url: b"<html>login</html>"),
            {"text": "couldn't read the timetable", "boxes": []},
        )


class FakeRequest(QObject):
    finished = Signal(object)

    def __init__(self, command):
        super().__init__()
        self.command = command
        self.started = False
        self.cancelled = False

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True


class CalendarQueryTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.results = []

    def factory(self, command):
        request = FakeRequest(command)
        self.requests.append(request)
        return request

    def test_starts_a_request_for_its_command_and_hands_back_the_reply(self):
        query = timetable.CalendarQuery("week", self.results.append, request_factory=self.factory)

        query.start()
        self.requests[0].finished.emit({"text": "nothing in the next 7 days", "boxes": []})

        self.assertEqual(self.requests[0].command, "week")
        self.assertTrue(self.requests[0].started)
        self.assertEqual(self.results, [{"text": "nothing in the next 7 days", "boxes": []}])

    def test_a_cancelled_query_never_answers(self):
        query = timetable.CalendarQuery("today", self.results.append, request_factory=self.factory)
        query.start()

        query.cancel()
        self.requests[0].finished.emit({"text": "late reply", "boxes": []})

        self.assertTrue(self.requests[0].cancelled)
        self.assertEqual(self.results, [])


if __name__ == "__main__":
    unittest.main()
