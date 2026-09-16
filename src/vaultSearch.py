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
# The `[[Concept]]` link goes into whichever note Derich clicks in card.md's
# note picker, shown on every `?` lookup - nothing is remembered between
# lookups (this replaced issue 05's sticky set_current_note designation). On
# a concept miss, that click is also the confirmation for writing the draft
# (confirm_pick). A Korean miss shows Claude's translation, and for a single
# word the picker offers Vocab.md as its one row - clicking it appends the
# word (issue 23). A sentence is never saved. insert_concept_link is a no-op
# rather than an error when the picked note can't be found - it's a
# convenience on top of the primary
# explain/write flow, never something that should block it. Only
# concept-note hits/writes get a link - a `[[word]]` link to a Korean vocab
# table row wouldn't resolve to anything in Obsidian, so append_vocab_row
# doesn't call it.
#
# TriageQuery (issue 04) follows the same confirm-before-write split: it
# only proposes a destination folder for an Inbox entry (list_inbox_entries
# + parse_triage_response), never moves anything itself. move_inbox_entry is
# the separate, explicit call for after Derich confirms the proposal - like
# issue 03's write functions, it performs the move with no confirmation of
# its own (and, like write_concept_note, refuses to clobber an existing
# file). Wiring a UI surface to drive this per-entry is
# also still deferred, same as the `[[Concept]]` link above.

import os
import re
import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal

import vaultIndex
from actions.claudeAction import ClaudeQuery, ClaudeRequest
from backgroundRequest import BackgroundRequest

EXPLAIN_PROMPT_TEMPLATE = 'Explain "{query}" concisely, for a personal reference note.'

KOREAN_PROMPT_TEMPLATE = 'Translate the Korean "{query}" into English. Reply with only the translation, no explanation.'

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


LOOKUP_PREFIX = "?"

RECENT_NOTES_LIMIT = 20
RECENT_SECONDS = 24 * 60 * 60  # edited within this long counts as "recent" (card.md's sand dot)


def lookup_query(text):
    """The search term of a `? Dijkstra`-style chat message, or None if the
    message is normal chat (card.md's trigger). A bare "?" is not a lookup -
    it would otherwise draft a note titled ".md"."""
    if not text.startswith(LOOKUP_PREFIX):
        return None
    return text[len(LOOKUP_PREFIX):].strip() or None


def all_notes(db_path=None, now=None):
    """Every indexed note, most recently edited first - what the note
    picker's filter field searches (issue 24). The index never contains
    `6 Private/`, so neither does this list."""
    now = time.time() if now is None else now
    conn = vaultIndex.connect(db_path)
    try:
        rows = conn.execute("SELECT path, mtime FROM notes ORDER BY mtime DESC").fetchall()
    finally:
        conn.close()
    return [{"path": path, "recent": now - mtime <= RECENT_SECONDS} for path, mtime in rows]


def vocab_note(db_path=None, now=None):
    """The indexed Korean Vocab.md in the picker's note shape, or None if
    there isn't one - a new word can only be offered for saving into a
    Vocab.md that exists (issue 23)."""
    now = time.time() if now is None else now
    conn = vaultIndex.connect(db_path)
    try:
        rows = conn.execute("SELECT path, mtime FROM notes").fetchall()
    finally:
        conn.close()
    for path, mtime in rows:
        if folder_matches(path, "Areas", "Korean", "Vocab.md"):
            return {"path": path, "recent": now - mtime <= RECENT_SECONDS}
    return None


def is_vocab_query(query):
    """A query containing Hangul is a Korean vocab lookup, not a concept."""
    return re.search(r"[ᄀ-ᇿ㄰-㆏가-힣]", query) is not None


def is_single_word(query):
    """Only a single Korean word is offered for saving, never a sentence."""
    return bool(query) and not any(char.isspace() for char in query)


def lookup(query, vault_path=None, db_path=None):
    """Everything a `?` lookup needs from the vault, in one call so
    SearchWorker can run it all off the UI thread: the index is refreshed
    first (nothing else in the app refreshes it), then searched, then
    listed for the note picker: the recent notes it shows while its filter is
    empty, and every note for the filter to search."""
    vaultIndex.refresh(vault_path=vault_path, db_path=db_path)
    notes = all_notes(db_path=db_path)
    return {
        "found": search_notes(query, db_path=db_path),
        "notes": notes[:RECENT_NOTES_LIMIT],
        "all_notes": notes,
        "vocab": vocab_note(db_path=db_path),
    }


def search_notes(query, db_path=None):
    """Checks for an existing answer to `query` before Bel explains or files
    anything new: an atomic concept note at `<Reference>/<query>.md`, or a
    matching row inside `<Areas>/Korean/Vocab.md`. Returns a dict describing
    the hit, or None on a miss.

    Looks up paths first and only fetches a candidate's content once it has
    matched by path, rather than pulling every note's full text into memory
    up front - the FTS5 index exists precisely so this doesn't have to
    rescan the whole vault's content per call. Content is fetched by rowid,
    not path - `WHERE path = ?` would be a second full scan (issue 20)."""
    conn = vaultIndex.connect(db_path)
    try:
        # One read transaction, so a refresh() committing between the two
        # queries can't reuse a matched rowid for a different note.
        conn.execute("BEGIN")
        rows = conn.execute("SELECT rowid, path FROM notes").fetchall()

        for rowid, path in rows:
            if folder_matches(path, "Reference", f"{query}.md"):
                content = conn.execute("SELECT content FROM notes WHERE rowid = ?", (rowid,)).fetchone()[0]
                return {"kind": "concept", "path": path, "content": content}

        for rowid, path in rows:
            if folder_matches(path, "Areas", "Korean", "Vocab.md"):
                content = conn.execute("SELECT content FROM notes WHERE rowid = ?", (rowid,)).fetchone()[0]
                # Whole-cell match on real entries, not a substring of the
                # file - "an" must not hit a row translated as "and,
                # additionally" (issue 12).
                wanted = query.strip().casefold()
                for cells in table_rows(content):
                    if wanted and any(cell.casefold() == wanted for cell in cells):
                        row = [cell for cell in cells if cell]
                        return {"kind": "vocab", "path": path, "content": content, "row": row}

        return None
    finally:
        conn.close()


def is_off_limits(relative):
    """True if a vault-relative path escapes the vault or lands in the
    Private folder."""
    return (
        not relative.parts
        or bool(relative.anchor)
        or relative.parts[0] == ".."
        or vaultIndex.folder_name(Path(relative.parts[0])).casefold() in vaultIndex.EXCLUDED_FOLDERS
    )


CONCEPTS_HEADING = "## Concepts"
GIST_MAX_LENGTH = 80


def concept_gist(text):
    """The one-line gist beside a `[[Concept]]` bullet (issue 25): the first
    sentence of the concept's note or draft, skipping frontmatter and
    headings, cut at a word to GIST_MAX_LENGTH."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        closing = next((index for index in range(1, len(lines)) if lines[index].strip() == "---"), None)
        if closing is not None:
            lines = lines[closing + 1:]
    paragraph = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            paragraph.append(line)
        elif paragraph:
            break
    text = " ".join(paragraph)
    sentence = re.match(r".+?[.!?](?=\s|$)", text)
    gist = (sentence.group() if sentence else text).removesuffix(".")
    if len(gist) > GIST_MAX_LENGTH:
        cut = gist[:GIST_MAX_LENGTH - 1]
        gist = (cut[:cut.rindex(" ")] if " " in cut else cut).rstrip(" ,;:") + "…"
    return gist


def with_concept_bullet(lines, concept, bullet):
    """`lines` with `bullet` added to the note's Concepts section: after the
    section's last bullet, so it stays inside the section even when other
    content follows it, or under a new heading at the end. None if the
    section already links `concept`."""
    lines = list(lines)
    heading = next(
        (index for index, line in enumerate(lines) if line.strip().casefold() == CONCEPTS_HEADING.casefold()),
        None,
    )
    if heading is None:
        at = len(lines)
        added = [CONCEPTS_HEADING + "\n", bullet]
        if lines and lines[-1].strip():
            added.insert(0, "\n")
    else:
        at = heading + 1
        added = [bullet]
        # Only the bullet's own leading link, so a link inside another
        # bullet's gist doesn't count. `[[X#Heading]]` and `[[X|alias]]` do.
        listed = re.compile(rf"[-*+] \[\[{re.escape(concept)}(\]\]|\||#)", re.IGNORECASE)
        for index in range(heading + 1, len(lines)):
            line = lines[index].strip()
            if line.startswith(("- ", "* ", "+ ")):
                if listed.match(line):
                    return None
                at = index + 1
            elif line:
                break
    if at == len(lines) and lines and not lines[-1].endswith("\n"):
        # Obsidian can save a note without a trailing newline.
        lines[-1] += "\n"
    return lines[:at] + added + lines[at:]


def insert_concept_link(query, note, gist="", vault_path=None):
    """Adds a `- [[query]] — gist` bullet to the `## Concepts` section of
    `note` (vault-relative), the note Derich picked in card.md's picker
    (issue 25). Bel has no notion of cursor position in a file it doesn't
    render, so the link always goes in that section. A no-op, not an error,
    when the note can no longer be found - see the module comment above.
    A concept the section already lists is left alone but still returns
    the note, since it is connected."""
    vault_path = vault_path or vaultIndex.VAULT_PATH
    # `note` is any string as far as this function knows, so the Private
    # exclusion has to be enforced here (issue 16). Checked on the path
    # string first, so an ordinary Private path is refused without touching
    # the filesystem at all - even resolve() opens a handle on Windows. The
    # resolved check after it catches aliases a string can't see (8.3 short
    # names, junctions, the trailing dots/spaces Windows ignores).
    if is_off_limits(Path(os.path.normpath(note))):
        return None
    path = vault_path / note
    try:
        if is_off_limits(path.resolve().relative_to(vault_path.resolve())):
            return None
    except ValueError:
        return None
    if not path.is_file():
        # Checked up front so a note that went missing since it was listed
        # is reported as not found - this function never creates a stub.
        return None
    bullet = f"- [[{query}]] — {gist}\n" if gist else f"- [[{query}]]\n"
    try:
        # Bytes in and out, so Windows' text mode can't turn "\n" into CRLF.
        lines = with_concept_bullet(path.read_bytes().decode("utf-8").splitlines(keepends=True), query, bullet)
        if lines is not None:
            path.write_bytes("".join(lines).encode("utf-8"))
    except (OSError, UnicodeDecodeError):
        return None
    return path


def escape_table_cell(text):
    """Escapes a value for embedding in a markdown table row - Obsidian's
    table syntax breaks on a literal "|" (spurious column) or newline
    (spurious row), and a drafted translation isn't guaranteed free of
    either."""
    return re.sub(r"\r\n|\r|\n", " ", text.replace("|", "\\|"))


def table_cells(line):
    """Splits a markdown table row into its cell values, undoing
    escape_table_cell's pipe escaping so an escaped "\\|" stays inside its
    cell."""
    return [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", line)]


def is_separator_row(line):
    return line.startswith("|") and re.fullmatch(r"[|:\-\s]+", line) is not None


def table_rows(content):
    """Yields the cells of each data row in `content`'s markdown tables -
    headings, prose, header rows, and `| --- |` separator rows are skipped,
    so only real entries can count as a vocab hit."""
    lines = [line.strip() for line in content.splitlines()]
    for line, next_line in zip(lines, lines[1:] + [""]):
        if line.startswith("|") and not is_separator_row(line) and not is_separator_row(next_line):
            yield table_cells(line)


def is_valid_note_title(query):
    """False if `query` contains a character Windows forbids in filenames.
    "/" and "\\" would write outside "Reference/"; ":" silently writes an
    NTFS alternate data stream instead of a note; the rest raise an
    OSError."""
    return re.search(r'[<>:"/\\|?*\x00-\x1f]', query) is None


def write_concept_note(query, content, vault_path=None):
    """Writes a confirmed miss-case explanation as a new atomic concept
    note (issue 03 step 4). Call only after Derich has confirmed the draft
    - this performs the write with no confirmation of its own, but refuses
    to overwrite an existing note."""
    if not is_valid_note_title(query):
        raise ValueError(f"query must be a single valid note title: {query!r}")
    vault_path = vault_path or vaultIndex.VAULT_PATH
    reference = vaultIndex.resolve_top_folder(vault_path, "Reference")
    path = reference / f"{query}.md"
    # "x" (exclusive create) raises FileExistsError rather than clobbering a
    # real note that search_notes() missed on a stale index - same refusal
    # as move_inbox_entry.
    with path.open("x", encoding="utf-8") as f:
        f.write(content)
    return path


def confirm_pick(query, result, note, vault_path=None):
    """Derich clicked `note` in the picker for ExplainQuery's `result` -
    card.md's "clicking a row is the action". On a concept hit that only
    inserts the link, named after the matched note's real filename (a hit
    can be case-insensitive, so the query's casing isn't the title's). On a
    miss the click is also the confirmation: the draft is written as a new
    note first, and the link is only inserted once that write succeeds."""
    if result["hit"]:
        concept = Path(result["path"]).stem
        gist = concept_gist(result["content"])
    else:
        write_concept_note(query, result["draft"], vault_path=vault_path)
        concept = query
        gist = concept_gist(result["draft"])
    return insert_concept_link(concept, note, gist=gist, vault_path=vault_path)


def append_vocab_row(word, translation, vault_path=None):
    """Appends a confirmed word/translation pair to the Korean vocab table
    (issue 03's "same shape applies to Korean vocab" note). Call only after
    Derich has confirmed the row - clicking Vocab.md in the chat card's
    picker (issue 23)."""
    vault_path = vault_path or vaultIndex.VAULT_PATH
    areas = vaultIndex.resolve_top_folder(vault_path, "Areas")
    path = areas / "Korean" / "Vocab.md"
    row = f"| {escape_table_cell(word)} | {escape_table_cell(translation)} |\n"
    # Bytes in and out, so Windows' text mode can't turn "\n" into CRLF.
    lines = path.read_bytes().decode("utf-8").splitlines(keepends=True) if path.exists() else []
    at = vocab_row_insert_index(lines)
    if at == len(lines) and lines and not lines[-1].endswith("\n"):
        # Obsidian can save a note without a trailing newline, and the row
        # must not glue onto the table's last line.
        lines[-1] += "\n"
    lines.insert(at, row)
    path.write_bytes("".join(lines).encode("utf-8"))
    return path


def vocab_row_insert_index(lines):
    """Where a new row goes: right after the first table's last filled-in
    row. Obsidian's table editor leaves empty rows and blank lines after a
    table, and a row appended past them would sit outside the table. With
    no table, it goes at the end."""
    for separator in range(1, len(lines)):
        if lines[separator - 1].strip().startswith("|") and is_separator_row(lines[separator].strip()):
            at = separator + 1
            for index in range(separator + 1, len(lines)):
                line = lines[index].strip()
                if not line.startswith("|"):
                    break
                if any(table_cells(line)):
                    at = index + 1
            return at
    return len(lines)


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
    """Runs lookup() on a background thread, mirroring ClaudeWorker's
    cross-thread pattern (see claude.py). lookup() refreshes the index,
    searches it and lists the picker's notes, all before returning - keeping
    that off the Qt main thread is this worker's whole reason to exist
    (issue 08)."""

    finished = Signal(object)

    def __init__(self, query, vault_path=None, db_path=None):
        super().__init__()
        self.query = query
        self.vault_path = vault_path
        self.db_path = db_path

    def run(self):
        # `finished` must always fire, same as ClaudeWorker.run - it's the
        # only thing that resolves the query and lets ExplainQuery disconnect
        # from aboutToQuit (issue 18). A failed lookup (locked db, a row
        # deleted mid-search) is reported as a miss with no notes to pick,
        # so nothing can be written off the back of it.
        try:
            outcome = lookup(self.query, vault_path=self.vault_path, db_path=self.db_path)
        except Exception:
            outcome = {"found": None, "notes": [], "all_notes": [], "vocab": None}
        self.finished.emit(outcome)


class SearchRequest(BackgroundRequest):
    """One lookup(), start to finish. Shares ClaudeRequest's thread lifecycle
    via BackgroundRequest: moves the actual lookup to a background QThread
    so ExplainQuery.start() - which used to call search_notes() straight on
    its own (UI) thread - doesn't block on it (issue 08)."""

    finished = Signal(object)

    def __init__(self, query, vault_path=None, db_path=None, parent=None):
        super().__init__(SearchWorker(query, vault_path=vault_path, db_path=db_path), parent)
        self.worker.finished.connect(self.onWorkerFinished)

    def onWorkerFinished(self, outcome):
        # Runs on the main thread - the worker emits this from its own
        # thread as run() returns, so by now there is nothing left to wait
        # for. Mirrors ClaudeRequest.onWorkerFinished.
        self.stopThread()
        self.finished.emit(outcome)

    def cancel(self):
        # Unlike ClaudeRequest.cancel(), there's no subprocess to terminate
        # - lookup() is a bounded local read/index refresh with nothing to
        # interrupt mid-flight - so this just confirms the thread has
        # stopped.
        self.stopThread()


class ExplainQuery(ClaudeQuery):
    """Drives one `? query` lookup for card.md's picker, using issue 02's
    chosen architecture. A ClaudeQuery, rather than a bare askBel() call, so
    the CLI subprocess still runs on a background QThread instead of
    blocking the UI. The lookup itself is threaded the same way, via
    SearchRequest (issue 08) - neither path touches the UI thread with slow
    work.

    Never writes to the vault: on_result gets the hit or draft plus the
    notes to pick from, and confirm_pick does the writing once Derich
    clicks one."""

    def __init__(
        self,
        query,
        on_result,
        db_path=None,
        vault_path=None,
        request_factory=ClaudeRequest,
        search_request_factory=SearchRequest,
    ):
        super().__init__(request_factory)
        self.query = query
        self.on_result = on_result
        self.db_path = db_path
        self.vault_path = vault_path
        self.search_request_factory = search_request_factory  # swappable in tests, so the lookup doesn't need a real QThread/event loop
        self.notes = []
        self.all_notes = []
        self.vocab = None
        self.kind = None
        self.search_request = None

    def start(self):
        self.search_request = self.search_request_factory(self.query, vault_path=self.vault_path, db_path=self.db_path)
        self.search_request.finished.connect(self.onSearchFinished)
        self.search_request.start()

    def onSearchFinished(self, outcome):
        # `finished` still fires after cancel() (SearchRequest mirrors
        # ClaudeRequest's guarantee here) - without this guard a cancelled
        # query could still kick off the miss-case draft after the caller
        # has moved on. Must disconnect here too (not just return), same as
        # ClaudeQuery.onFinished's guard - otherwise a query cancelled while its
        # search is still in flight never disconnects from aboutToQuit and
        # leaks for the app's lifetime (issue 06, reintroduced for this path).
        # ClaudeQuery only covers the Claude half, so this guard stays here.
        if self.cancelled:
            self.disconnectAboutToQuit()
            return
        self.notes = outcome["notes"]
        self.all_notes = outcome["all_notes"]
        self.vocab = outcome["vocab"]
        hit = outcome["found"]
        if hit is not None:
            self.disconnectAboutToQuit()
            # Linking the matched note into itself is never what's wanted.
            notes = [note for note in self.notes if note["path"] != hit["path"]]
            all_notes = [note for note in self.all_notes if note["path"] != hit["path"]]
            self.on_result({"hit": True, **hit, "notes": notes, "all_notes": all_notes})
            return
        if is_vocab_query(self.query):
            # Reported as kind "vocab", so the translation is only ever
            # offered for saving into Vocab.md, never as
            # "3 Reference/<word>.md" (issues 22, 23).
            self.kind = "vocab"
            prompt = KOREAN_PROMPT_TEMPLATE.format(query=self.query)
        else:
            self.kind = "concept"
            prompt = EXPLAIN_PROMPT_TEMPLATE.format(query=self.query)
        self.ask(prompt)

    def answered(self, text, failed):
        # An error or cut-off answer is reported as no draft at all, so it can
        # never be offered for saving.
        draft = "" if failed else text
        result = {"hit": False, "kind": self.kind, "draft": draft, "notes": self.notes, "all_notes": self.all_notes}
        if self.kind == "vocab":
            result["vocab"] = self.vocab
        self.on_result(result)

    def cancel(self):
        super().cancel()
        if self.search_request is not None:
            self.search_request.cancel()


class TriageQuery(ClaudeQuery):
    """Drives the inbox-triage flow (issue 04) for one Inbox entry, using
    issue 02's chosen architecture: Bel's own code calls this directly and
    the miss/hit-style branching from ExplainQuery doesn't apply here - every
    entry gets a proposal, shown to Derich to confirm before move_inbox_entry
    ever runs. A ClaudeQuery like ExplainQuery (one ClaudeRequest per query,
    a background QThread so the CLI subprocess doesn't block the UI)."""

    def __init__(self, path, on_result, request_factory=ClaudeRequest):
        super().__init__(request_factory)
        self.path = Path(path)
        self.on_result = on_result

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
        self.ask(TRIAGE_PROMPT_TEMPLATE.format(title=self.path.stem, content=content))

    def answered(self, text, failed):
        self.on_result({"path": self.path, "folder": parse_triage_response(text)})
