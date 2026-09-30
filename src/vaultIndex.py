# Incremental SQLite FTS5 index over the user's Obsidian vault, so
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

import cardStore

# The vault Bel reads and writes: None until one is chosen in Settings, which
# leaves the vault features (`?` lookups, `! save`) with nothing to work on.
# Set by load_vault_path() at startup and save_vault_path() on a pick;
# everything else reads it through current_vault() at call time, so a change
# reaches lookups and saves without a restart. refresh() drops the old
# vault's rows on its next run, since it removes whatever it no longer sees.
VAULT_PATH = None
VAULT_STORE_KEY = "vault"


def current_vault(vault_path=None):
    """`vault_path`, else the chosen vault. Raises FileNotFoundError - an
    OSError, which every caller already treats as "couldn't" - when there is none."""
    vault_path = vault_path or VAULT_PATH
    if vault_path is None:
        raise FileNotFoundError("no vault chosen")
    return vault_path

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


def is_off_limits_root(path):
    """True if `path` is, or sits inside, a folder the vault rules exclude - a
    `6 Private` picked as the vault would otherwise be indexed from the inside."""
    return any(folder_name(Path(part)).casefold() in EXCLUDED_FOLDERS for part in Path(path).parts)


def load_vault_path():
    """Applies the saved vault folder. Called once at startup."""
    global VAULT_PATH
    saved = cardStore.load(VAULT_STORE_KEY, {}).get("path")
    if saved and not is_off_limits_root(saved):
        VAULT_PATH = Path(saved)


def save_vault_path(path):
    """Points Bel at `path`. Raises ValueError for a folder the never-access rule covers."""
    global VAULT_PATH
    if is_off_limits_root(path):
        raise ValueError("that folder is off limits")
    VAULT_PATH = Path(path)
    cardStore.save(VAULT_STORE_KEY, {"path": str(VAULT_PATH)})


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
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS notes USING fts5(path, content, mtime UNINDEXED)"
        )
    except Exception:
        # A locked or corrupt db file raises here, before the caller ever
        # gets a connection to close - so close it now (issue 19).
        conn.close()
        raise
    return conn


def refresh(vault_path=None, db_path=None):
    vault_path = current_vault(vault_path)
    conn = connect(db_path)
    try:
        # Rows are written by rowid, never `WHERE path = ?` - rowid is the
        # only thing an FTS5 table can look up without scanning every row
        # (issue 13). The write lock is taken before reading them, so another
        # refresh (a second Bel process) can't change the table underneath
        # and leave these rowids stale.
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute("SELECT rowid, path, mtime FROM notes").fetchall()
        rowids = {path: rowid for rowid, path, mtime in rows}
        stored_mtimes = {path: mtime for rowid, path, mtime in rows}
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

            if relative in rowids:
                conn.execute(
                    "UPDATE notes SET content = ?, mtime = ? WHERE rowid = ?",
                    (content, mtime, rowids[relative]),
                )
            else:
                conn.execute(
                    "INSERT INTO notes (path, content, mtime) VALUES (?, ?, ?)",
                    (relative, content, mtime),
                )

        for relative in set(stored_mtimes) - seen_paths:
            conn.execute("DELETE FROM notes WHERE rowid = ?", (rowids[relative],))

        conn.commit()
    finally:
        conn.close()
