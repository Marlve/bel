# The issue-02 integration point (.scratch/vault-search/issues/02): Bel's
# own Qt-side code calls search_notes() directly and decides hit/miss
# itself - no MCP tool, no agent-loop wiring. askBel() (via ClaudeRequest,
# same convention as CalendarNudgeQuery in calendarNudge.py) is only invoked
# for the miss-case draft.
#
# write_concept_note/append_vocab_row are the confirm-before-write half of
# issue 03 steps 4-5: nothing writes to the vault until one of these is
# called explicitly, which only happens after Derich confirms the drafted
# text - ExplainQuery itself never calls them. The auto-inserted
# `[[Concept]]` link is still deferred - it needs a concrete UI trigger
# point (which note surface represents "the note Derich is currently
# writing") that hasn't been designed yet.
#
# TriageQuery (issue 04) follows the same confirm-before-write split: it
# only proposes a destination folder for an Inbox entry (list_inbox_entries
# + parse_triage_response), never moves anything itself. move_inbox_entry is
# the separate, explicit call for after Derich confirms the proposal - like
# issue 03's write functions, it performs the move unconditionally with no
# confirmation of its own. Wiring a UI surface to drive this per-entry is
# also still deferred, same as the `[[Concept]]` link above.

import re
from pathlib import Path

from PySide6.QtWidgets import QApplication

import vaultIndex
from actions.claudeAction import ClaudeRequest

EXPLAIN_PROMPT_TEMPLATE = 'Explain "{query}" concisely, for a personal reference note.'

# The three inbox-triage destinations (issue 04) - deliberately excludes
# "Inbox" itself and the other top-level folders (Atlas, Private, Templates),
# which issue 04's spec never lists as a triage target.
TRIAGE_FOLDERS = ("Project", "Areas", "Reference")

TRIAGE_PROMPT_TEMPLATE = (
    'Which folder does this inbox note belong in: "Project", "Areas", or '
    '"Reference"? Reply with only that one word.\n\n'
    "Title: {title}\n\n{content}"
)


def folder_matches(path_str, *parts):
    """True if path_str's components equal `parts` case-insensitively. Only
    the folder components (everything but the last, the filename) get
    vaultIndex.folder_name()'s numeric-prefix stripping - files are never
    Obsidian-numbered the way the vault's six top-level folders are, so
    stripping the filename too would corrupt a title that happens to start
    with a digit (e.g. "5 Minute Rule.md")."""
    segments = Path(path_str).parts
    if len(segments) != len(parts):
        return False
    *folder_segments, file_segment = segments
    *folder_parts, file_part = parts
    return (
        file_segment.casefold() == file_part.casefold()
        and all(
            vaultIndex.folder_name(Path(segment)).casefold() == part.casefold()
            for segment, part in zip(folder_segments, folder_parts)
        )
    )


def search_notes(query, db_path=None):
    """Checks for an existing answer to `query` before Bel explains or files
    anything new: an atomic concept note at `<Reference>/<query>.md`, or a
    matching row inside `<Areas>/Korean/Vocab.md`. Returns a dict describing
    the hit, or None on a miss.

    Looks up paths first and only fetches a candidate's content once it has
    matched by path, rather than pulling every note's full text into memory
    up front - the FTS5 index exists precisely so this doesn't have to
    rescan the whole vault's content per call."""
    conn = vaultIndex.connect(db_path)
    try:
        paths = [row[0] for row in conn.execute("SELECT path FROM notes").fetchall()]

        for path in paths:
            if folder_matches(path, "Reference", f"{query}.md"):
                content = conn.execute("SELECT content FROM notes WHERE path = ?", (path,)).fetchone()[0]
                return {"kind": "concept", "path": path, "content": content}

        for path in paths:
            if folder_matches(path, "Areas", "Korean", "Vocab.md"):
                content = conn.execute("SELECT content FROM notes WHERE path = ?", (path,)).fetchone()[0]
                if query.casefold() in content.casefold():
                    return {"kind": "vocab", "path": path, "content": content}

        return None
    finally:
        conn.close()


def escape_table_cell(text):
    """Escapes a value for embedding in a markdown table row - Obsidian's
    table syntax breaks on a literal "|" (spurious column) or newline
    (spurious row), and a drafted translation isn't guaranteed free of
    either."""
    return text.replace("|", "\\|").replace("\n", " ")


def write_concept_note(query, content, vault_path=None):
    """Writes a confirmed miss-case explanation as a new atomic concept
    note (issue 03 step 4). Call only after Derich has confirmed the draft
    - this performs the write unconditionally, with no confirmation of its
    own."""
    if "/" in query or "\\" in query:
        # pathlib treats both as separators on Windows - letting one through
        # would write outside "Reference/" (or raise on a missing
        # intermediate dir) instead of naming a single note.
        raise ValueError(f"query must be a single note title, not a path: {query!r}")
    vault_path = vault_path or vaultIndex.VAULT_PATH
    reference = vaultIndex.resolve_top_folder(vault_path, "Reference")
    path = reference / f"{query}.md"
    path.write_text(content, encoding="utf-8")
    return path


def append_vocab_row(word, translation, vault_path=None):
    """Appends a confirmed word/translation pair to the Korean vocab table
    (issue 03's "same shape applies to Korean vocab" note). Call only after
    Derich has confirmed the row."""
    vault_path = vault_path or vaultIndex.VAULT_PATH
    areas = vaultIndex.resolve_top_folder(vault_path, "Areas")
    path = areas / "Korean" / "Vocab.md"
    with path.open("a", encoding="utf-8") as f:
        f.write(f"| {escape_table_cell(word)} | {escape_table_cell(translation)} |\n")
    return path


def list_inbox_entries(vault_path=None):
    """Lists the vault's Inbox notes for the triage flow (issue 04) to
    propose a destination for, one at a time. Non-recursive - Inbox is a
    flat dropzone of individual notes, not subfoldered like the other
    top-level folders."""
    vault_path = vault_path or vaultIndex.VAULT_PATH
    inbox = vaultIndex.resolve_top_folder(vault_path, "Inbox")
    return sorted(entry for entry in inbox.iterdir() if entry.suffix.casefold() == ".md")


def parse_triage_response(text):
    """Best-effort match of Bel's triage reply to one of TRIAGE_FOLDERS -
    tolerant of extra wrapping text/punctuation, since the model doesn't
    always follow "reply with only that word" exactly. Returns None both
    when nothing recognizable matched and when more than one folder name
    appears (e.g. "not Project, it's Areas") - picking a fixed one in that
    case risks silently inverting the model's actual recommendation, so an
    ambiguous reply must surface as a miss rather than a guess."""
    matches = {
        folder for folder in TRIAGE_FOLDERS
        if re.search(rf"\b{re.escape(folder)}\b", text, re.IGNORECASE)
    }
    if len(matches) == 1:
        return matches.pop()
    return None


def move_inbox_entry(path, folder, vault_path=None):
    """Moves a confirmed inbox entry to its proposed top-level folder
    (issue 04's move-on-confirmation). Call only after Derich has confirmed
    the proposal - performs the move unconditionally, no confirmation of its
    own. Mirrors write_concept_note's fail-loud-if-target-folder-missing
    behavior."""
    if folder not in TRIAGE_FOLDERS:
        raise ValueError(f"folder must be one of {TRIAGE_FOLDERS}, not {folder!r}")
    vault_path = vault_path or vaultIndex.VAULT_PATH
    target = vaultIndex.resolve_top_folder(vault_path, folder)
    path = Path(path)
    destination = target / path.name
    path.rename(destination)
    return destination


class ExplainQuery:
    """Drives the explain-on-miss half of issue 03, using issue 02's chosen
    architecture. Mirrors CalendarNudgeQuery's shape (calendarNudge.py): a
    plain callback-based class wrapping one ClaudeRequest, rather than a
    bare askBel() call, so the CLI subprocess still runs on a background
    QThread instead of blocking the UI."""

    def __init__(self, query, on_result, db_path=None, request_factory=ClaudeRequest):
        self.query = query
        self.on_result = on_result
        self.db_path = db_path
        self.request_factory = request_factory  # swappable in tests, so the miss path never spawns a real `claude` subprocess
        self.text = ""
        self.request = None
        self.cancelled = False

        # Mirrors CalendarNudgeQuery's/ClaudeAction's own aboutToQuit wiring
        # so an in-flight miss-case request can't outlive the app.
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.cancel)

    def start(self):
        hit = search_notes(self.query, db_path=self.db_path)
        if hit is not None:
            self.on_result({"hit": True, **hit})
            return

        self.request = self.request_factory(EXPLAIN_PROMPT_TEMPLATE.format(query=self.query))
        self.request.chunk.connect(self.onChunk)
        self.request.finished.connect(self.onFinished)
        self.request.start()

    def onChunk(self, text):
        self.text += text

    def onFinished(self):
        # `finished` still fires after cancel() (ClaudeWorker's own
        # guarantee, see claude.py) - without this guard a cancelled query
        # would still hand the caller a truncated/garbage draft.
        if self.cancelled:
            return
        self.on_result({"hit": False, "draft": self.text})

    def cancel(self):
        self.cancelled = True
        if self.request is not None:
            self.request.cancel()


class TriageQuery:
    """Drives the inbox-triage flow (issue 04) for one Inbox entry, using
    issue 02's chosen architecture: Bel's own code calls this directly and
    the miss/hit-style branching from ExplainQuery doesn't apply here - every
    entry gets a proposal, shown to Derich to confirm before move_inbox_entry
    ever runs. Mirrors ExplainQuery's shape (one ClaudeRequest per query, a
    background QThread so the CLI subprocess doesn't block the UI)."""

    def __init__(self, path, on_result, request_factory=ClaudeRequest):
        self.path = Path(path)
        self.on_result = on_result
        self.request_factory = request_factory  # swappable in tests, so triage never spawns a real `claude` subprocess
        self.text = ""
        self.request = None
        self.cancelled = False

        # Mirrors ExplainQuery's/CalendarNudgeQuery's own aboutToQuit wiring
        # so an in-flight triage request can't outlive the app.
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.cancel)

    def start(self):
        # Mirrors vaultIndex.refresh()'s own tolerance for a file that
        # disappears or turns unreadable out from under it - the window
        # between list_inbox_entries() listing this entry and the user
        # picking it isn't instantaneous.
        try:
            content = self.path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            self.on_result({"path": self.path, "folder": None})
            return
        prompt = TRIAGE_PROMPT_TEMPLATE.format(title=self.path.stem, content=content)
        self.request = self.request_factory(prompt)
        self.request.chunk.connect(self.onChunk)
        self.request.finished.connect(self.onFinished)
        self.request.start()

    def onChunk(self, text):
        self.text += text

    def onFinished(self):
        # `finished` still fires after cancel() (ClaudeWorker's own
        # guarantee, see claude.py) - without this guard a cancelled query
        # would still hand the caller a stale proposal.
        if self.cancelled:
            return
        self.on_result({"path": self.path, "folder": parse_triage_response(self.text)})

    def cancel(self):
        self.cancelled = True
        if self.request is not None:
            self.request.cancel()
