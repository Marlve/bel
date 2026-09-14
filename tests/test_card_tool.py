import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import cardStore
import cardTool

CARD_TOOL_PATH = Path(__file__).resolve().parent.parent / "src" / "cardTool.py"


class CardToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_dir = cardStore.STORE_DIR
        self.original_legacy_path = cardStore.LEGACY_STORE_PATH
        cardStore.STORE_DIR = Path(self.tmp.name) / "cards"
        cardStore.LEGACY_STORE_PATH = Path(self.tmp.name) / "cards.json"

    def tearDown(self):
        cardStore.STORE_DIR = self.original_dir
        cardStore.LEGACY_STORE_PATH = self.original_legacy_path
        self.tmp.cleanup()

    def test_list_todos_on_empty_store_prints_empty_list(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cardTool.list_todos()
        self.assertEqual(buf.getvalue().strip(), "[]")

    def test_add_todo_appends_an_open_item(self):
        cardTool.add_todo("buy milk")
        self.assertEqual(
            cardStore.load("todo", None)["items"],
            [{"text": "buy milk", "done": False}],
        )

    def test_add_todo_preserves_existing_size_and_pos(self):
        cardStore.save("todo", {"items": [], "size": [200, 300], "pos": [10, 20]})
        cardTool.add_todo("buy milk")
        saved = cardStore.load("todo", None)
        self.assertEqual(saved["size"], [200, 300])
        self.assertEqual(saved["pos"], [10, 20])

    def test_toggle_todo_flips_done(self):
        cardStore.save("todo", {"items": [{"text": "buy milk", "done": False}]})
        cardTool.toggle_todo("buy milk")
        self.assertTrue(cardStore.load("todo", None)["items"][0]["done"])

    def test_toggle_todo_ignores_an_already_done_item_with_the_same_text(self):
        # No re-toggle back to open: once an item's done, a repeat call
        # (e.g. the model retrying) should error, not silently un-tick it.
        cardStore.save("todo", {"items": [{"text": "buy milk", "done": True}]})
        with self.assertRaises(SystemExit):
            cardTool.toggle_todo("buy milk")

    def test_toggle_todo_matches_the_first_open_item_when_text_is_duplicated(self):
        cardStore.save("todo", {"items": [
            {"text": "buy milk", "done": True},
            {"text": "buy milk", "done": False},
        ]})
        cardTool.toggle_todo("buy milk")
        self.assertEqual(
            cardStore.load("todo", None)["items"],
            [{"text": "buy milk", "done": True}, {"text": "buy milk", "done": True}],
        )

    def test_toggle_todo_no_match_exits_nonzero_without_crashing(self):
        cardStore.save("todo", {"items": []})
        with self.assertRaises(SystemExit) as ctx:
            cardTool.toggle_todo("buy milk")
        self.assertNotEqual(ctx.exception.code, 0)

    def test_toggle_todo_with_no_text_exits_nonzero_without_crashing(self):
        with self.assertRaises(SystemExit):
            cardTool.toggle_todo("")

    def test_add_todo_with_no_text_exits_nonzero_without_crashing(self):
        with self.assertRaises(SystemExit):
            cardTool.add_todo("   ")

    def test_main_dispatches_add_then_list(self):
        cardTool.main(["add-todo", "buy milk"])
        self.assertEqual(
            cardStore.load("todo", None)["items"],
            [{"text": "buy milk", "done": False}],
        )

    def test_main_joins_unquoted_multi_word_args(self):
        cardTool.main(["add-todo", "buy", "milk"])
        self.assertEqual(
            cardStore.load("todo", None)["items"],
            [{"text": "buy milk", "done": False}],
        )

    def test_main_dispatches_toggle_by_text(self):
        cardStore.save("todo", {"items": [{"text": "buy milk", "done": False}]})
        cardTool.main(["toggle-todo", "buy", "milk"])
        self.assertTrue(cardStore.load("todo", None)["items"][0]["done"])

    def test_main_rejects_unknown_command(self):
        self.assertEqual(cardTool.main(["bogus-command"]), 1)


class CardToolSubprocessTests(unittest.TestCase):
    """One end-to-end check of the exact shape Bel's Claude subprocess will
    invoke this script with (python <path> <command> <args...>), so quoting
    and argv handling are covered, not just the Python-level functions."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        # cardStore always reads ~/.bel - point HOME/USERPROFILE at the temp
        # dir for the child process so this never touches the real store.
        self.env = {**os.environ, "HOME": str(self.tmp.name), "USERPROFILE": str(self.tmp.name)}

    def tearDown(self):
        self.tmp.cleanup()

    def run_tool(self, *args):
        return subprocess.run(
            [sys.executable, str(CARD_TOOL_PATH), *args],
            capture_output=True, text=True, env=self.env,
        )

    def test_add_then_list_round_trips_through_a_real_subprocess(self):
        add_result = self.run_tool("add-todo", "buy milk")
        self.assertEqual(add_result.returncode, 0, add_result.stderr)
        self.assertEqual(json.loads(add_result.stdout), [{"text": "buy milk", "done": False}])

        list_result = self.run_tool("list-todos")
        self.assertEqual(json.loads(list_result.stdout), [{"text": "buy milk", "done": False}])

    def test_toggle_by_text_round_trips_through_a_real_subprocess(self):
        self.run_tool("add-todo", "buy", "milk")  # unquoted multi-word, as a caller that forgets quotes would send it

        toggle_result = self.run_tool("toggle-todo", "buy", "milk")

        self.assertEqual(toggle_result.returncode, 0, toggle_result.stderr)
        self.assertEqual(json.loads(toggle_result.stdout), [{"text": "buy milk", "done": True}])


if __name__ == "__main__":
    unittest.main()
