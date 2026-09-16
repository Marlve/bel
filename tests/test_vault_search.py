import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

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
        self.assertEqual(result["row"], ["안녕", "hello"])

    def test_vocab_miss_when_word_not_present_in_file(self):
        korean = self.vault / "2 Areas" / "Korean"
        korean.mkdir(parents=True)
        (korean / "Vocab.md").write_text("| 안녕 | hello |\n", encoding="utf-8")
        self.refresh()

        result = vaultSearch.search_notes("감사", db_path=self.db_path)

        self.assertIsNone(result)

    def test_vocab_miss_when_query_is_only_a_fragment_of_a_cell(self):
        korean = self.vault / "2 Areas" / "Korean"
        korean.mkdir(parents=True)
        (korean / "Vocab.md").write_text("| 그리고 | and, additionally |\n", encoding="utf-8")
        self.refresh()

        result = vaultSearch.search_notes("an", db_path=self.db_path)

        self.assertIsNone(result)

    def test_vocab_hit_matches_a_whole_cell_case_insensitively(self):
        korean = self.vault / "2 Areas" / "Korean"
        korean.mkdir(parents=True)
        (korean / "Vocab.md").write_text("| 안녕 | Hello |\n", encoding="utf-8")
        self.refresh()

        result = vaultSearch.search_notes("hello", db_path=self.db_path)

        self.assertEqual(result["kind"], "vocab")

    def test_vocab_miss_on_header_separator_heading_and_empty_query(self):
        korean = self.vault / "2 Areas" / "Korean"
        korean.mkdir(parents=True)
        (korean / "Vocab.md").write_text(
            "# Korean vocab\n\n| Korean | English |\n| --- | --- |\n| 안녕 | hello |\n",
            encoding="utf-8",
        )
        self.refresh()

        for query in ("English", "---", "# Korean vocab", ""):
            with self.subTest(query=query):
                self.assertIsNone(vaultSearch.search_notes(query, db_path=self.db_path))

    def test_vocab_hit_ignores_surrounding_whitespace_in_the_query(self):
        korean = self.vault / "2 Areas" / "Korean"
        korean.mkdir(parents=True)
        (korean / "Vocab.md").write_text("| 안녕 | hello |\n", encoding="utf-8")
        self.refresh()

        self.assertIsNotNone(vaultSearch.search_notes(" 안녕 ", db_path=self.db_path))

    def test_vocab_escaped_pipe_stays_inside_one_cell(self):
        # append_vocab_row escapes "|" as "\|" - the cell must still be read
        # back as one cell, not split in two.
        korean = self.vault / "2 Areas" / "Korean"
        korean.mkdir(parents=True)
        (korean / "Vocab.md").write_text("| 또는 | or \\| either |\n", encoding="utf-8")
        self.refresh()

        self.assertIsNone(vaultSearch.search_notes("either", db_path=self.db_path))
        self.assertIsNotNone(vaultSearch.search_notes("or | either", db_path=self.db_path))

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

    def test_is_valid_note_title(self):
        self.assertTrue(vaultSearch.is_valid_note_title("Dijkstra"))
        for query in ("TCP/IP", "C++ : templates", "What is X?"):
            with self.subTest(query=query):
                self.assertFalse(vaultSearch.is_valid_note_title(query))

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

    def test_write_concept_note_refuses_to_overwrite_an_existing_note(self):
        # A stale index can report a miss for a note Derich just created in
        # Obsidian - confirming the draft must not clobber the real note.
        reference = self.vault / "3 Reference"
        reference.mkdir()
        (reference / "Dijkstra.md").write_text("real note - must not be clobbered")

        with self.assertRaises(FileExistsError):
            vaultSearch.write_concept_note("Dijkstra", "Drafted explanation.", vault_path=self.vault)

        self.assertEqual((reference / "Dijkstra.md").read_text(), "real note - must not be clobbered")

    def test_write_concept_note_rejects_a_query_containing_an_illegal_filename_character(self):
        # Windows rejects these in filenames (":" instead silently writes an
        # NTFS alternate data stream) - callers expect the documented
        # ValueError for an unusable query instead.
        (self.vault / "3 Reference").mkdir()

        for query in ["What is X?", "C++ : templates", 'say "hi"', "a<b", "a>b", "a|b", "a*b", "a\\b", "a\tb", "a\nb"]:
            with self.subTest(query=query):
                with self.assertRaises(ValueError):
                    vaultSearch.write_concept_note(query, "Explanation.", vault_path=self.vault)

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


class LookupQueryTests(unittest.TestCase):
    def test_question_mark_prefix_marks_a_lookup(self):
        self.assertEqual(vaultSearch.lookup_query("? Dijkstra"), "Dijkstra")

    def test_prefix_without_a_space_still_counts(self):
        self.assertEqual(vaultSearch.lookup_query("?Dijkstra"), "Dijkstra")

    def test_message_without_the_prefix_is_normal_chat(self):
        self.assertIsNone(vaultSearch.lookup_query("what is Dijkstra?"))

    def test_a_bare_prefix_is_not_a_lookup(self):
        # An empty query would otherwise draft and write "3 Reference/.md".
        for text in ("?", "?   "):
            with self.subTest(text=text):
                self.assertIsNone(vaultSearch.lookup_query(text))


class RecentNotesTests(unittest.TestCase):
    def setUp(self):
        self.vault_dir = tempfile.TemporaryDirectory()
        self.db_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.vault_dir.cleanup)
        self.addCleanup(self.db_dir.cleanup)
        self.vault = Path(self.vault_dir.name)
        self.db_path = Path(self.db_dir.name) / "vault-index.sqlite3"

    def note(self, relative, mtime):
        path = self.vault / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("content", encoding="utf-8")
        os.utime(path, (mtime, mtime))

    def test_lists_notes_most_recently_edited_first(self):
        now = 1_000_000
        self.note(Path("1 Project") / "Old.md", now - 3 * 86400)
        self.note(Path("1 Project") / "New.md", now - 60)
        self.note(Path("2 Areas") / "Middle.md", now - 2 * 86400)
        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)

        notes = vaultSearch.recent_notes(db_path=self.db_path, now=now)

        self.assertEqual([note["path"] for note in notes], [
            str(Path("1 Project") / "New.md"),
            str(Path("2 Areas") / "Middle.md"),
            str(Path("1 Project") / "Old.md"),
        ])

    def test_marks_notes_edited_in_the_last_day_as_recent(self):
        now = 1_000_000
        self.note(Path("1 Project") / "Today.md", now - 3600)
        self.note(Path("1 Project") / "Older.md", now - 2 * 86400)
        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)

        notes = vaultSearch.recent_notes(db_path=self.db_path, now=now)

        self.assertEqual([note["recent"] for note in notes], [True, False])

    def test_never_lists_a_private_note(self):
        now = 1_000_000
        self.note(Path("6 Private") / "Secret.md", now - 60)
        self.note(Path("1 Project") / "Plan.md", now - 120)
        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)

        notes = vaultSearch.recent_notes(db_path=self.db_path, now=now)

        self.assertEqual([note["path"] for note in notes], [str(Path("1 Project") / "Plan.md")])

    def test_caps_the_list_length(self):
        now = 1_000_000
        for i in range(vaultSearch.RECENT_NOTES_LIMIT + 5):
            self.note(Path("1 Project") / f"Note {i}.md", now - i)
        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)

        notes = vaultSearch.recent_notes(db_path=self.db_path, now=now)

        self.assertEqual(len(notes), vaultSearch.RECENT_NOTES_LIMIT)


class LinkInsertTests(unittest.TestCase):
    def setUp(self):
        self.vault_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.vault_dir.cleanup)
        self.vault = Path(self.vault_dir.name)
        self.picked = str(Path("1 Project") / "Plan.md")

    def plan(self):
        (self.vault / "1 Project").mkdir()
        plan = self.vault / self.picked
        plan.write_text("Today I learned about pathfinding.", encoding="utf-8")
        return plan

    def test_insert_concept_link_appends_link_to_the_picked_note(self):
        plan = self.plan()

        result = vaultSearch.insert_concept_link("Dijkstra", self.picked, vault_path=self.vault)

        self.assertEqual(result, plan)
        self.assertEqual(
            plan.read_text(encoding="utf-8"),
            "Today I learned about pathfinding.\n[[Dijkstra]]\n",
        )

    def test_insert_concept_link_is_a_noop_when_the_picked_note_no_longer_exists(self):
        result = vaultSearch.insert_concept_link("Dijkstra", str(Path("1 Project") / "Gone.md"), vault_path=self.vault)

        self.assertIsNone(result)

    def test_insert_concept_link_does_not_create_a_stub_file_when_only_the_file_itself_is_missing(self):
        # Distinct from the folder-also-missing case above: append mode
        # would otherwise happily fabricate a new file here, since the
        # parent folder still exists.
        (self.vault / "1 Project").mkdir()

        result = vaultSearch.insert_concept_link("Dijkstra", str(Path("1 Project") / "Renamed.md"), vault_path=self.vault)

        self.assertIsNone(result)
        self.assertFalse((self.vault / "1 Project" / "Renamed.md").exists())

    def test_insert_concept_link_refuses_a_note_inside_private(self):
        private = self.vault / "6 Private"
        private.mkdir()
        secret = private / "Secret.md"
        secret.write_text("Private.", encoding="utf-8")

        for note in (
            str(Path("6 Private") / "Secret.md"),
            str(Path("6 PRIVATE") / "Secret.md"),
            str(Path("1 Project") / ".." / "6 Private" / "Secret.md"),
            str(Path("6 Private.") / "Secret.md"),
            str(secret),
        ):
            with self.subTest(note=note):
                result = vaultSearch.insert_concept_link("Dijkstra", note, vault_path=self.vault)

                self.assertIsNone(result)
                self.assertEqual(secret.read_text(encoding="utf-8"), "Private.")

    def test_insert_concept_link_refuses_a_private_note_without_touching_the_filesystem(self):
        # Even resolve() opens a handle to its target on Windows - the
        # refusal has to be decided from the path string alone.
        untouchable = AssertionError("touched the filesystem for a Private path")

        with patch.object(Path, "resolve", side_effect=untouchable), \
                patch.object(Path, "is_file", side_effect=untouchable), \
                patch.object(Path, "stat", side_effect=untouchable), \
                patch.object(Path, "open", side_effect=untouchable):
            result = vaultSearch.insert_concept_link("Dijkstra", str(Path("6 Private") / "Secret.md"), vault_path=self.vault)

        self.assertIsNone(result)

    def test_insert_concept_link_refuses_a_note_outside_the_vault(self):
        outside_dir = tempfile.TemporaryDirectory()
        self.addCleanup(outside_dir.cleanup)
        outside = Path(outside_dir.name) / "Elsewhere.md"
        outside.write_text("Not in the vault.", encoding="utf-8")

        result = vaultSearch.insert_concept_link("Dijkstra", str(outside), vault_path=self.vault)

        self.assertIsNone(result)
        self.assertEqual(outside.read_text(encoding="utf-8"), "Not in the vault.")


class ConfirmPickTests(unittest.TestCase):
    """Clicking a note in card.md's picker - the only thing that writes to
    the vault in the explain flow."""

    def setUp(self):
        self.vault_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.vault_dir.cleanup)
        self.vault = Path(self.vault_dir.name)
        self.reference = self.vault / "3 Reference"
        self.reference.mkdir()
        (self.vault / "1 Project").mkdir()
        self.picked = str(Path("1 Project") / "Plan.md")
        self.plan = self.vault / self.picked
        self.plan.write_text("Notes.", encoding="utf-8")

    def test_a_hit_links_the_existing_notes_real_filename(self):
        # search_notes matches case-insensitively, so the link uses the
        # note's on-disk title, not whatever casing was typed.
        (self.reference / "Dijkstra.md").write_text("Shortest path algorithm.", encoding="utf-8")
        hit = {"hit": True, "kind": "concept", "path": str(Path("3 Reference") / "Dijkstra.md"), "content": "Shortest path algorithm."}

        vaultSearch.confirm_pick("dijkstra", hit, self.picked, vault_path=self.vault)

        self.assertEqual(self.plan.read_text(encoding="utf-8"), "Notes.\n[[Dijkstra]]\n")
        self.assertEqual(sorted(p.name for p in self.reference.iterdir()), ["Dijkstra.md"])

    def test_a_miss_writes_the_draft_then_links_it(self):
        miss = {"hit": False, "draft": "Shortest path algorithm."}

        vaultSearch.confirm_pick("Dijkstra", miss, self.picked, vault_path=self.vault)

        self.assertEqual((self.reference / "Dijkstra.md").read_text(encoding="utf-8"), "Shortest path algorithm.")
        self.assertEqual(self.plan.read_text(encoding="utf-8"), "Notes.\n[[Dijkstra]]\n")

    def test_a_miss_that_would_overwrite_a_note_links_nothing(self):
        # A stale index can miss a note Derich just created in Obsidian.
        (self.reference / "Dijkstra.md").write_text("real note", encoding="utf-8")
        miss = {"hit": False, "draft": "Drafted explanation."}

        with self.assertRaises(FileExistsError):
            vaultSearch.confirm_pick("Dijkstra", miss, self.picked, vault_path=self.vault)

        self.assertEqual((self.reference / "Dijkstra.md").read_text(encoding="utf-8"), "real note")
        self.assertEqual(self.plan.read_text(encoding="utf-8"), "Notes.")


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


class TrackingSignal:
    """Stands in for QApplication.aboutToQuit - unlike FakeSignal, tracks
    every connected slot rather than just the latest one, so a test can
    assert the connection count doesn't grow across repeated ExplainQuery
    instantiations (issue 06)."""

    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def disconnect(self, slot):
        self.slots.remove(slot)


class FakeApp:
    def __init__(self):
        self.aboutToQuit = TrackingSignal()


class FakeClaudeRequest:
    def __init__(self, prompt):
        self.prompt = prompt
        self.chunk = FakeSignal()
        self.finished = FakeSignal()
        self.started = False
        self.cancelled = False
        self.failed = False

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True


class FakeSearchRequest:
    """Stands in for SearchRequest (issue 08) - no real QThread, so
    hit-path tests stay synchronous and controllable, mirroring
    FakeClaudeRequest's role for the miss path. start() still runs the
    real (cheap, local) lookup and stashes it on self.outcome; only the
    Signal is faked, so a test must explicitly emit finished to resolve
    it, same as FakeClaudeRequest's explicit-emit shape."""

    def __init__(self, query, vault_path=None, db_path=None):
        self.query = query
        self.vault_path = vault_path
        self.db_path = db_path
        self.finished = FakeSignal()
        self.started = False
        self.cancelled = False
        self.outcome = None

    def start(self):
        self.started = True
        self.outcome = vaultSearch.lookup(self.query, vault_path=self.vault_path, db_path=self.db_path)

    def cancel(self):
        self.cancelled = True


class LookupTests(unittest.TestCase):
    def setUp(self):
        self.vault_dir = tempfile.TemporaryDirectory()
        self.db_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.vault_dir.cleanup)
        self.addCleanup(self.db_dir.cleanup)
        self.vault = Path(self.vault_dir.name)
        self.db_path = Path(self.db_dir.name) / "vault-index.sqlite3"

    def test_refreshes_the_index_before_searching(self):
        # Nothing else in the app refreshes the index, so a note created
        # since the last lookup must still be found.
        reference = self.vault / "3 Reference"
        reference.mkdir()
        (reference / "Dijkstra.md").write_text("Shortest path algorithm.")

        outcome = vaultSearch.lookup("Dijkstra", vault_path=self.vault, db_path=self.db_path)

        self.assertEqual(outcome["found"]["path"], str(Path("3 Reference") / "Dijkstra.md"))
        self.assertEqual([note["path"] for note in outcome["notes"]], [str(Path("3 Reference") / "Dijkstra.md")])


class SearchWorkerTests(unittest.TestCase):
    def test_run_still_emits_finished_as_a_miss_when_the_lookup_raises(self):
        # Otherwise nothing downstream ever resolves - the query hangs and
        # ExplainQuery never disconnects from aboutToQuit (issue 18). No
        # notes either, so there's nothing to pick and nothing gets written.
        worker = vaultSearch.SearchWorker("Dijkstra")
        outcomes = []
        worker.finished.connect(outcomes.append)

        with patch.object(vaultSearch, "lookup", side_effect=sqlite3.OperationalError("database is locked")):
            worker.run()

        self.assertEqual(outcomes, [{"found": None, "notes": []}])


class ExplainQueryTests(unittest.TestCase):
    def setUp(self):
        self.vault_dir = tempfile.TemporaryDirectory()
        self.db_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.vault_dir.cleanup)
        self.addCleanup(self.db_dir.cleanup)
        self.vault = Path(self.vault_dir.name)
        self.db_path = Path(self.db_dir.name) / "vault-index.sqlite3"
        self.results = []

    def explain(self, query):
        return vaultSearch.ExplainQuery(
            query,
            lambda result: self.results.append(result),
            vault_path=self.vault,
            db_path=self.db_path,
            request_factory=FakeClaudeRequest,
            search_request_factory=FakeSearchRequest,
        )

    def start(self, query):
        explain = self.explain(query)
        explain.start()
        # The hit-path lookup is threaded too now (issue 08) - resolve it
        # synchronously here so every test below can keep treating a
        # hit/miss outcome as available right after start().
        explain.search_request.finished.emit(explain.search_request.outcome)
        return explain

    def dijkstra_note(self):
        reference = self.vault / "3 Reference"
        reference.mkdir()
        (reference / "Dijkstra.md").write_text("Shortest path algorithm.")

    def test_hit_reports_the_existing_note_and_candidates_without_starting_a_request(self):
        self.dijkstra_note()

        explain = self.start("Dijkstra")

        path = str(Path("3 Reference") / "Dijkstra.md")
        self.assertEqual(len(self.results), 1)
        result = self.results[0]
        self.assertEqual(
            {key: result[key] for key in ("hit", "kind", "path", "content")},
            {"hit": True, "kind": "concept", "path": path, "content": "Shortest path algorithm."},
        )
        self.assertEqual(result["notes"], [])  # the only indexed note is the hit itself
        self.assertIsNone(explain.request)

    def test_hit_does_not_write_anything_before_a_pick(self):
        self.dijkstra_note()
        (self.vault / "1 Project").mkdir()
        plan = self.vault / "1 Project" / "Plan.md"
        plan.write_text("Notes.", encoding="utf-8")

        self.start("Dijkstra")

        self.assertEqual(plan.read_text(encoding="utf-8"), "Notes.")

    def test_miss_starts_a_request_for_the_draft(self):
        explain = self.start("Nonexistent")

        self.assertEqual(self.results, [])
        self.assertIsInstance(explain.request, FakeClaudeRequest)
        self.assertTrue(explain.request.started)
        self.assertIn("Nonexistent", explain.request.prompt)

    def test_on_finished_reports_the_miss_case_draft_and_candidates(self):
        (self.vault / "1 Project").mkdir()
        (self.vault / "1 Project" / "Plan.md").write_text("Notes.", encoding="utf-8")
        explain = self.start("Nonexistent")

        explain.request.chunk.emit("A drafted ")
        explain.request.chunk.emit("explanation.")
        explain.request.finished.emit()

        self.assertEqual(self.results, [{
            "hit": False,
            "kind": "concept",
            "draft": "A drafted explanation.",
            "notes": [{"path": str(Path("1 Project") / "Plan.md"), "recent": True}],
        }])

    def test_a_failed_draft_is_reported_as_no_draft(self):
        # An error or a timed-out, cut-off answer must never be offered for
        # saving - the card shows no picker for an empty draft.
        explain = self.start("Nonexistent")

        explain.request.chunk.emit("[error: claude exited]")
        explain.request.failed = True
        explain.request.finished.emit()

        self.assertEqual(self.results[0]["draft"], "")

    def test_a_hit_does_not_offer_the_matched_note_as_a_place_to_link_itself(self):
        self.dijkstra_note()
        (self.vault / "1 Project").mkdir()
        (self.vault / "1 Project" / "Plan.md").write_text("Notes.", encoding="utf-8")

        self.start("Dijkstra")

        self.assertEqual([note["path"] for note in self.results[0]["notes"]], [str(Path("1 Project") / "Plan.md")])

    def test_a_korean_miss_starts_a_request_and_reports_its_draft_as_kind_vocab(self):
        # Issue 22: Claude answers what the word means, but as kind "vocab" -
        # never a concept draft that could be saved as "3 Reference/<word>.md".
        explain = self.start("감사")

        self.assertIsInstance(explain.request, FakeClaudeRequest)
        self.assertTrue(explain.request.started)
        self.assertIn("감사", explain.request.prompt)
        explain.request.chunk.emit("Thanks.")
        explain.request.finished.emit()

        self.assertEqual(self.results, [{"hit": False, "kind": "vocab", "draft": "Thanks.", "notes": []}])

    def test_a_failed_korean_answer_is_reported_as_no_draft(self):
        explain = self.start("감사")

        explain.request.chunk.emit("[error: claude exited]")
        explain.request.failed = True
        explain.request.finished.emit()

        self.assertEqual((self.results[0]["kind"], self.results[0]["draft"]), ("vocab", ""))

    def test_cancel_before_a_request_starts_is_a_no_op(self):
        explain = vaultSearch.ExplainQuery(
            "unused", lambda result: None, db_path=self.db_path, request_factory=FakeClaudeRequest
        )
        explain.cancel()  # must not raise even though start() was never called

    def test_cancel_reaches_both_the_search_and_the_claude_request(self):
        # Otherwise quitting mid-draft would leave the `claude` subprocess
        # running - ExplainQuery.cancel must still call ClaudeQuery.cancel.
        explain = self.start("Nonexistent")

        explain.cancel()

        self.assertTrue(explain.search_request.cancelled)
        self.assertTrue(explain.request.cancelled)

    def test_finished_after_cancel_does_not_report_a_stale_draft(self):
        explain = self.start("Nonexistent")

        explain.cancel()
        explain.request.chunk.emit("partial draft")
        explain.request.finished.emit()

        self.assertEqual(self.results, [])

    def test_hit_after_cancel_does_not_report_a_stale_hit(self):
        # Only possible now that the hit-path lookup is threaded (issue
        # 08) - before, search_notes() resolved synchronously inside
        # start(), so cancel() could never race it.
        self.dijkstra_note()
        explain = self.explain("Dijkstra")
        explain.start()

        explain.cancel()
        explain.search_request.finished.emit(explain.search_request.outcome)

        self.assertEqual(self.results, [])

    def test_a_cancel_during_search_still_disconnects_from_aboutToQuit(self):
        # Regression: onSearchFinished's cancelled guard must disconnect
        # before returning, same as onFinished's - otherwise a query
        # cancelled while its search is still in flight leaks its
        # aboutToQuit connection forever (issue 06, reintroduced by 08).
        self.dijkstra_note()
        fake_app = FakeApp()

        with patch.object(QApplication, "instance", return_value=fake_app):
            explain = self.explain("Dijkstra")
            explain.start()
            explain.cancel()
            explain.search_request.finished.emit(explain.search_request.outcome)

        self.assertEqual(fake_app.aboutToQuit.slots, [])

    def test_a_hit_disconnects_from_aboutToQuit_without_waiting_for_a_request(self):
        self.dijkstra_note()
        fake_app = FakeApp()

        with patch.object(QApplication, "instance", return_value=fake_app):
            self.start("Dijkstra")

        self.assertEqual(fake_app.aboutToQuit.slots, [])

    def test_a_korean_miss_disconnects_from_aboutToQuit(self):
        fake_app = FakeApp()

        with patch.object(QApplication, "instance", return_value=fake_app):
            explain = self.start("감사")
            explain.request.finished.emit()

        self.assertEqual(fake_app.aboutToQuit.slots, [])

    def test_repeated_instantiation_does_not_grow_the_aboutToQuit_connection_count(self):
        fake_app = FakeApp()

        with patch.object(QApplication, "instance", return_value=fake_app):
            for _ in range(3):
                explain = self.start("Nonexistent")
                explain.request.finished.emit()

        self.assertEqual(fake_app.aboutToQuit.slots, [])


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

    def test_an_unreadable_file_disconnects_from_aboutToQuit_without_waiting_for_a_request(self):
        self.entry.unlink()
        fake_app = FakeApp()

        with patch.object(QApplication, "instance", return_value=fake_app):
            self.start()

        self.assertEqual(fake_app.aboutToQuit.slots, [])

    def test_repeated_instantiation_does_not_grow_the_aboutToQuit_connection_count(self):
        fake_app = FakeApp()

        with patch.object(QApplication, "instance", return_value=fake_app):
            for _ in range(3):
                triage = self.start()
                triage.request.finished.emit()

        self.assertEqual(fake_app.aboutToQuit.slots, [])


if __name__ == "__main__":
    unittest.main()
