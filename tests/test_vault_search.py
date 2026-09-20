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


class SearchQueryTermsTests(unittest.TestCase):
    def test_each_word_becomes_its_own_quoted_phrase(self):
        self.assertEqual(vaultSearch.search_query_terms("shortest path"), '"shortest" AND "path"')

    def test_an_apostrophe_splits_instead_of_reaching_fts(self):
        # Raw "Dijkstra's" is an FTS5 syntax error - the whole point of the
        # recipe is that no user punctuation survives into the expression.
        self.assertEqual(vaultSearch.search_query_terms("Dijkstra's"), '"Dijkstra" AND "s"')

    def test_fts_operators_typed_by_a_human_are_just_words(self):
        self.assertEqual(vaultSearch.search_query_terms("NOT a tree"), '"NOT" AND "a" AND "tree"')
        self.assertEqual(vaultSearch.search_query_terms("graph OR queue"), '"graph" AND "OR" AND "queue"')

    def test_punctuation_is_dropped_rather_than_escaped(self):
        # "+" and "?" are both FTS5 syntax errors raw. Note "c++" survives
        # only as "c" - the recipe searches words, and "++" isn't one.
        self.assertEqual(vaultSearch.search_query_terms("what is c++?"), '"what" AND "is" AND "c"')

    def test_hangul_is_a_term(self):
        self.assertEqual(vaultSearch.search_query_terms("안녕 하세요"), '"안녕" AND "하세요"')

    def test_a_query_of_pure_punctuation_has_no_terms(self):
        self.assertEqual(vaultSearch.search_query_terms("??? !!!"), "")


class SearchContentTests(unittest.TestCase):
    def setUp(self):
        self.vault_dir = tempfile.TemporaryDirectory()
        self.db_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.vault_dir.cleanup)
        self.addCleanup(self.db_dir.cleanup)
        self.vault = Path(self.vault_dir.name)
        self.db_path = Path(self.db_dir.name) / "vault-index.sqlite3"
        self.reference = self.vault / "3 Reference"
        self.reference.mkdir()

    def note(self, name, content):
        (self.reference / name).write_text(content, encoding="utf-8")

    def refresh(self):
        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)

    def paths(self, query):
        return [note["path"] for note in vaultSearch.search_content(query, db_path=self.db_path)]

    def test_finds_a_note_by_words_that_are_not_in_its_title(self):
        self.note("Dijkstra.md", "Finds the shortest path with a priority queue.")
        self.refresh()

        self.assertEqual(self.paths("shortest path"), [str(Path("3 Reference") / "Dijkstra.md")])

    def test_the_query_that_drafts_a_duplicate_today_finds_the_note(self):
        # "? Dijkstra's algorithm" misses on filename equality and files a
        # second note about Dijkstra - the reason this ticket exists.
        self.note("Dijkstra.md", "Dijkstra's algorithm finds the shortest path.")
        self.refresh()

        self.assertEqual(self.paths("Dijkstra's algorithm"), [str(Path("3 Reference") / "Dijkstra.md")])

    def test_a_candidate_carries_the_recency_dot(self):
        # Same shape as all_notes/vocab_note, so the picker's note_row can
        # draw a candidate without the card reshaping it.
        self.note("Dijkstra.md", "Finds the shortest path.")
        self.refresh()
        now = Path(self.reference / "Dijkstra.md").stat().st_mtime

        fresh = vaultSearch.search_content("shortest path", db_path=self.db_path, now=now)
        stale = vaultSearch.search_content("shortest path", db_path=self.db_path, now=now + vaultSearch.RECENT_SECONDS + 1)

        self.assertEqual([note["recent"] for note in fresh], [True])
        self.assertEqual([note["recent"] for note in stale], [False])

    def test_a_question_typed_as_a_human_types_it_never_raises(self):
        self.note("Dijkstra.md", "Dijkstra's algorithm. NOT a tree. Uses C++.")
        self.refresh()

        for query in ("Dijkstra's", "NOT a tree", "c++", "what is a graph?", "graph OR queue", "*"):
            with self.subTest(query=query):
                vaultSearch.search_content(query, db_path=self.db_path)

    def test_a_query_of_pure_punctuation_is_no_search(self):
        self.note("Dijkstra.md", "Finds the shortest path.")
        self.refresh()

        self.assertEqual(self.paths("??? !!!"), [])

    def test_a_private_note_left_in_the_index_is_never_returned(self):
        # refresh() can't index Private, so this writes the row straight into
        # the index - a stale db from before a folder was renamed. The row
        # outranks the real note, so filtering has to happen before the cap.
        self.note("Dijkstra.md", "Finds the shortest path eventually, after a while.")
        self.refresh()
        conn = vaultIndex.connect(self.db_path)
        try:
            conn.execute(
                "INSERT INTO notes (path, content, mtime) VALUES (?, ?, ?)",
                (str(Path("6 Private") / "Secret.md"), "shortest path", 1.0),
            )
            conn.commit()
        finally:
            conn.close()

        self.assertEqual(self.paths("shortest path"), [str(Path("3 Reference") / "Dijkstra.md")])

    def test_the_best_match_comes_first(self):
        # The names carry the test: refresh() indexes in directory order, so
        # the dense note has to sort *after* the weak one for the assertion
        # to fail when the ranking is dropped. Named "Alpha"/"Zeta" so a
        # tidy-up can't rename them back into insertion order.
        self.note("Alpha.md", "graph " + "filler " * 200)
        self.note("Zeta.md", "graph graph graph graph graph")
        self.refresh()

        self.assertEqual(self.paths("graph"), [
            str(Path("3 Reference") / "Zeta.md"),
            str(Path("3 Reference") / "Alpha.md"),
        ])

    def test_candidates_are_capped(self):
        for index in range(vaultSearch.CONTENT_MATCH_LIMIT + 3):
            self.note(f"Note {index}.md", "Finds the shortest path.")
        self.refresh()

        self.assertEqual(len(self.paths("shortest path")), vaultSearch.CONTENT_MATCH_LIMIT)

    def test_no_hits_is_an_empty_list(self):
        self.note("Dijkstra.md", "Finds the shortest path.")
        self.refresh()

        self.assertEqual(self.paths("photosynthesis"), [])


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
        (korean / "Vocab.md").write_text("| Word | Meaning |\n| --- | --- |\n| 안녕 | hello |\n", encoding="utf-8")

        path = vaultSearch.append_vocab_row("감사", "thanks", vault_path=self.vault)

        self.assertEqual(path, korean / "Vocab.md")
        self.assertEqual(path.read_text(encoding="utf-8"), "| Word | Meaning |\n| --- | --- |\n| 안녕 | hello |\n| 감사 | thanks |\n")

    def test_append_vocab_row_flattens_carriage_returns_so_the_row_stays_findable(self):
        korean = self.vault / "2 Areas" / "Korean"
        korean.mkdir(parents=True)
        (korean / "Vocab.md").write_text("", encoding="utf-8")

        path = vaultSearch.append_vocab_row("감사", "thanks\r\ngratitude\rthank you", vault_path=self.vault)

        self.assertEqual(
            path.read_bytes().decode("utf-8").splitlines(),
            ["| Word | Meaning |", "| --- | --- |", "| 감사 | thanks gratitude thank you |"],
        )

    def test_append_vocab_row_starts_a_new_line_when_the_file_does_not_end_with_one(self):
        # Obsidian can save a note without a trailing newline - the new row
        # must not glue onto the last table row.
        korean = self.vault / "2 Areas" / "Korean"
        korean.mkdir(parents=True)
        (korean / "Vocab.md").write_text("| Word | Meaning |\n| --- | --- |\n| 안녕 | hello |", encoding="utf-8")

        path = vaultSearch.append_vocab_row("감사", "thanks", vault_path=self.vault)

        self.assertEqual(path.read_text(encoding="utf-8"), "| Word | Meaning |\n| --- | --- |\n| 안녕 | hello |\n| 감사 | thanks |\n")

    def test_append_vocab_row_goes_after_the_last_filled_row_not_after_empty_rows(self):
        # Obsidian's table editor leaves empty rows and a trailing blank line
        # - appending to the end of the file would land outside the table.
        korean = self.vault / "2 Areas" / "Korean"
        korean.mkdir(parents=True)
        (korean / "Vocab.md").write_bytes(
            "---\ntype: vocab\n---\n\n| Word | Meaning |\n| ---- | ------- |\n| 안녕   | Hello   |\n|      |         |\n|      |         |\n\n\n".encode()
        )

        path = vaultSearch.append_vocab_row("감사", "thanks", vault_path=self.vault)

        self.assertEqual(
            path.read_bytes().decode("utf-8"),
            "---\ntype: vocab\n---\n\n| Word | Meaning |\n| ---- | ------- |\n| 안녕   | Hello   |\n| 감사 | thanks |\n|      |         |\n|      |         |\n\n\n",
        )

    def test_append_vocab_row_goes_right_after_the_separator_of_an_empty_table(self):
        korean = self.vault / "2 Areas" / "Korean"
        korean.mkdir(parents=True)
        (korean / "Vocab.md").write_bytes("| Word | Meaning |\n| ---- | ------- |\n|  |  |\n\nnotes below\n".encode())

        path = vaultSearch.append_vocab_row("감사", "thanks", vault_path=self.vault)

        self.assertEqual(
            path.read_bytes().decode("utf-8"),
            "| Word | Meaning |\n| ---- | ------- |\n| 감사 | thanks |\n|  |  |\n\nnotes below\n",
        )

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

        self.assertEqual(path.read_text(encoding="utf-8"), "| Word | Meaning |\n| --- | --- |\n| or | either\\|or |\n")

    def test_append_vocab_row_strips_newlines_from_a_multiline_translation(self):
        korean = self.vault / "2 Areas" / "Korean"
        korean.mkdir(parents=True)
        (korean / "Vocab.md").write_text("", encoding="utf-8")

        path = vaultSearch.append_vocab_row("word", "line one\nline two", vault_path=self.vault)

        self.assertEqual(path.read_text(encoding="utf-8"), "| Word | Meaning |\n| --- | --- |\n| word | line one line two |\n")

    def test_append_grammar_row_appends_to_the_grammar_table_not_the_vocab_one(self):
        # The two tables are kept apart on purpose (resolve_breakdown) - a
        # grammar point landing in Vocab.md would answer a word lookup.
        korean = self.vault / "2 Areas" / "Korean"
        korean.mkdir(parents=True)
        (korean / "Vocab.md").write_text("| Word | Meaning |\n| --- | --- |\n| 안녕 | hello |\n", encoding="utf-8")
        (korean / "Grammar.md").write_text("| Word | Explanation |\n| --- | --- |\n| -이/가 | subject marker |\n", encoding="utf-8")

        path = vaultSearch.append_grammar_row("-은/는", "topic marker", vault_path=self.vault)

        self.assertEqual(path, korean / "Grammar.md")
        self.assertEqual(
            path.read_text(encoding="utf-8"),
            "| Word | Explanation |\n| --- | --- |\n| -이/가 | subject marker |\n| -은/는 | topic marker |\n",
        )
        self.assertEqual((korean / "Vocab.md").read_text(encoding="utf-8"), "| Word | Meaning |\n| --- | --- |\n| 안녕 | hello |\n")

    def test_append_grammar_row_creates_a_real_table_when_the_note_does_not_exist(self):
        # The bug Derich hit on 2026-09-20: Grammar.md did not exist, so every
        # confirmed point was appended as a bare "| a | b |" line with no
        # header or separator above it. Obsidian renders those as literal
        # text, never as a table, and resolve_breakdown never matched them.
        korean = self.vault / "2 Areas" / "Korean"
        korean.mkdir(parents=True)

        path = vaultSearch.append_grammar_row("-ㅂ니다", "formal polite ending", vault_path=self.vault)

        self.assertEqual(path.read_text(encoding="utf-8"), "| Word | Explanation |\n| --- | --- |\n| -ㅂ니다 | formal polite ending |\n")

    def test_a_second_point_reuses_the_table_instead_of_starting_another(self):
        korean = self.vault / "2 Areas" / "Korean"
        korean.mkdir(parents=True)

        vaultSearch.append_grammar_row("-ㅂ니다", "formal polite ending", vault_path=self.vault)
        path = vaultSearch.append_grammar_row("-은/는", "topic marker", vault_path=self.vault)

        self.assertEqual(
            path.read_text(encoding="utf-8"),
            "| Word | Explanation |\n| --- | --- |\n| -ㅂ니다 | formal polite ending |\n| -은/는 | topic marker |\n",
        )

    def test_a_table_started_under_existing_prose_keeps_a_blank_line_above_it(self):
        # A note that is notes-first, table-later: the header must not glue
        # onto the prose, or Obsidian reads neither as a table.
        korean = self.vault / "2 Areas" / "Korean"
        korean.mkdir(parents=True)
        (korean / "Grammar.md").write_text("# Grammar\n\nPoints I have hit.\n", encoding="utf-8")

        path = vaultSearch.append_grammar_row("-에", "destination particle", vault_path=self.vault)

        self.assertEqual(
            path.read_text(encoding="utf-8"),
            "# Grammar\n\nPoints I have hit.\n\n| Word | Explanation |\n| --- | --- |\n| -에 | destination particle |\n",
        )

    def test_a_note_written_without_a_trailing_newline_still_gets_its_table(self):
        korean = self.vault / "2 Areas" / "Korean"
        korean.mkdir(parents=True)
        (korean / "Grammar.md").write_text("Points I have hit.", encoding="utf-8")

        path = vaultSearch.append_grammar_row("-에", "destination particle", vault_path=self.vault)

        self.assertEqual(
            path.read_text(encoding="utf-8"),
            "Points I have hit.\n\n| Word | Explanation |\n| --- | --- |\n| -에 | destination particle |\n",
        )


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


class AllNotesTests(unittest.TestCase):
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

        notes = vaultSearch.all_notes(db_path=self.db_path, now=now)

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

        notes = vaultSearch.all_notes(db_path=self.db_path, now=now)

        self.assertEqual([note["recent"] for note in notes], [True, False])

    def test_never_lists_a_private_note(self):
        now = 1_000_000
        self.note(Path("6 Private") / "Secret.md", now - 60)
        self.note(Path("1 Project") / "Plan.md", now - 120)
        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)

        notes = vaultSearch.all_notes(db_path=self.db_path, now=now)

        self.assertEqual([note["path"] for note in notes], [str(Path("1 Project") / "Plan.md")])

    def test_never_lists_a_folder_a_link_should_not_go_in(self):
        # Archive, Templates, Atlas (links-only hubs) and Reference (Bel's
        # concept notes) stay indexed, but are never offered in the picker.
        now = 1_000_000
        for folder in ("4 Archive", "Templates", "5 Atlas", "3 Reference", "5 ATLAS"):
            self.note(Path(folder) / "Skipped.md", now - 60)
        self.note(Path("2 Areas") / "Archive" / "Kept.md", now - 120)
        self.note(Path("Second Brain.md"), now - 180)
        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)

        notes = vaultSearch.all_notes(db_path=self.db_path, now=now)

        self.assertEqual([note["path"] for note in notes], [
            str(Path("2 Areas") / "Archive" / "Kept.md"),
            "Second Brain.md",
        ])


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

    def insert(self, concept="Dijkstra", gist="shortest paths in weighted graphs"):
        return vaultSearch.insert_concept_link(concept, self.picked, gist=gist, vault_path=self.vault)

    def test_insert_concept_link_starts_a_concepts_section_with_a_gist_bullet(self):
        # Issue 25. The note has no trailing newline, as Obsidian can save it.
        plan = self.plan()

        result = self.insert()

        self.assertEqual(result, plan)
        self.assertEqual(
            plan.read_bytes(),
            b"Today I learned about pathfinding.\n\n## Concepts\n- [[Dijkstra]] \xe2\x80\x94 shortest paths in weighted graphs\n",
        )

    def test_insert_concept_link_adds_after_the_existing_sections_last_bullet(self):
        # The heading is found case-insensitively, and `*` bullets count too.
        plan = self.plan()
        plan.write_bytes(b"Notes.\n\n## concepts\n- [[Big O]] \xe2\x80\x94 growth rate\n* [[Heap]]\n")

        self.insert()

        self.assertEqual(
            plan.read_bytes().decode("utf-8"),
            "Notes.\n\n## concepts\n- [[Big O]] — growth rate\n* [[Heap]]\n- [[Dijkstra]] — shortest paths in weighted graphs\n",
        )

    def test_insert_concept_link_stays_inside_a_section_followed_by_other_content(self):
        plan = self.plan()
        plan.write_bytes(b"## Concepts\n- [[Big O]]\n\n## Later\nMore notes.")

        self.insert()

        self.assertEqual(
            plan.read_bytes().decode("utf-8"),
            "## Concepts\n- [[Big O]]\n- [[Dijkstra]] — shortest paths in weighted graphs\n\n## Later\nMore notes.",
        )

    def test_insert_concept_link_skips_a_concept_the_section_already_lists(self):
        plan = self.plan()
        plan.write_bytes(b"## Concepts\n- [[dijkstra]] \xe2\x80\x94 older gist\n")

        result = self.insert()

        self.assertEqual(result, plan)  # still reported as connected
        self.assertEqual(plan.read_bytes(), b"## Concepts\n- [[dijkstra]] \xe2\x80\x94 older gist\n")

    def test_insert_concept_link_counts_heading_and_alias_links_as_already_listed(self):
        plan = self.plan()
        for listed in ("- [[Dijkstra#Proof]]\n", "- [[Dijkstra|shortest path]]\n"):
            with self.subTest(listed=listed):
                plan.write_text("## Concepts\n" + listed, encoding="utf-8")

                self.insert()

                self.assertEqual(plan.read_text(encoding="utf-8"), "## Concepts\n" + listed)

    def test_insert_concept_link_ignores_a_link_inside_another_bullets_gist(self):
        # Only a bullet's own leading link says which concept it lists.
        plan = self.plan()
        plan.write_bytes(b"## Concepts\n- [[Big O]] \xe2\x80\x94 cost of [[Dijkstra]]\n")

        self.insert()

        self.assertTrue(plan.read_text(encoding="utf-8").endswith("- [[Dijkstra]] — shortest paths in weighted graphs\n"))

    def test_insert_concept_link_without_a_gist_writes_a_bare_bullet(self):
        plan = self.plan()

        self.insert(gist="")

        self.assertTrue(plan.read_text(encoding="utf-8").endswith("## Concepts\n- [[Dijkstra]]\n"))

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


class ConceptGistTests(unittest.TestCase):
    """The one-line gist beside a `[[Concept]]` bullet (issue 25)."""

    def test_the_first_sentence_without_its_full_stop(self):
        self.assertEqual(
            vaultSearch.concept_gist("Finds shortest paths in weighted graphs. It is greedy."),
            "Finds shortest paths in weighted graphs",
        )

    def test_skips_frontmatter_and_headings(self):
        text = "---\ntags: [algo]\n---\n# Dijkstra\n\nFinds shortest\npaths. It is greedy."

        self.assertEqual(vaultSearch.concept_gist(text), "Finds shortest paths")

    def test_a_long_sentence_is_cut_at_a_word(self):
        gist = vaultSearch.concept_gist("word " * 30)

        self.assertLessEqual(len(gist), vaultSearch.GIST_MAX_LENGTH)
        self.assertTrue(gist.endswith("word…"))

    def test_no_text_means_no_gist(self):
        self.assertEqual(vaultSearch.concept_gist("# Only a heading\n"), "")


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

        self.assertEqual(self.plan.read_text(encoding="utf-8"), "Notes.\n\n## Concepts\n- [[Dijkstra]] — Shortest path algorithm\n")
        self.assertEqual(sorted(p.name for p in self.reference.iterdir()), ["Dijkstra.md"])

    def test_a_miss_writes_the_draft_then_links_it(self):
        miss = {"hit": False, "draft": "Finds shortest paths. It is greedy."}

        vaultSearch.confirm_pick("Dijkstra", miss, self.picked, vault_path=self.vault)

        self.assertEqual((self.reference / "Dijkstra.md").read_text(encoding="utf-8"), "Finds shortest paths. It is greedy.")
        self.assertEqual(self.plan.read_text(encoding="utf-8"), "Notes.\n\n## Concepts\n- [[Dijkstra]] — Finds shortest paths\n")

    def test_a_miss_that_would_overwrite_a_note_links_nothing(self):
        # A stale index can miss a note Derich just created in Obsidian.
        (self.reference / "Dijkstra.md").write_text("real note", encoding="utf-8")
        miss = {"hit": False, "draft": "Drafted explanation."}

        with self.assertRaises(FileExistsError):
            vaultSearch.confirm_pick("Dijkstra", miss, self.picked, vault_path=self.vault)

        self.assertEqual((self.reference / "Dijkstra.md").read_text(encoding="utf-8"), "real note")
        self.assertEqual(self.plan.read_text(encoding="utf-8"), "Notes.")


class ListInboxEntriesTests(unittest.TestCase):
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


SENTENCE = "저는 매일 학교에 갑니다"

BREAKDOWN_REPLY = """{
  "translation": "I go to school every day",
  "words": [
    {"surface": "저는", "lemma": "저", "meaning": "I, me"},
    {"surface": "매일", "lemma": "매일", "meaning": "every day"},
    {"surface": "학교에", "lemma": "학교", "meaning": "school"},
    {"surface": "갑니다", "lemma": "가다", "meaning": "to go"}
  ],
  "grammar": [
    {"point": "-은/는", "meaning": "marks the topic of the sentence"},
    {"point": "-에", "meaning": "marks a destination or location"},
    {"point": "-ㅂ니다", "meaning": "the formal polite sentence ending"}
  ]
}"""


class ParseBreakdownTests(unittest.TestCase):
    def test_parses_a_reply_into_translation_words_and_grammar(self):
        breakdown = vaultSearch.parse_breakdown(BREAKDOWN_REPLY)

        self.assertEqual(breakdown["translation"], "I go to school every day")
        self.assertEqual([word["surface"] for word in breakdown["words"]], ["저는", "매일", "학교에", "갑니다"])
        self.assertEqual([word["lemma"] for word in breakdown["words"]], ["저", "매일", "학교", "가다"])
        self.assertEqual([point["point"] for point in breakdown["grammar"]], ["-은/는", "-에", "-ㅂ니다"])

    def test_reads_the_json_out_of_a_reply_that_says_more_than_the_object(self):
        # BEL_PROMPT's tutor persona can still add a line around the object.
        text = f"Here you go:\n\n{BREAKDOWN_REPLY}\n\nHope that helps."

        self.assertEqual(vaultSearch.parse_breakdown(text)["translation"], "I go to school every day")

    def test_an_answer_that_is_not_a_breakdown_is_no_breakdown_at_all(self):
        # The degrade the card relies on: a plain translation stays a plain
        # translation instead of raising.
        for text in ("I go to school every day", "", "{ not json", "[]", '{"translation": 3}', '{"translation": "  "}'):
            with self.subTest(text=text):
                self.assertIsNone(vaultSearch.parse_breakdown(text))

    def test_an_entry_missing_a_field_is_dropped_not_fatal(self):
        text = """{"translation": "I go", "words": [
            {"surface": "저는", "lemma": "저", "meaning": "I, me"},
            {"surface": "갑니다", "meaning": "to go"},
            "갑니다"
        ], "grammar": "none"}"""

        breakdown = vaultSearch.parse_breakdown(text)

        self.assertEqual([word["lemma"] for word in breakdown["words"]], ["저"])
        self.assertEqual(breakdown["grammar"], [])


class ResolveBreakdownTests(unittest.TestCase):
    def setUp(self):
        self.vault_dir = tempfile.TemporaryDirectory()
        self.db_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.vault_dir.cleanup)
        self.addCleanup(self.db_dir.cleanup)
        self.vault = Path(self.vault_dir.name)
        self.db_path = Path(self.db_dir.name) / "vault-index.sqlite3"
        self.korean = self.vault / "2 Areas" / "Korean"
        self.korean.mkdir(parents=True)

    def writeTable(self, name, header, rows):
        lines = [f"| {header[0]} | {header[1]} |\n", "| --- | --- |\n"]
        lines += [f"| {first} | {second} |\n" for first, second in rows]
        (self.korean / name).write_text("".join(lines), encoding="utf-8")

    def resolve(self, text=BREAKDOWN_REPLY):
        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)
        return vaultSearch.resolve_breakdown(vaultSearch.parse_breakdown(text), db_path=self.db_path)

    def test_every_word_already_in_vocab_md_resolves_by_lemma_not_surface_form(self):
        # The trap this feature exists to avoid: three of these four surface
        # forms ("저는", "학교에", "갑니다") can never match their own row,
        # because search_notes matches a whole cell.
        self.writeTable("Vocab.md", ("word", "meaning"), [("저", "I, me"), ("매일", "every day"), ("학교", "school"), ("가다", "to go")])

        resolved = self.resolve()

        self.assertEqual([word["row"] for word in resolved["words"]], [
            ["저", "I, me"], ["매일", "every day"], ["학교", "school"], ["가다", "to go"],
        ])

    def test_a_lemma_with_no_row_is_reported_as_unfiled(self):
        self.writeTable("Vocab.md", ("word", "meaning"), [("저", "I, me")])

        resolved = self.resolve()

        self.assertEqual([word["row"] is None for word in resolved["words"]], [False, True, True, True])

    def test_grammar_points_resolve_against_grammar_md(self):
        self.writeTable("Grammar.md", ("point", "meaning"), [("-은/는", "topic particle"), ("-ㅂ니다", "formal polite ending")])

        resolved = self.resolve()

        self.assertEqual([point["row"] for point in resolved["grammar"]], [
            ["-은/는", "topic particle"], None, ["-ㅂ니다", "formal polite ending"],
        ])

    def test_a_vault_with_neither_table_resolves_everything_as_unfiled(self):
        resolved = self.resolve()

        self.assertTrue(all(word["row"] is None for word in resolved["words"]))
        self.assertTrue(all(point["row"] is None for point in resolved["grammar"]))
        self.assertEqual(resolved["translation"], "I go to school every day")

    def test_a_word_is_not_answered_out_of_the_grammar_table_nor_the_reverse(self):
        # The two tables stay apart: "가다" filed as a grammar point is not a
        # vocab row, and vice versa.
        self.writeTable("Vocab.md", ("word", "meaning"), [("-은/는", "topic particle")])
        self.writeTable("Grammar.md", ("point", "meaning"), [("가다", "to go")])

        resolved = self.resolve()

        self.assertTrue(all(word["row"] is None for word in resolved["words"]))
        self.assertTrue(all(point["row"] is None for point in resolved["grammar"]))

    def test_a_locked_index_resolves_everything_as_unfiled_rather_than_raising(self):
        # Same guarantee SearchWorker.run gives the lookup itself - the
        # breakdown still shows, with nothing claimed to be filed.
        self.writeTable("Vocab.md", ("word", "meaning"), [("저", "I, me")])
        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)

        for error in (sqlite3.OperationalError("database is locked"), OSError("no space left on device")):
            with self.subTest(error=error), patch("vaultSearch.vaultIndex.connect", side_effect=error):
                resolved = vaultSearch.resolve_breakdown(vaultSearch.parse_breakdown(BREAKDOWN_REPLY), db_path=self.db_path)

                self.assertTrue(all(word["row"] is None for word in resolved["words"]))
                self.assertEqual(resolved["translation"], "I go to school every day")


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

    def test_a_miss_carries_the_notes_that_may_already_cover_it(self):
        reference = self.vault / "3 Reference"
        reference.mkdir()
        (reference / "Dijkstra.md").write_text("Dijkstra's algorithm finds the shortest path.")

        outcome = vaultSearch.lookup("Dijkstra's algorithm", vault_path=self.vault, db_path=self.db_path)

        self.assertIsNone(outcome["found"])
        self.assertEqual(
            [note["path"] for note in outcome["content_matches"]],
            [str(Path("3 Reference") / "Dijkstra.md")],
        )

    def test_a_korean_miss_looks_for_no_content_matches(self):
        # The Korean flows have their own block, so nothing would show them -
        # the query is skipped rather than run and thrown away.
        korean = self.vault / "2 Areas" / "Korean"
        korean.mkdir(parents=True)
        (korean / "Grammar.md").write_text("안녕 is the casual greeting.", encoding="utf-8")

        outcome = vaultSearch.lookup("안녕", vault_path=self.vault, db_path=self.db_path)

        self.assertIsNone(outcome["found"])
        self.assertEqual(outcome["content_matches"], [])

    def test_a_hit_looks_for_no_candidates(self):
        # An exact title is a certainty, so there is no maybe to offer - and
        # no reason to pay for a second query.
        reference = self.vault / "3 Reference"
        reference.mkdir()
        (reference / "Dijkstra.md").write_text("Dijkstra's algorithm finds the shortest path.")

        outcome = vaultSearch.lookup("Dijkstra", vault_path=self.vault, db_path=self.db_path)

        self.assertIsNotNone(outcome["found"])
        self.assertEqual(outcome["content_matches"], [])

    def test_also_lists_every_indexed_note_for_the_picker_filter(self):
        # Issue 24: the filter searches the whole index, not just the recent
        # notes, and filters in memory rather than querying per keystroke.
        project = self.vault / "1 Project"
        project.mkdir()
        for i in range(vaultSearch.RECENT_NOTES_LIMIT + 5):
            (project / f"Note {i}.md").write_text("content", encoding="utf-8")
        private = self.vault / "6 Private"
        private.mkdir()
        (private / "Secret.md").write_text("Private.", encoding="utf-8")

        outcome = vaultSearch.lookup("Dijkstra", vault_path=self.vault, db_path=self.db_path)

        self.assertEqual(len(outcome["notes"]), vaultSearch.RECENT_NOTES_LIMIT)
        self.assertEqual(len(outcome["all_notes"]), vaultSearch.RECENT_NOTES_LIMIT + 5)
        self.assertEqual(outcome["all_notes"][:vaultSearch.RECENT_NOTES_LIMIT], outcome["notes"])
        self.assertFalse(any("Private" in note["path"] for note in outcome["all_notes"]))


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

        self.assertEqual(outcomes, [{"found": None, "content_matches": [], "notes": [], "all_notes": [], "vocab": None}])


class ResolveWorkerTests(unittest.TestCase):
    def setUp(self):
        self.breakdown = vaultSearch.parse_breakdown(BREAKDOWN_REPLY)

    def test_run_emits_the_resolved_breakdown(self):
        resolved = {"translation": "x", "words": [], "grammar": []}
        worker = vaultSearch.ResolveWorker(self.breakdown)
        seen = []
        worker.finished.connect(seen.append)

        with patch.object(vaultSearch, "resolve_breakdown", return_value=resolved):
            worker.run()

        self.assertEqual(seen, [resolved])

    def test_run_still_emits_everything_unfiled_when_the_resolve_raises(self):
        # Same guarantee SearchWorker.run gives the lookup: without it the
        # card's breakdown block never leaves its pending state. Nothing may
        # be claimed as already saved off the back of a failed read.
        worker = vaultSearch.ResolveWorker(self.breakdown)
        seen = []
        worker.finished.connect(seen.append)

        with patch.object(vaultSearch, "resolve_breakdown", side_effect=sqlite3.OperationalError("locked")):
            worker.run()

        resolved = seen[0]
        self.assertEqual(resolved["translation"], "I go to school every day")
        self.assertEqual([word["surface"] for word in resolved["words"]], ["저는", "매일", "학교에", "갑니다"])
        self.assertTrue(all(word["row"] is None for word in resolved["words"]))
        self.assertTrue(all(point["row"] is None for point in resolved["grammar"]))


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

        plan = [{"path": str(Path("1 Project") / "Plan.md"), "recent": True}]
        self.assertEqual(self.results, [{
            "hit": False,
            "kind": "concept",
            "draft": "A drafted explanation.",
            "notes": plan,
            "all_notes": plan,
            "content_matches": [],
        }])

    def test_a_concept_miss_reports_the_notes_that_may_already_cover_it(self):
        # The whole point: "? Dijkstra's algorithm" misses on the title but
        # the note is right there, so the card can say so before drafting a
        # second one.
        reference = self.vault / "3 Reference"
        reference.mkdir()
        (reference / "Dijkstra.md").write_text("Dijkstra's algorithm finds the shortest path.")
        explain = self.start("Dijkstra's algorithm")

        explain.request.chunk.emit("A drafted explanation.")
        explain.request.finished.emit()

        self.assertEqual(
            [note["path"] for note in self.results[0]["content_matches"]],
            [str(Path("3 Reference") / "Dijkstra.md")],
        )

    def test_only_a_concept_lookup_carries_content_matches(self):
        # The Korean flows have their own block; two lists of notes over one
        # translation is noise, not help.
        explain = self.start("감사")

        explain.request.finished.emit()

        self.assertNotIn("content_matches", self.results[0])

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
        self.assertEqual([note["path"] for note in self.results[0]["all_notes"]], [str(Path("1 Project") / "Plan.md")])

    def test_a_korean_miss_starts_a_request_and_reports_its_draft_as_kind_vocab(self):
        # Issue 22: Claude answers what the word means, but as kind "vocab" -
        # never a concept draft that could be saved as "3 Reference/<word>.md".
        explain = self.start("감사")

        self.assertIsInstance(explain.request, FakeClaudeRequest)
        self.assertTrue(explain.request.started)
        self.assertIn("감사", explain.request.prompt)
        explain.request.chunk.emit("Thanks.")
        explain.request.finished.emit()

        self.assertEqual(self.results, [{"hit": False, "kind": "vocab", "draft": "Thanks.", "notes": [], "all_notes": [], "vocab": None}])

    def test_a_korean_miss_reports_the_indexed_vocab_md_to_save_into(self):
        korean = self.vault / "2 Areas" / "Korean"
        korean.mkdir(parents=True)
        (korean / "Vocab.md").write_text("| Word | Meaning |\n| --- | --- |\n", encoding="utf-8")
        explain = self.start("감사")

        explain.request.finished.emit()

        self.assertEqual(self.results[0]["vocab"], {"path": str(Path("2 Areas") / "Korean" / "Vocab.md"), "recent": True})

    def test_a_korean_miss_asks_for_a_translation_only(self):
        explain = self.start("감사")

        self.assertIn("only the translation", explain.request.prompt)

    def test_a_failed_korean_answer_is_reported_as_no_draft(self):
        explain = self.start("감사")

        explain.request.chunk.emit("[error: claude exited]")
        explain.request.failed = True
        explain.request.finished.emit()

        self.assertEqual((self.results[0]["kind"], self.results[0]["draft"]), ("vocab", ""))

    def test_a_korean_sentence_asks_for_a_breakdown_not_a_bare_translation(self):
        explain = self.start(SENTENCE)

        self.assertIn(SENTENCE, explain.request.prompt)
        self.assertIn('"lemma"', explain.request.prompt)
        self.assertNotIn("only the translation", explain.request.prompt)

    def test_a_korean_sentence_reports_the_parsed_breakdown_and_its_translation(self):
        explain = self.start(SENTENCE)

        explain.request.chunk.emit(BREAKDOWN_REPLY)
        explain.request.finished.emit()

        result = self.results[0]
        self.assertEqual((result["hit"], result["kind"]), (False, "sentence"))
        self.assertEqual(result["draft"], "I go to school every day")
        self.assertEqual([word["lemma"] for word in result["breakdown"]["words"]], ["저", "매일", "학교", "가다"])
        self.assertEqual([point["point"] for point in result["breakdown"]["grammar"]], ["-은/는", "-에", "-ㅂ니다"])

    def test_a_korean_sentence_does_not_touch_the_index_from_the_ui_thread(self):
        # answered() runs on the Qt main thread, where a concurrent lookup's
        # refresh() holds BEGIN IMMEDIATE for a whole vault walk - a read here
        # would sit on SQLite's busy timeout with the card frozen. Resolving
        # belongs to whoever builds the picker, off-thread.
        explain = self.start(SENTENCE)

        with patch("vaultSearch.vaultIndex.connect", side_effect=AssertionError("read the index from answered()")):
            explain.request.chunk.emit(BREAKDOWN_REPLY)
            explain.request.finished.emit()

        self.assertEqual(self.results[0]["draft"], "I go to school every day")

    def test_a_sentence_answer_that_botched_the_json_is_reported_as_no_draft(self):
        # A cut-off object, or a stray "}" after it, must never reach the chat
        # as a raw JSON blob - only an answer that ignored the format outright
        # is worth showing as a plain translation.
        for text in (BREAKDOWN_REPLY[:80], f"{BREAKDOWN_REPLY}\n\nHope that helps :}}", "{'translation': 'I go'}"):
            with self.subTest(text=text):
                self.results.clear()
                explain = self.start(SENTENCE)

                explain.request.chunk.emit(text)
                explain.request.finished.emit()

                self.assertEqual((self.results[0]["draft"], self.results[0]["breakdown"]), ("", None))

    def test_a_sentence_answer_with_an_empty_translation_is_no_breakdown(self):
        # A valid-but-empty translation would otherwise blank the draft and
        # leave the card saying "couldn't draft an explanation."
        explain = self.start(SENTENCE)

        explain.request.chunk.emit('{"translation": "  ", "words": [], "grammar": []}')
        explain.request.finished.emit()

        self.assertEqual((self.results[0]["draft"], self.results[0]["breakdown"]), ("", None))

    def test_a_sentence_answer_that_is_not_a_breakdown_stays_a_plain_translation(self):
        explain = self.start(SENTENCE)

        explain.request.chunk.emit("I go to school every day")
        explain.request.finished.emit()

        self.assertEqual(self.results[0]["draft"], "I go to school every day")
        self.assertIsNone(self.results[0]["breakdown"])

    def test_a_failed_sentence_answer_is_reported_as_no_draft_and_no_breakdown(self):
        explain = self.start(SENTENCE)

        explain.request.chunk.emit("[error: claude exited]")
        explain.request.failed = True
        explain.request.finished.emit()

        self.assertEqual((self.results[0]["draft"], self.results[0]["breakdown"]), ("", None))

    def test_a_sentence_already_filed_as_a_vocab_row_is_answered_from_it(self):
        # search_notes can whole-cell match a sentence written into a Vocab
        # row; that's a hit like any other, answered from the vault with no
        # request and no breakdown.
        korean = self.vault / "2 Areas" / "Korean"
        korean.mkdir(parents=True)
        (korean / "Vocab.md").write_text(f"| word | meaning |\n| --- | --- |\n| {SENTENCE} | I go to school |\n", encoding="utf-8")

        explain = self.start(SENTENCE)

        self.assertIsNone(explain.request)
        self.assertEqual(self.results[0]["kind"], "vocab")

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


if __name__ == "__main__":
    unittest.main()
