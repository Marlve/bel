# The issue-02 integration point (.scratch/vault-search/issues/02): Bel's
# own Qt-side code calls search_notes() directly and decides hit/miss
# itself - no MCP tool, no agent-loop wiring. askBel() (via ClaudeRequest,
# same convention as CalendarNudgeQuery in calendarNudge.py) is only invoked
# for the miss-case draft.
#
# The confirm-before-write dialog, the actual write to `3 Reference/`, and
# the auto-inserted `[[Concept]]` link (issue 03 steps 4-5) aren't built
# here yet - those need a concrete UI trigger point (which note surface,
# what dialog) that hasn't been designed.

from pathlib import Path

from PySide6.QtWidgets import QApplication

import vaultIndex
from actions.claudeAction import ClaudeRequest

EXPLAIN_PROMPT_TEMPLATE = 'Explain "{query}" concisely, for a personal reference note.'


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
