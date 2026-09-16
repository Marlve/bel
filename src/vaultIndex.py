# Incremental SQLite FTS5 index over Derich's Obsidian vault, so
# search_notes (issue 03 in .scratch/vault-search/, not built yet) has
# something to query without rescanning every markdown file on every call.
# refresh() diffs by mtime against the last-indexed state and only touches
# the FTS table for what actually changed.
#
# `6 Private/` is never opened, read, or listed - see the
# never-access-private-vault-folder rule. iter_markdown_files() enforces
# this by walking top-level folders one at a time and skipping an excluded
# one before ever recursing into it, rather than listing everything and
# filtering afterward.

import re
import sqlite3
from pathlib import Path

# Hardcoded per the vault-search spec - matches Bel's existing preference
# against unrequested configurability. Revisit if Derich ever asks for a
# second vault or a moved path.
VAULT_PATH = Path("C:/Vault/ObsidianVault")

# Bel's own local state, matching the Path.home() / ".bel" pattern already
# used for CLAUDE_CWD in claude.py - never inside the vault folder itself,
# since the vault is a separate git repo (obsidian-git auto-commits it) and
# a binary index there would bloat/conflict that repo.
INDEX_DB_PATH = Path.home() / ".bel" / "vault-index.sqlite3"

# The numeric prefixes ("0 Inbox", "6 Private", ...) are Obsidian
# file-explorer sort cosmetics only - matching is by name after stripping
# them, never by the digits themselves. Casefolded so a rename to
# "6 PRIVATE" or "6 private" (Explorer, a sync tool, a typo) is still
# caught - this exclusion is a hard requirement, not a style convention.
EXCLUDED_FOLDERS = {"private"}


def folder_name(path):
    # Stripped first so a stray leading space (" 6 Private") can't stop the
    # prefix regex from matching at position 0.
    return re.sub(r"^\d+[\s._-]+", "", path.name.strip())


def resolve_top_folder(vault_path, name):
    """Finds vault_path's top-level folder matching `name` once Obsidian's
    numeric sort prefix is stripped (folder_name) - never hardcodes the
    digits themselves. Raises rather than silently picking a fallback
    location if the folder is missing, matching this module's own
    fail-loud convention for vault-shape assumptions. Used by
    vaultSearch.py's write-back functions (issue 03)."""
    for entry in vault_path.iterdir():
        if entry.is_dir() and folder_name(entry).casefold() == name.casefold():
            return entry
    raise FileNotFoundError(f'No "{name}" folder found under {vault_path}')


def iter_markdown_files(vault_path):
    for entry in vault_path.iterdir():
        if entry.is_dir():
            if folder_name(entry).casefold() in EXCLUDED_FOLDERS:
                continue
            yield from entry.rglob("*.md")
        elif entry.suffix.casefold() == ".md":
            yield entry


def connect(db_path=None):
    db_path = db_path or INDEX_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS notes USING fts5(path, content, mtime UNINDEXED)"
    )
    return conn


def refresh(vault_path=None, db_path=None):
    vault_path = vault_path or VAULT_PATH
    conn = connect(db_path)
    try:
        stored_mtimes = dict(conn.execute("SELECT path, mtime FROM notes"))
        seen_paths = set()

        for file_path in iter_markdown_files(vault_path):
            relative = str(file_path.relative_to(vault_path))
            # Marked seen before the read is attempted - a file that fails
            # to read this call (mid-walk delete, invalid encoding) must
            # not be treated as removed-from-vault below; it just keeps
            # whatever it already has in the index, stale or absent.
            seen_paths.add(relative)
            try:
                mtime = file_path.stat().st_mtime
                if stored_mtimes.get(relative) == mtime:
                    continue
                content = file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            conn.execute("DELETE FROM notes WHERE path = ?", (relative,))
            conn.execute(
                "INSERT INTO notes (path, content, mtime) VALUES (?, ?, ?)",
                (relative, content, mtime),
            )

        for relative in set(stored_mtimes) - seen_paths:
            conn.execute("DELETE FROM notes WHERE path = ?", (relative,))

        conn.commit()
    finally:
        conn.close()
