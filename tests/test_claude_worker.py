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


if __name__ == "__main__":
    unittest.main()
