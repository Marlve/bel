import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import cardStore
from calendarNudge import CalendarNudgeQuery, STORE_KEY, parse_response


class ParseResponseTests(unittest.TestCase):
    def test_clean_json(self):
        text = '{"items": [{"title": "Essay draft", "due": "Fri"}], "before": "Friday"}'
        data = parse_response(text)
        self.assertEqual(data["items"], [{"title": "Essay draft", "due": "Fri"}])
        self.assertEqual(data["before"], "Friday")

    def test_fenced_json_is_unwrapped(self):
        text = '```json\n{"items": [], "before": "Friday"}\n```'
        data = parse_response(text)
        self.assertEqual(data["items"], [])

    def test_leading_commentary_is_ignored(self):
        text = 'Sure, here you go:\n{"items": [{"title": "A", "due": "Mon"}], "before": "Monday"}'
        data = parse_response(text)
        self.assertEqual(len(data["items"]), 1)

    def test_empty_items_list(self):
        data = parse_response('{"items": []}')
        self.assertEqual(data["items"], [])

    def test_missing_before_defaults_to_soon(self):
        data = parse_response('{"items": []}')
        self.assertEqual(data["before"], "soon")

    def test_garbage_returns_none(self):
        self.assertIsNone(parse_response("not json at all"))

    def test_items_not_a_list_returns_none(self):
        self.assertIsNone(parse_response('{"items": "nope"}'))

    def test_items_missing_title_are_dropped(self):
        text = '{"items": [{"due": "Fri"}, {"title": "Keep me", "due": "Mon"}]}'
        data = parse_response(text)
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["title"], "Keep me")


class CalendarNudgeQueryCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.original_dir = cardStore.STORE_DIR
        cardStore.STORE_DIR = Path(self.tmp.name) / "cards"
        self.addCleanup(setattr, cardStore, "STORE_DIR", self.original_dir)

        self.calls = []
        self.query = CalendarNudgeQuery(lambda items, before: self.calls.append((items, before)))
        self.addCleanup(self.query.request.deleteLater)

    def test_cache_hit_with_items_reports_them_without_starting_a_request(self):
        cardStore.save(STORE_KEY, {
            "date": date.today().isoformat(),
            "items": [{"title": "Essay draft", "due": "Fri"}],
            "before": "Friday",
        })
        self.query.start()
        self.assertEqual(self.calls, [([{"title": "Essay draft", "due": "Fri"}], "Friday")])
        self.assertFalse(self.query.request.thread.isRunning())

    def test_cache_hit_with_empty_items_stays_quiet_without_starting_a_request(self):
        cardStore.save(STORE_KEY, {"date": date.today().isoformat(), "items": [], "before": ""})
        self.query.start()
        self.assertEqual(self.calls, [])
        self.assertFalse(self.query.request.thread.isRunning())

    def test_stale_cache_from_a_previous_day_is_ignored(self):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        cardStore.save(STORE_KEY, {
            "date": yesterday,
            "items": [{"title": "Old item", "due": "Mon"}],
            "before": "Monday",
        })
        self.query.start()
        self.assertEqual(self.calls, [])
        self.assertTrue(self.query.request.thread.isRunning())
        self.query.request.cancel()

    def test_no_cache_starts_the_live_request(self):
        self.query.start()
        self.assertEqual(self.calls, [])
        self.assertTrue(self.query.request.thread.isRunning())
        self.query.request.cancel()

    def test_finished_caches_a_non_empty_result_with_todays_date(self):
        self.query.text = '{"items": [{"title": "Essay draft", "due": "Fri"}], "before": "Friday"}'
        self.query.onFinished()
        self.assertEqual(cardStore.load(STORE_KEY, None), {
            "date": date.today().isoformat(),
            "items": [{"title": "Essay draft", "due": "Fri"}],
            "before": "Friday",
        })
        self.assertEqual(self.calls, [([{"title": "Essay draft", "due": "Fri"}], "Friday")])

    def test_finished_caches_a_legitimately_empty_result(self):
        self.query.text = '{"items": [], "before": ""}'
        self.query.onFinished()
        self.assertEqual(cardStore.load(STORE_KEY, None), {
            "date": date.today().isoformat(),
            "items": [],
            "before": "soon",
        })
        self.assertEqual(self.calls, [])

    def test_finished_does_not_cache_an_unparseable_reply(self):
        self.query.text = "not json at all"
        self.query.onFinished()
        self.assertIsNone(cardStore.load(STORE_KEY, None))
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
