import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from calendarNudge import parse_response


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


if __name__ == "__main__":
    unittest.main()
