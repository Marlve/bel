import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import vaultIndex


class VaultIndexTests(unittest.TestCase):
    def setUp(self):
        self.vault_dir = tempfile.TemporaryDirectory()
        self.db_dir = tempfile.TemporaryDirectory()
        self.vault = Path(self.vault_dir.name)
        self.db_path = Path(self.db_dir.name) / "vault-index.sqlite3"

    def tearDown(self):
        self.vault_dir.cleanup()
        self.db_dir.cleanup()

    def notes(self):
        conn = vaultIndex.connect(self.db_path)
        try:
            return [row[0] for row in conn.execute("SELECT path FROM notes").fetchall()]
        finally:
            conn.close()

    def search(self, query):
        conn = vaultIndex.connect(self.db_path)
        try:
            return [row[0] for row in conn.execute(
                "SELECT path FROM notes WHERE notes MATCH ?", (query,)
            ).fetchall()]
        finally:
            conn.close()

    def test_search_finds_indexed_content(self):
        area = self.vault / "2 Areas" / "Korean"
        area.mkdir(parents=True)
        (area / "Vocab.md").write_text("Dijkstra shortest path algorithm")
        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)

        self.assertEqual(len(self.search("Dijkstra")), 1)

    def test_excludes_private_folder_entirely(self):
        private_dir = self.vault / "6 Private"
        private_dir.mkdir()
        # Invalid UTF-8: if the indexer ever opened this file with
        # encoding="utf-8" it would raise, so a clean refresh() proves the
        # folder was never even read, not just filtered out afterward.
        (private_dir / "secret.md").write_bytes(b"\xff\xfe not valid utf-8")

        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)

        self.assertEqual(self.notes(), [])

    def test_matches_folder_by_name_ignoring_numeric_prefix(self):
        # "Private" without its usual "6 " prefix is still excluded...
        (self.vault / "Private").mkdir()
        (self.vault / "Private" / "secret.md").write_text("secret content")
        # ...while a folder that merely starts with a digit is not.
        other = self.vault / "6 Other"
        other.mkdir()
        (other / "note.md").write_text("visible content")

        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)

        paths = self.notes()
        self.assertNotIn(str(Path("Private") / "secret.md"), paths)
        self.assertIn(str(Path("6 Other") / "note.md"), paths)

    def test_refresh_reindexes_modified_file(self):
        reference = self.vault / "3 Reference"
        reference.mkdir()
        file_path = reference / "Note.md"
        file_path.write_text("original content")
        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)

        file_path.write_text("updated content")
        future = time.time() + 5
        os.utime(file_path, (future, future))
        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)

        self.assertEqual(self.search("original"), [])
        self.assertEqual(len(self.search("updated")), 1)

    def test_refresh_removes_deleted_file_from_index(self):
        reference = self.vault / "3 Reference"
        reference.mkdir()
        file_path = reference / "Note.md"
        file_path.write_text("temporary content")
        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)

        file_path.unlink()
        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)

        self.assertEqual(self.notes(), [])

    def test_refresh_skips_unchanged_files_on_second_call(self):
        reference = self.vault / "3 Reference"
        reference.mkdir()
        (reference / "Note.md").write_text("hello")
        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)

        with mock.patch.object(Path, "read_text", autospec=True) as mocked_read:
            vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)
        mocked_read.assert_not_called()

    def test_default_index_db_lives_under_bel_home_not_vault(self):
        self.assertEqual(vaultIndex.INDEX_DB_PATH.parent, Path.home() / ".bel")

    def test_excludes_private_folder_case_insensitively(self):
        private_dir = self.vault / "6 PRIVATE"
        private_dir.mkdir()
        (private_dir / "secret.md").write_bytes(b"\xff\xfe not valid utf-8")

        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)

        self.assertEqual(self.notes(), [])

    def test_root_level_uppercase_extension_is_indexed(self):
        (self.vault / "Note.MD").write_text("root level content")

        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)

        self.assertEqual(len(self.search("root")), 1)

    def test_refresh_skips_unreadable_file_without_aborting_others(self):
        reference = self.vault / "3 Reference"
        reference.mkdir()
        (reference / "Good.md").write_text("keep this content")
        (reference / "Bad.md").write_bytes(b"\xff\xfe not valid utf-8")

        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)

        self.assertEqual(len(self.search("keep")), 1)

    def test_refresh_keeps_old_entry_when_file_becomes_unreadable(self):
        reference = self.vault / "3 Reference"
        reference.mkdir()
        file_path = reference / "Note.md"
        file_path.write_text("original content")
        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)
        self.assertEqual(len(self.search("original")), 1)

        file_path.write_bytes(b"\xff\xfe not valid utf-8")
        future = time.time() + 5
        os.utime(file_path, (future, future))
        vaultIndex.refresh(vault_path=self.vault, db_path=self.db_path)

        # A transient/bad read shouldn't drop the file from the index the
        # way a real deletion does - the stale-but-valid entry stays put.
        self.assertEqual(len(self.search("original")), 1)


if __name__ == "__main__":
    unittest.main()
