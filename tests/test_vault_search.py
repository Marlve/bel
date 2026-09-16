import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import vaultIndex
import vaultSearch


class SearchNotesTests(unittest.TestCase):
    def setUp(self):
        self.vault_dir = tempfile.TemporaryDirectory()
        self.db_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.vault_dir.cleanup)
        self.addCleanup(self.db_dir.cleanup)
        self.vault = Path(self.vault_dir.name)
        self.db_path = Path(self.db_dir.name) / "vault-index.sqlite3"

    def refresh(self):
        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)

    def test_hit_on_existing_reference_note(self):
        reference = self.vault / "3 Reference"
        reference.mkdir()
        (reference / "Dijkstra.md").write_text("Shortest path algorithm.")
        self.refresh()

        result = vaultSearch.search_notes("Dijkstra", db_path=self.db_path)

        self.assertEqual(result["kind"], "concept")
        self.assertEqual(result["path"], str(Path("3 Reference") / "Dijkstra.md"))
        self.assertEqual(result["content"], "Shortest path algorithm.")

    def test_hit_is_case_insensitive_on_filename(self):
        reference = self.vault / "3 Reference"
        reference.mkdir()
        (reference / "Dijkstra.md").write_text("Shortest path algorithm.")
        self.refresh()

        result = vaultSearch.search_notes("dijkstra", db_path=self.db_path)

        self.assertIsNotNone(result)

    def test_miss_when_no_matching_note_or_row_exists(self):
        self.refresh()

        result = vaultSearch.search_notes("Nonexistent", db_path=self.db_path)

        self.assertIsNone(result)

    def test_reference_match_ignores_numeric_prefix(self):
        # "Reference" without its usual "3 " prefix should still match, same
        # as vaultIndex's own folder-name convention.
        reference = self.vault / "Reference"
        reference.mkdir()
        (reference / "Dijkstra.md").write_text("Shortest path algorithm.")
        self.refresh()

        result = vaultSearch.search_notes("Dijkstra", db_path=self.db_path)

        self.assertIsNotNone(result)

    def test_hit_on_a_concept_note_whose_title_starts_with_a_digit(self):
        # The leading-digit stripping is a folder-name convention (Obsidian's
        # numbered top-level folders) - a note *title* that happens to start
        # with a digit, like "5 Minute Rule", must be compared as-is.
        reference = self.vault / "3 Reference"
        reference.mkdir()
        (reference / "5 Minute Rule.md").write_text("Read for five minutes daily.")
        self.refresh()

        result = vaultSearch.search_notes("5 Minute Rule", db_path=self.db_path)

        self.assertIsNotNone(result)

    def test_does_not_match_a_similarly_named_file_in_the_wrong_folder(self):
        other = self.vault / "1 Project"
        other.mkdir()
        (other / "Dijkstra.md").write_text("Not the reference note.")
        self.refresh()

        result = vaultSearch.search_notes("Dijkstra", db_path=self.db_path)

        self.assertIsNone(result)

    def test_hit_on_korean_vocab_row(self):
        korean = self.vault / "2 Areas" / "Korean"
        korean.mkdir(parents=True)
        (korean / "Vocab.md").write_text("| 안녕 | hello |\n| 감사 | thanks |\n", encoding="utf-8")
        self.refresh()

        result = vaultSearch.search_notes("안녕", db_path=self.db_path)

        self.assertEqual(result["kind"], "vocab")
        self.assertEqual(result["path"], str(Path("2 Areas") / "Korean" / "Vocab.md"))

    def test_vocab_miss_when_word_not_present_in_file(self):
        korean = self.vault / "2 Areas" / "Korean"
        korean.mkdir(parents=True)
        (korean / "Vocab.md").write_text("| 안녕 | hello |\n", encoding="utf-8")
        self.refresh()

        result = vaultSearch.search_notes("감사", db_path=self.db_path)

        self.assertIsNone(result)

    def test_reference_note_is_checked_before_vocab_row(self):
        reference = self.vault / "3 Reference"
        reference.mkdir()
        (reference / "Term.md").write_text("Reference explanation.")
        korean = self.vault / "2 Areas" / "Korean"
        korean.mkdir(parents=True)
        (korean / "Vocab.md").write_text("Term shows up here too.")
        self.refresh()

        result = vaultSearch.search_notes("Term", db_path=self.db_path)

        self.assertEqual(result["kind"], "concept")


class WriteConfirmedTests(unittest.TestCase):
    def setUp(self):
        self.vault_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.vault_dir.cleanup)
        self.vault = Path(self.vault_dir.name)

    def test_write_concept_note_creates_file_under_reference_folder(self):
        (self.vault / "3 Reference").mkdir()

        path = vaultSearch.write_concept_note("Dijkstra", "Shortest path algorithm.", vault_path=self.vault)

        self.assertEqual(path, self.vault / "3 Reference" / "Dijkstra.md")
        self.assertEqual(path.read_text(encoding="utf-8"), "Shortest path algorithm.")

    def test_write_concept_note_matches_reference_folder_ignoring_numeric_prefix(self):
        (self.vault / "Reference").mkdir()

        path = vaultSearch.write_concept_note("Dijkstra", "Explanation.", vault_path=self.vault)

        self.assertEqual(path, self.vault / "Reference" / "Dijkstra.md")

    def test_write_concept_note_raises_when_reference_folder_is_missing(self):
        with self.assertRaises(FileNotFoundError):
            vaultSearch.write_concept_note("Dijkstra", "Explanation.", vault_path=self.vault)

    def test_write_concept_note_rejects_a_query_containing_a_path_separator(self):
        # A concept like "async/await" is a plausible query, not an attack -
        # but pathlib treats "/" (and "\\") as a separator on Windows too, so
        # letting it through would write outside "3 Reference/" entirely.
        (self.vault / "3 Reference").mkdir()

        with self.assertRaises(ValueError):
            vaultSearch.write_concept_note("async/await", "Explanation.", vault_path=self.vault)

    def test_append_vocab_row_appends_to_existing_file(self):
        korean = self.vault / "2 Areas" / "Korean"
        korean.mkdir(parents=True)
        (korean / "Vocab.md").write_text("| 안녕 | hello |\n", encoding="utf-8")

        path = vaultSearch.append_vocab_row("감사", "thanks", vault_path=self.vault)

        self.assertEqual(path, korean / "Vocab.md")
        self.assertEqual(path.read_text(encoding="utf-8"), "| 안녕 | hello |\n| 감사 | thanks |\n")

    def test_append_vocab_row_matches_areas_folder_ignoring_numeric_prefix(self):
        korean = self.vault / "Areas" / "Korean"
        korean.mkdir(parents=True)

        path = vaultSearch.append_vocab_row("안녕", "hello", vault_path=self.vault)

        self.assertEqual(path, korean / "Vocab.md")

    def test_append_vocab_row_raises_when_areas_folder_is_missing(self):
        with self.assertRaises(FileNotFoundError):
            vaultSearch.append_vocab_row("안녕", "hello", vault_path=self.vault)

    def test_append_vocab_row_escapes_a_pipe_in_the_translation(self):
        korean = self.vault / "2 Areas" / "Korean"
        korean.mkdir(parents=True)
        (korean / "Vocab.md").write_text("", encoding="utf-8")

        path = vaultSearch.append_vocab_row("or", "either|or", vault_path=self.vault)

        self.assertEqual(path.read_text(encoding="utf-8"), "| or | either\\|or |\n")

    def test_append_vocab_row_strips_newlines_from_a_multiline_translation(self):
        korean = self.vault / "2 Areas" / "Korean"
        korean.mkdir(parents=True)
        (korean / "Vocab.md").write_text("", encoding="utf-8")

        path = vaultSearch.append_vocab_row("word", "line one\nline two", vault_path=self.vault)

        self.assertEqual(path.read_text(encoding="utf-8"), "| word | line one line two |\n")


class InboxTriageTests(unittest.TestCase):
    def setUp(self):
        self.vault_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.vault_dir.cleanup)
        self.vault = Path(self.vault_dir.name)

    def test_list_inbox_entries_finds_notes_in_numbered_inbox_folder(self):
        inbox = self.vault / "0 Inbox"
        inbox.mkdir()
        (inbox / "Stray thought.md").write_text("content")

        entries = vaultSearch.list_inbox_entries(vault_path=self.vault)

        self.assertEqual(entries, [inbox / "Stray thought.md"])

    def test_list_inbox_entries_matches_inbox_folder_ignoring_numeric_prefix(self):
        inbox = self.vault / "Inbox"
        inbox.mkdir()
        (inbox / "Stray thought.md").write_text("content")

        entries = vaultSearch.list_inbox_entries(vault_path=self.vault)

        self.assertEqual(entries, [inbox / "Stray thought.md"])

    def test_list_inbox_entries_is_sorted_by_name(self):
        inbox = self.vault / "0 Inbox"
        inbox.mkdir()
        (inbox / "Zebra.md").write_text("content")
        (inbox / "Apple.md").write_text("content")

        entries = vaultSearch.list_inbox_entries(vault_path=self.vault)

        self.assertEqual(entries, [inbox / "Apple.md", inbox / "Zebra.md"])

    def test_list_inbox_entries_ignores_non_markdown_files(self):
        inbox = self.vault / "0 Inbox"
        inbox.mkdir()
        (inbox / "Note.md").write_text("content")
        (inbox / "image.png").write_bytes(b"\x89PNG")

        entries = vaultSearch.list_inbox_entries(vault_path=self.vault)

        self.assertEqual(entries, [inbox / "Note.md"])

    def test_list_inbox_entries_raises_when_inbox_folder_is_missing(self):
        with self.assertRaises(FileNotFoundError):
            vaultSearch.list_inbox_entries(vault_path=self.vault)

    def test_parse_triage_response_matches_project(self):
        self.assertEqual(vaultSearch.parse_triage_response("Project"), "Project")

    def test_parse_triage_response_matches_areas(self):
        self.assertEqual(vaultSearch.parse_triage_response("Areas"), "Areas")

    def test_parse_triage_response_matches_reference(self):
        self.assertEqual(vaultSearch.parse_triage_response("Reference"), "Reference")

    def test_parse_triage_response_is_case_insensitive_and_tolerates_extra_text(self):
        self.assertEqual(vaultSearch.parse_triage_response("This belongs in reference.\n"), "Reference")

    def test_parse_triage_response_returns_none_when_nothing_matches(self):
        self.assertIsNone(vaultSearch.parse_triage_response("I'm not sure."))

    def test_parse_triage_response_returns_none_on_an_ambiguous_reply_naming_two_folders(self):
        # A fixed first-match-wins scan would silently invert the model's
        # actual recommendation here ("not Project, it's Areas") - ambiguity
        # must surface as a miss, not a guess.
        self.assertIsNone(vaultSearch.parse_triage_response("This isn't really a Project - it belongs in Areas."))

    def test_move_inbox_entry_moves_file_into_target_folder(self):
        inbox = self.vault / "0 Inbox"
        inbox.mkdir()
        entry = inbox / "Stray thought.md"
        entry.write_text("content")
        (self.vault / "3 Reference").mkdir()

        destination = vaultSearch.move_inbox_entry(entry, "Reference", vault_path=self.vault)

        self.assertEqual(destination, self.vault / "3 Reference" / "Stray thought.md")
        self.assertTrue(destination.exists())
        self.assertFalse(entry.exists())
        self.assertEqual(destination.read_text(encoding="utf-8"), "content")

    def test_move_inbox_entry_matches_target_folder_ignoring_numeric_prefix(self):
        inbox = self.vault / "0 Inbox"
        inbox.mkdir()
        entry = inbox / "Stray thought.md"
        entry.write_text("content")
        (self.vault / "Areas").mkdir()

        destination = vaultSearch.move_inbox_entry(entry, "Areas", vault_path=self.vault)

        self.assertEqual(destination, self.vault / "Areas" / "Stray thought.md")

    def test_move_inbox_entry_rejects_a_folder_outside_the_triage_choices(self):
        inbox = self.vault / "0 Inbox"
        inbox.mkdir()
        entry = inbox / "Stray thought.md"
        entry.write_text("content")

        with self.assertRaises(ValueError):
            vaultSearch.move_inbox_entry(entry, "Inbox", vault_path=self.vault)

    def test_move_inbox_entry_raises_when_target_folder_is_missing(self):
        inbox = self.vault / "0 Inbox"
        inbox.mkdir()
        entry = inbox / "Stray thought.md"
        entry.write_text("content")

        with self.assertRaises(FileNotFoundError):
            vaultSearch.move_inbox_entry(entry, "Project", vault_path=self.vault)

    def test_move_inbox_entry_refuses_to_overwrite_an_existing_file_at_the_destination(self):
        inbox = self.vault / "0 Inbox"
        inbox.mkdir()
        entry = inbox / "Untitled.md"
        entry.write_text("new content")
        reference = self.vault / "3 Reference"
        reference.mkdir()
        (reference / "Untitled.md").write_text("existing content - must not be clobbered")

        with self.assertRaises(FileExistsError):
            vaultSearch.move_inbox_entry(entry, "Reference", vault_path=self.vault)

        self.assertEqual((reference / "Untitled.md").read_text(), "existing content - must not be clobbered")
        self.assertTrue(entry.exists())


class FakeSignal:
    """Stands in for a Qt Signal without needing a real QObject/QThread -
    connect() records the slot, emit() calls it straight away. Keeps
    ExplainQueryTests from ever spawning the real `claude` CLI subprocess
    that the real ClaudeRequest would start."""

    def __init__(self):
        self.slot = None

    def connect(self, slot):
        self.slot = slot

    def emit(self, *args):
        if self.slot is not None:
            self.slot(*args)


class FakeClaudeRequest:
    def __init__(self, prompt):
        self.prompt = prompt
        self.chunk = FakeSignal()
        self.finished = FakeSignal()
        self.started = False
        self.cancelled = False

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True


class ExplainQueryTests(unittest.TestCase):
    def setUp(self):
        self.vault_dir = tempfile.TemporaryDirectory()
        self.db_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.vault_dir.cleanup)
        self.addCleanup(self.db_dir.cleanup)
        self.vault = Path(self.vault_dir.name)
        self.db_path = Path(self.db_dir.name) / "vault-index.sqlite3"
        self.results = []

    def start(self, query):
        explain = vaultSearch.ExplainQuery(
            query,
            lambda result: self.results.append(result),
            db_path=self.db_path,
            request_factory=FakeClaudeRequest,
        )
        explain.start()
        return explain

    def test_hit_reports_the_existing_note_without_starting_a_request(self):
        reference = self.vault / "3 Reference"
        reference.mkdir()
        (reference / "Dijkstra.md").write_text("Shortest path algorithm.")
        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)

        explain = self.start("Dijkstra")

        self.assertEqual(self.results, [{
            "hit": True,
            "kind": "concept",
            "path": str(Path("3 Reference") / "Dijkstra.md"),
            "content": "Shortest path algorithm.",
        }])
        self.assertIsNone(explain.request)

    def test_miss_starts_a_request_for_the_draft(self):
        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)

        explain = self.start("Nonexistent")

        self.assertEqual(self.results, [])
        self.assertIsInstance(explain.request, FakeClaudeRequest)
        self.assertTrue(explain.request.started)
        self.assertIn("Nonexistent", explain.request.prompt)

    def test_on_finished_reports_the_miss_case_draft(self):
        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)
        explain = self.start("Nonexistent")

        explain.request.chunk.emit("A drafted ")
        explain.request.chunk.emit("explanation.")
        explain.request.finished.emit()

        self.assertEqual(self.results, [{"hit": False, "draft": "A drafted explanation."}])

    def test_cancel_before_a_request_starts_is_a_no_op(self):
        explain = vaultSearch.ExplainQuery(
            "unused", lambda result: None, db_path=self.db_path, request_factory=FakeClaudeRequest
        )
        explain.cancel()  # must not raise even though start() was never called

    def test_finished_after_cancel_does_not_report_a_stale_draft(self):
        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)
        explain = self.start("Nonexistent")

        explain.cancel()
        explain.request.chunk.emit("partial draft")
        explain.request.finished.emit()

        self.assertEqual(self.results, [])


class TriageQueryTests(unittest.TestCase):
    def setUp(self):
        self.vault_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.vault_dir.cleanup)
        self.vault = Path(self.vault_dir.name)
        self.inbox = self.vault / "0 Inbox"
        self.inbox.mkdir()
        self.entry = self.inbox / "Stray thought.md"
        self.entry.write_text("Some note about an ongoing side project.")
        self.results = []

    def start(self):
        triage = vaultSearch.TriageQuery(
            self.entry,
            lambda result: self.results.append(result),
            request_factory=FakeClaudeRequest,
        )
        triage.start()
        return triage

    def test_start_sends_the_note_content_to_claude(self):
        triage = self.start()

        self.assertIsInstance(triage.request, FakeClaudeRequest)
        self.assertTrue(triage.request.started)
        self.assertIn("Some note about an ongoing side project.", triage.request.prompt)

    def test_on_finished_reports_the_proposed_folder(self):
        triage = self.start()

        triage.request.chunk.emit("Project")
        triage.request.finished.emit()

        self.assertEqual(self.results, [{"path": self.entry, "folder": "Project"}])

    def test_on_finished_reports_none_folder_when_reply_is_unrecognized(self):
        triage = self.start()

        triage.request.chunk.emit("not sure")
        triage.request.finished.emit()

        self.assertEqual(self.results, [{"path": self.entry, "folder": None}])

    def test_finished_after_cancel_does_not_report_a_stale_proposal(self):
        triage = self.start()

        triage.cancel()
        triage.request.chunk.emit("Project")
        triage.request.finished.emit()

        self.assertEqual(self.results, [])

    def test_start_reports_none_folder_without_starting_a_request_when_file_is_unreadable(self):
        # Mirrors vaultIndex.refresh()'s own tolerance for a file that
        # disappears or turns unreadable between being listed and being
        # acted on - an unlucky delete/rename in the window between
        # list_inbox_entries() and the user picking this entry.
        self.entry.unlink()

        triage = self.start()

        self.assertEqual(self.results, [{"path": self.entry, "folder": None}])
        self.assertIsNone(triage.request)


if __name__ == "__main__":
    unittest.main()
