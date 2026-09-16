# The issue-02 integration point (.scratch/vault-search/issues/02): Bel's
# own Qt-side code calls search_notes() directly and decides hit/miss
# itself - no MCP tool, no agent-loop wiring. askBel() (via ClaudeRequest,
# same convention as CalendarNudgeQuery in calendarNudge.py) is only invoked
# for the miss-case draft.
#
# write_concept_note/append_vocab_row are the confirm-before-write half of
# issue 03 steps 4-5: nothing writes to the vault until one of these is
# called explicitly, which only happens after Derich confirms the drafted
# text - ExplainQuery itself never calls them.
#
# The `[[Concept]]` auto-insert (issue 03 steps 3-4) needed a concrete
# answer to "which note is Derich currently writing" before it could be
# built - issue 05 resolved that as manual designation: Derich points Bel at
# a note (set_current_note), sticky until he changes it, no OS/Obsidian
# integration required. insert_concept_link is a no-op rather than an error
# when nothing's designated or the designated note can't be found - it's a
# convenience on top of the primary explain/write flow, never something that
# should block it. Only concept-note hits/writes get a link - a `[[word]]`
# link to a Korean vocab table row wouldn't resolve to anything in Obsidian,
# so append_vocab_row doesn't call it.
#
# TriageQuery (issue 04) follows the same confirm-before-write split: it
# only proposes a destination folder for an Inbox entry (list_inbox_entries
# + parse_triage_response), never moves anything itself. move_inbox_entry is
# the separate, explicit call for after Derich confirms the proposal - like
# issue 03's write functions, it performs the move with no confirmation of
# its own (and, like write_concept_note, refuses to clobber an existing
# file). Wiring a UI surface to drive this per-entry is
# also still deferred, same as the `[[Concept]]` link above.

import re
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal
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
                # Whole-cell match, not a substring of the file - "an" must
                # not hit a row translated as "and, additionally" (issue 12).
                if any(
                    cell.casefold() == query.casefold()
                    for line in content.splitlines()
                    for cell in table_cells(line)
                ):
                    return {"kind": "vocab", "path": path, "content": content}

        return None
    finally:
        conn.close()


# Bel's own local state, matching the Path.home() / ".bel" convention already
# used for vaultIndex.INDEX_DB_PATH and claude.py's CLAUDE_CWD.
CURRENT_NOTE_PATH = Path.home() / ".bel" / "current-note.txt"


def set_current_note(path, store_path=None):
    """Designates `path` (vault-relative, matching search_notes' own "path"
    format) as the note Derich is currently writing (issue 05's manual-
    designation decision) - sticky until the next call to set_current_note.
    Bel has no view onto Obsidian's own editor state, so this is the only
    way it learns where insert_concept_link should write."""
    store_path = store_path or CURRENT_NOTE_PATH
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(str(path), encoding="utf-8")


def get_current_note(store_path=None):
    """Returns the designated path, or None if Derich hasn't set one yet."""
    store_path = store_path or CURRENT_NOTE_PATH
    try:
        return store_path.read_text(encoding="utf-8")
    except OSError:
        return None


def insert_concept_link(query, vault_path=None, store_path=None):
    """Auto-inserts a `[[query]]` link into the currently-designated note
    (issue 03 steps 3-4) - mechanical and low-risk, so no confirmation of
    its own. Appended as its own line, matching append_vocab_row's
    append-only style, since Bel has no notion of cursor position in a file
    it doesn't render. A no-op, not an error, when no note is designated or
    it can no longer be found - see the module comment above."""
    current = get_current_note(store_path=store_path)
    if current is None:
        return None
    vault_path = vault_path or vaultIndex.VAULT_PATH
    path = vault_path / current
    # set_current_note accepts any string, so the Private exclusion has to
    # be enforced here, before is_file() even stats the path. Resolved first
    # so "..", an absolute path, or a path outside the vault can't sneak
    # past the top-folder check.
    try:
        relative = path.resolve().relative_to(vault_path.resolve())
    except ValueError:
        return None
    if not relative.parts or vaultIndex.folder_name(Path(relative.parts[0])).casefold() in vaultIndex.EXCLUDED_FOLDERS:
        return None
    if not path.is_file():
        # Append mode (below) would otherwise happily create a stub file
        # here if just the file (not its parent folder) went missing since
        # it was designated - that would violate this function's own
        # no-op-when-not-found contract.
        return None
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(f"\n[[{query}]]\n")
    except OSError:
        return None
    return path


def escape_table_cell(text):
    """Escapes a value for embedding in a markdown table row - Obsidian's
    table syntax breaks on a literal "|" (spurious column) or newline
    (spurious row), and a drafted translation isn't guaranteed free of
    either."""
    return text.replace("|", "\\|").replace("\n", " ")


def table_cells(line):
    """Splits a markdown table row into its cell values - the reverse of
    escape_table_cell, so an escaped "\\|" stays inside its cell."""
    return [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", line)]


def write_concept_note(query, content, vault_path=None, store_path=None):
    """Writes a confirmed miss-case explanation as a new atomic concept
    note (issue 03 step 4). Call only after Derich has confirmed the draft
    - this performs the write with no confirmation of its own, but refuses
    to overwrite an existing note. Also auto-inserts the `[[query]]` link
    into whatever note is currently designated (issue 03 step 4's "no separate confirmation for
    the link itself") - see insert_concept_link."""
    if re.search(r'[<>:"/\\|?*\x00-\x1f]', query):
        # Windows' illegal filename characters. "/" and "\\" would write
        # outside "Reference/"; ":" silently writes an NTFS alternate data
        # stream instead of a note; the rest raise an OSError.
        raise ValueError(f"query must be a single valid note title: {query!r}")
    vault_path = vault_path or vaultIndex.VAULT_PATH
    reference = vaultIndex.resolve_top_folder(vault_path, "Reference")
    path = reference / f"{query}.md"
    # "x" (exclusive create) raises FileExistsError rather than clobbering a
    # real note that search_notes() missed on a stale index - same refusal
    # as move_inbox_entry.
    with path.open("x", encoding="utf-8") as f:
        f.write(content)
    insert_concept_link(query, vault_path=vault_path, store_path=store_path)
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


class SearchWorker(QObject):
    """Runs search_notes() on a background thread, mirroring ClaudeWorker's
    cross-thread pattern (see claude.py). search_notes() pulls every
    indexed path into memory and, on a hit, fetches the matched note's
    content, all before returning - keeping that off the Qt main thread is
    this worker's whole reason to exist (issue 08)."""

    finished = Signal(object)

    def __init__(self, query, db_path=None):
        super().__init__()
        self.query = query
        self.db_path = db_path

    def run(self):
        # `finished` must always fire, same as ClaudeWorker.run - it's the
        # only thing that resolves the query and lets ExplainQuery disconnect
        # from aboutToQuit (issue 18). A failed lookup (locked db, a row
        # deleted mid-search) is reported as a miss.
        try:
            hit = search_notes(self.query, db_path=self.db_path)
        except Exception:
            hit = None
        self.finished.emit(hit)


class SearchRequest(QObject):
    """One search_notes() lookup, start to finish. Mirrors ClaudeRequest's
    shape (actions/claudeAction.py): moves the actual lookup to a
    background QThread so ExplainQuery.start() - which used to call
    search_notes() straight on its own (UI) thread - doesn't block on it
    (issue 08)."""

    finished = Signal(object)

    def __init__(self, query, db_path=None, parent=None):
        super().__init__(parent)
        self.thread = QThread()
        self.worker = SearchWorker(query, db_path=db_path)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.onWorkerFinished)

    def start(self):
        self.thread.start()

    def onWorkerFinished(self, hit):
        # Runs on the main thread - the worker emits this from its own
        # thread as run() returns, so by now there is nothing left to wait
        # for. Mirrors ClaudeRequest.onWorkerFinished.
        self.thread.quit()
        self.thread.wait(2000)
        self.finished.emit(hit)

    def cancel(self):
        # Unlike ClaudeRequest.cancel(), there's no subprocess to terminate
        # - search_notes() is a bounded local SQLite read with nothing to
        # interrupt mid-flight - so this just confirms the thread has
        # stopped before returning (matters most when called from
        # aboutToQuit, since the app may not get another event loop turn
        # afterward).
        self.thread.quit()
        self.thread.wait(2000)


class ExplainQuery:
    """Drives the explain-on-miss half of issue 03, using issue 02's chosen
    architecture. Mirrors CalendarNudgeQuery's shape (calendarNudge.py): a
    plain callback-based class wrapping one ClaudeRequest, rather than a
    bare askBel() call, so the CLI subprocess still runs on a background
    QThread instead of blocking the UI. The hit-path search_notes() lookup
    is threaded the same way, via SearchRequest (issue 08) - neither path
    touches the UI thread with slow work."""

    def __init__(
        self,
        query,
        on_result,
        db_path=None,
        vault_path=None,
        store_path=None,
        request_factory=ClaudeRequest,
        search_request_factory=SearchRequest,
    ):
        self.query = query
        self.on_result = on_result
        self.db_path = db_path
        self.vault_path = vault_path  # passed through to insert_concept_link on a concept hit
        self.store_path = store_path  # passed through to insert_concept_link on a concept hit
        self.request_factory = request_factory  # swappable in tests, so the miss path never spawns a real `claude` subprocess
        self.search_request_factory = search_request_factory  # swappable in tests, so the hit-path lookup doesn't need a real QThread/event loop
        self.text = ""
        self.search_request = None
        self.request = None
        self.cancelled = False

        # Mirrors CalendarNudgeQuery's/ClaudeAction's own aboutToQuit wiring
        # so an in-flight miss-case request can't outlive the app.
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.cancel)

    def start(self):
        self.search_request = self.search_request_factory(self.query, db_path=self.db_path)
        self.search_request.finished.connect(self.onSearchFinished)
        self.search_request.start()

    def onSearchFinished(self, hit):
        # `finished` still fires after cancel() (SearchRequest mirrors
        # ClaudeRequest's guarantee here) - without this guard a cancelled
        # query could still kick off the miss-case draft or a stale link
        # insert after the caller has moved on. Must disconnect here too
        # (not just return), same as onFinished's guard below - otherwise a
        # query cancelled while its search is still in flight never
        # disconnects from aboutToQuit and leaks for the app's lifetime
        # (issue 06, reintroduced for this path).
        if self.cancelled:
            self.disconnectAboutToQuit()
            return
        if hit is not None:
            if hit["kind"] == "concept":
                # A `[[word]]` link to a Korean vocab table row wouldn't
                # resolve to anything in Obsidian - only concept-note hits
                # get the auto-insert (see insert_concept_link). Linked by
                # the matched note's real filename, not self.query - a hit
                # can be case-insensitive (search_notes/folder_matches), so
                # the query text isn't guaranteed to match the note's actual
                # on-disk title.
                concept_name = Path(hit["path"]).stem
                insert_concept_link(concept_name, vault_path=self.vault_path, store_path=self.store_path)
            self.disconnectAboutToQuit()
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
        self.disconnectAboutToQuit()
        if self.cancelled:
            return
        self.on_result({"hit": False, "draft": self.text})

    def cancel(self):
        self.cancelled = True
        if self.search_request is not None:
            self.search_request.cancel()
        if self.request is not None:
            self.request.cancel()

    def disconnectAboutToQuit(self):
        # Undoes the __init__ wiring once this query resolves. aboutToQuit
        # holds a strong reference to the connected bound method, so leaving
        # it connected would keep every past ExplainQuery alive for the rest
        # of the app's life - unbounded growth proportional to search count
        # (issue 06).
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.disconnect(self.cancel)


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
            self.disconnectAboutToQuit()
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
        self.disconnectAboutToQuit()
        if self.cancelled:
            return
        self.on_result({"path": self.path, "folder": parse_triage_response(self.text)})

    def cancel(self):
        self.cancelled = True
        if self.request is not None:
            self.request.cancel()

    def disconnectAboutToQuit(self):
        # Mirrors ExplainQuery.disconnectAboutToQuit - same leak, same fix
        # (issue 06): aboutToQuit holds a strong reference to self.cancel,
        # so leaving it connected would keep every past TriageQuery alive
        # for the rest of the app's life.
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.disconnect(self.cancel)
