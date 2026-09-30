import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import claude


class FakeProcess:
    def __init__(self, returncode):
        self.returncode = returncode


def answer(returncode):
    """A stand-in askBel() whose CLI process exits with `returncode`."""

    def ask(prompt, session_id=None, on_process=None, on_session=None):
        on_process(FakeProcess(returncode))
        yield "partial "
        yield "answer"

    return ask


class FakePopen:
    """A `claude` subprocess that streams nothing - these tests only care
    about the argv askBel() built, not the answer that comes back."""

    def __init__(self, args):
        self.args = args
        self.stdout = []
        self.returncode = 0

    def wait(self):
        pass


class ClaudeWorkerFailedTests(unittest.TestCase):
    """`failed` lets a caller tell a complete answer from an error or a
    cut-off one - ExplainQuery must never offer to save either (card.md)."""

    def run_worker(self, ask):
        worker = claude.ClaudeWorker("prompt")
        with patch.object(claude, "askBel", ask):
            worker.run()
        return worker

    def test_a_clean_exit_is_not_failed(self):
        self.assertFalse(self.run_worker(answer(0)).failed)

    def test_a_non_zero_exit_is_failed(self):
        # What a timeout's terminate() or a CLI error exit looks like.
        self.assertTrue(self.run_worker(answer(1)).failed)

    def test_an_exception_is_failed(self):
        def ask(prompt, session_id=None, on_process=None, on_session=None):
            raise OSError("claude not found")
            yield

        self.assertTrue(self.run_worker(ask).failed)


class AskBelArgsTests(unittest.TestCase):
    """One prompt for every path - chat, `?` and the todo wedge (Derich,
    2026-09-18). What keeps the strict-output callers working is BEL_PROMPT's
    last rule, not a prompt of their own."""

    def argv(self, **kwargs):
        spawned = []

        def popen(args, **rest):
            process = FakePopen(args)
            spawned.append(process)
            return process

        with patch.object(claude.subprocess, "Popen", popen):
            list(claude.askBel("hi", **kwargs))
        return spawned[0].args

    def system_prompt(self, argv):
        return argv[argv.index("--append-system-prompt") + 1]

    def test_the_plain_prompt_is_what_a_caller_gets_by_default(self):
        self.assertEqual(self.system_prompt(self.argv()), claude.BEL_PROMPT)




class SystemPromptTests(unittest.TestCase):
    """BEL_PROMPT is the only system prompt; one whole literal, so reading it
    tells you everything every call sends."""

    def test_a_named_output_format_outranks_everything_else(self):
        # What lets one prompt serve a Korean `?` lookup ("Reply with only
        # the translation, no explanation") as well as chat. Without this
        # rule Bel talks over it and the parse breaks.
        self.assertIn("obey it exactly and reply with nothing else", claude.BEL_PROMPT)
        self.assertIn("outranks every rule above", claude.BEL_PROMPT)

    def test_it_keeps_the_load_bearing_rules(self):
        # The CLI is told to ignore repo context it may pick up, and Bel has
        # no view onto the to-do list.
        self.assertIn("ignore any git/repository status context", claude.BEL_PROMPT)
        self.assertIn("to-do list", claude.BEL_PROMPT)
