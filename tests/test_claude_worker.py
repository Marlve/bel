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

    def ask(prompt, session_id=None, system_prompt=None, on_process=None, on_session=None):
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
        def ask(prompt, session_id=None, system_prompt=None, on_process=None, on_session=None):
            raise OSError("claude not found")
            yield

        self.assertTrue(self.run_worker(ask).failed)


class AskBelArgsTests(unittest.TestCase):
    """The system prompt is per-call, not global. Chat gets the tutor
    persona; `?` lookups, `! organize` and the todo wedge keep the plain
    prompt, whose "reply with only a JSON array" answers a tutor would
    otherwise talk over."""

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

    def test_a_caller_can_ask_for_the_tutor_prompt_instead(self):
        argv = self.argv(system_prompt=claude.TUTOR_PROMPT)
        self.assertEqual(self.system_prompt(argv), claude.TUTOR_PROMPT)



class SystemPromptTests(unittest.TestCase):
    """What separates the two prompts. Each is one whole literal, so reading
    one tells you everything that call sends. Socratic mode is not a third
    prompt - it can't be, see SocraticRuleTests."""

    def test_only_the_plain_prompt_asks_for_short_answers(self):
        # Teaching needs room; a command reply does not. Splitting the
        # prompt per path is what let the terseness rule stay on one of them.
        self.assertIn("short and concise", claude.BEL_PROMPT)
        self.assertNotIn("short and concise", claude.TUTOR_PROMPT)

    def test_every_prompt_keeps_the_load_bearing_rules(self):
        # The CLI is told to ignore repo context it may pick up, and Bel has
        # no view onto the to-do list - true of a tutor as much as a helper.
        for prompt in (claude.BEL_PROMPT, claude.TUTOR_PROMPT):
            self.assertIn("ignore any git/repository status context", prompt)
            self.assertIn("to-do list", prompt)


class SocraticRuleTests(unittest.TestCase):
    """Why socratic mode is a message addendum and not a third system prompt.

    Measured against the real CLI on 2026-09-18: a fresh session obeys its
    --append-system-prompt, a --resume'd one ignores it and keeps the prompt
    the session was created with. So a system-prompt swap would flip the
    toggle, report "socratic mode on", and change nothing about the answer -
    exactly the mid-conversation case the mode exists for.
    """

    def test_the_rule_is_not_a_system_prompt(self):
        self.assertFalse(hasattr(claude, "SOCRATIC_PROMPT"))

    def test_the_rule_stands_apart_from_the_message_it_rides_on(self):
        # Appended to his own line, so it has to read as an aside rather than
        # as part of the question.
        self.assertTrue(claude.SOCRATIC_RULE.startswith(chr(10)))
        self.assertIn("socratic mode is on", claude.SOCRATIC_RULE)

    def test_the_rule_does_not_repeat_the_teaching_persona(self):
        # The persona is already on the session via TUTOR_PROMPT; repeating it
        # every turn would just spend tokens.
        self.assertNotIn("You're a tutor", claude.SOCRATIC_RULE)


class WorkerSystemPromptTests(unittest.TestCase):
    """ClaudeWorker is the only thing between ClaudeRequest and askBel, so
    a system prompt that stops here never reaches the CLI."""

    def test_the_worker_hands_its_system_prompt_to_ask_bel(self):
        seen = {}

        def ask(prompt, session_id=None, system_prompt=None, on_process=None, on_session=None):
            seen["system_prompt"] = system_prompt
            yield "ok"

        worker = claude.ClaudeWorker("prompt", system_prompt=claude.TUTOR_PROMPT)
        with patch.object(claude, "askBel", ask):
            worker.run()
        self.assertEqual(seen["system_prompt"], claude.TUTOR_PROMPT)


if __name__ == "__main__":
    unittest.main()
